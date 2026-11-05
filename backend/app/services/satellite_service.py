"""Satellite service for Sentinel-2 11-band MARIDA U-Net inference."""

from __future__ import annotations

import base64
from io import BytesIO
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

import numpy as np
from PIL import Image
try:
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import Affine
except (ImportError, OSError) as exc:
    rasterio = None
    MemoryFile = None
    Affine = None
    _RASTERIO_IMPORT_ERROR = exc
else:
    _RASTERIO_IMPORT_ERROR = None
try:
    import torch
except (ImportError, OSError) as exc:
    torch = None
    _TORCH_IMPORT_ERROR = exc
else:
    _TORCH_IMPORT_ERROR = None

from app.core.config import settings
try:
    from app.ml.satellite.detector import DebrisDetector
except (ImportError, OSError) as exc:
    DebrisDetector = None
    _DETECTOR_IMPORT_ERROR = exc
else:
    _DETECTOR_IMPORT_ERROR = None
from app.schemas.satellite import HotspotCatalogItem, SatelliteAnalysisResponse, SatelliteRasterMetadata

logger = logging.getLogger(__name__)

# Backend base directory
_BACKEND_ROOT = Path(__file__).resolve().parents[2]

# MARIDA's 15 source labels are consolidated to 11 segmentation labels. The
# model's existing pipeline assigns index 0 to Marine Debris.
MARIDA_CLASSES = (
    ("Marine Debris", "#ef4444"),
    ("Dense Sargassum", "#f97316"),
    ("Sparse Sargassum", "#eab308"),
    ("Natural Organic Material", "#a855f7"),
    ("Ship", "#ec4899"),
    ("Clouds", "#e2e8f0"),
    ("Marine Water", "#2563eb"),
    ("Sediment-Laden Water", "#92400e"),
    ("Foam", "#f8fafc"),
    ("Turbid Water", "#14b8a6"),
    ("Shallow Water", "#22c55e"),
)
SENTINEL2_BAND_ORDER = ("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12")
UNCERTAIN_CLASS_ID = 254
INVALID_CLASS_ID = 255


class _ConfidenceClassification(NamedTuple):
    mask: np.ndarray
    confident_pixels: np.ndarray
    uncertain_pixels: np.ndarray
    average_confidence: float
    debris_pixel_count: int
    debris_coverage_percentage: Optional[float]
    excluded_pixel_count: int
    excluded_pixel_percentage: float


class SatelliteUnavailableError(RuntimeError):
    """Raised when satellite inference cannot run in the current environment."""


class InvalidSatelliteRasterError(ValueError):
    """Raised when an input raster is unreadable or has an unsupported structure."""


class SatelliteService:
    """Singleton service for MARIDA U-Net Sentinel-2 satellite analysis."""

    _detector: Optional[DebrisDetector] = None

    # Bundled demonstration rasters are not verified MARIDA/Sentinel-2 inputs.
    CATALOG: Dict[str, Dict[str, Any]] = {
        "accra-coast": {
            "id": "accra-coast",
            "name": "Accra Coast, Ghana",
            "coordinates": [5.55, -0.20],
            "description": "Bundled GeoTIFF sample; satellite imagery and georeferencing provenance are unverified.",
            "sample_file": "samples/accra-coast.tif",
            "inference_available": False,
        },
        "gulf-of-honduras": {
            "id": "gulf-of-honduras",
            "name": "Gulf of Honduras",
            "coordinates": [15.80, -87.90],
            "description": "Bundled GeoTIFF sample; satellite imagery and georeferencing provenance are unverified.",
            "sample_file": "samples/gulf-of-honduras.tif",
            "inference_available": False,
        },
        "durban-harbor": {
            "id": "durban-harbor",
            "name": "Durban Harbor, South Africa",
            "coordinates": [-29.86, 31.02],
            "description": "Bundled GeoTIFF sample; satellite imagery and georeferencing provenance are unverified.",
            "sample_file": "samples/durban-harbor.tif",
            "inference_available": False,
        },
        "coastal-demo-site": {
            "id": "coastal-demo-site",
            "name": "Coastal Demo Site",
            "coordinates": [12.91, 74.85],
            "description": "Bundled GeoTIFF sample; satellite imagery and georeferencing provenance are unverified.",
            "sample_file": "samples/coastal-demo-site.tif",
            "inference_available": False,
        },
    }

    @classmethod
    def initialize(cls) -> None:
        """Load the U-Net model once during application startup."""
        if rasterio is None or torch is None or DebrisDetector is None:
            missing = []
            if rasterio is None:
                missing.append(f"rasterio ({_RASTERIO_IMPORT_ERROR})")
            if torch is None:
                missing.append(f"torch ({_TORCH_IMPORT_ERROR})")
            if DebrisDetector is None:
                missing.append(f"U-Net detector ({_DETECTOR_IMPORT_ERROR})")
            raise SatelliteUnavailableError(
                "Satellite inference dependencies are unavailable: "
                + ", ".join(missing)
                + ". Install the backend requirements in its active Python environment."
            )
        if cls._detector is None:
            model_path = _BACKEND_ROOT / settings.SATELLITE_MODEL_PATH
            if not model_path.is_file():
                raise SatelliteUnavailableError(
                    f"Satellite model checkpoint is unavailable ({model_path.name})."
                )
            logger.info("Initializing SatelliteService with model %s...", model_path.name)
            try:
                device = settings.SATELLITE_DEVICE
                if device.startswith("cuda") and not torch.cuda.is_available():
                    logger.warning("Configured CUDA device is unavailable; using CPU inference.")
                    device = "cpu"
                cls._detector = DebrisDetector(
                    model_path=model_path,
                    input_bands=11,
                    output_classes=11,
                    hidden_channels=16,
                    device=device,
                    class_names=[class_name for class_name, _ in MARIDA_CLASSES],
                    band_order=SENTINEL2_BAND_ORDER,
                )
            except (EOFError, OSError, RuntimeError, TypeError, ValueError, pickle.UnpicklingError) as exc:
                logger.exception("Satellite U-Net checkpoint initialization failed.")
                raise SatelliteUnavailableError(
                    f"Satellite model could not be verified or loaded: {exc}"
                ) from exc
            logger.info("SatelliteService successfully initialized.")

    @classmethod
    def get_detector(cls) -> DebrisDetector:
        """Ensure detector is initialized and return singleton instance."""
        if cls._detector is None:
            cls.initialize()
        if cls._detector is None:
            raise SatelliteUnavailableError("Satellite detector could not be initialized.")
        return cls._detector

    @classmethod
    def get_catalog(cls) -> List[HotspotCatalogItem]:
        """Return catalog of pre-registered coastal monitoring sites."""
        items: List[HotspotCatalogItem] = []
        for item in cls.CATALOG.values():
            sample_path = _BACKEND_ROOT / item["sample_file"]
            items.append(
                HotspotCatalogItem(
                    id=item["id"],
                    name=item["name"],
                    coordinates=item["coordinates"],
                    description=item["description"],
                    sample_file=item["sample_file"],
                    has_local_sample=sample_path.is_file(),
                    inference_available=item["inference_available"],
                )
            )
        return items

    @staticmethod
    def _normalize_band(band: np.ndarray, valid_pixels: np.ndarray) -> np.ndarray:
        """Normalize band reflectance to 0-255 uint8 for preview visualization."""
        values = band.astype(np.float32, copy=False)
        finite = np.isfinite(values) & valid_pixels
        if not finite.any():
            return np.zeros(values.shape, dtype=np.uint8)
        low, high = float(values[finite].min()), float(values[finite].max())
        if high <= low:
            return np.zeros(values.shape, dtype=np.uint8)
        normalized = np.zeros(values.shape, dtype=np.float32)
        normalized[finite] = (values[finite] - low) / (high - low)
        return (np.clip(normalized, 0.0, 1.0) * 255).astype(np.uint8)

    @staticmethod
    def _encode_png(image: np.ndarray, mode: str) -> str:
        """Encode numpy array image to base64 PNG."""
        buffer = BytesIO()
        Image.fromarray(image, mode=mode).save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    @classmethod
    def _validate_and_read_dataset(
        cls,
        dataset: Any,
    ) -> tuple[np.ndarray, SatelliteRasterMetadata, np.ndarray]:
        """Validate raster structure, band count, dimensions, and numeric values."""
        if dataset.count != 11:
            raise InvalidSatelliteRasterError(
                f"Sentinel-2 MARIDA model requires exactly 11 spectral bands "
                f"(B1, B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12). Got {dataset.count} bands."
            )
        if dataset.width <= 0 or dataset.height <= 0:
            raise InvalidSatelliteRasterError(
                f"Invalid raster dimensions: width={dataset.width}, height={dataset.height}."
            )

        try:
            masked_bands = dataset.read(masked=True)
        except Exception as exc:
            raise InvalidSatelliteRasterError(f"Failed to read raster pixel data: {exc}") from exc

        if not np.issubdtype(masked_bands.dtype, np.number):
            raise InvalidSatelliteRasterError(
                f"Raster pixel data must be numeric. Found dtype: {masked_bands.dtype}"
            )

        bounds_list = [float(dataset.bounds.left), float(dataset.bounds.bottom),
                       float(dataset.bounds.right), float(dataset.bounds.top)] if dataset.bounds else None

        metadata = SatelliteRasterMetadata(
            driver=dataset.driver,
            width=dataset.width,
            height=dataset.height,
            count=dataset.count,
            nodata=float(dataset.nodata) if dataset.nodata is not None else None,
            crs=str(dataset.crs) if dataset.crs else None,
            bounds=bounds_list,
            transform=[float(value) for value in tuple(dataset.transform)[:6]],
            band_descriptions=list(dataset.descriptions),
            band_scales=[float(value) for value in dataset.scales],
            band_offsets=[float(value) for value in dataset.offsets],
            band_dtypes=list(dataset.dtypes),
            band_units=list(dataset.units),
        )
        valid_pixels = ~np.ma.getmaskarray(masked_bands).any(axis=0)
        bands = np.asarray(masked_bands.filled(np.nan), dtype=np.float32)
        scales = np.asarray(dataset.scales, dtype=np.float32)[:, None, None]
        offsets = np.asarray(dataset.offsets, dtype=np.float32)[:, None, None]
        if not np.isfinite(scales).all() or not np.isfinite(offsets).all():
            raise InvalidSatelliteRasterError("Raster band scales and offsets must be finite.")
        bands = bands * scales + offsets
        valid_pixels &= np.isfinite(bands).all(axis=0)
        if not valid_pixels.any():
            raise InvalidSatelliteRasterError("Raster data contains no valid numeric pixels.")
        return bands, metadata, valid_pixels

    @staticmethod
    def _classify_with_confidence(
        predicted_classes: np.ndarray,
        confidence: np.ndarray,
        valid_pixels: np.ndarray,
        threshold: float,
    ) -> _ConfidenceClassification:
        """Mask low-confidence and invalid pixels and summarize debris coverage."""
        if predicted_classes.shape != valid_pixels.shape or confidence.shape != valid_pixels.shape:
            raise ValueError("Predictions, confidence, and valid-pixel masks must have matching shapes.")
        if not np.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError("Confidence threshold must be between 0 and 1.")
        if not valid_pixels.any():
            raise ValueError("Cannot classify a raster without valid pixels.")
        if not np.isfinite(confidence[valid_pixels]).all():
            raise ValueError("Model returned non-finite confidence for valid raster pixels.")

        confident_pixels = valid_pixels & (confidence >= threshold)
        uncertain_pixels = valid_pixels & ~confident_pixels
        mask = np.full(valid_pixels.shape, INVALID_CLASS_ID, dtype=np.uint8)
        mask[uncertain_pixels] = UNCERTAIN_CLASS_ID
        mask[confident_pixels] = predicted_classes[confident_pixels].astype(np.uint8)

        total_pixels = int(valid_pixels.size)
        valid_pixel_count = int(valid_pixels.sum())
        confident_pixel_count = int(confident_pixels.sum())
        debris_pixel_count = int(((mask == 0) & confident_pixels).sum())
        excluded_pixel_count = total_pixels - confident_pixel_count
        return _ConfidenceClassification(
            mask=mask,
            confident_pixels=confident_pixels,
            uncertain_pixels=uncertain_pixels,
            average_confidence=float(confidence[valid_pixels].mean()),
            debris_pixel_count=debris_pixel_count,
            debris_coverage_percentage=(
                round(debris_pixel_count / confident_pixel_count * 100.0, 4)
                if confident_pixel_count
                else None
            ),
            excluded_pixel_count=excluded_pixel_count,
            excluded_pixel_percentage=round(excluded_pixel_count / total_pixels * 100.0, 4),
        )

    @staticmethod
    def _input_warnings(metadata: SatelliteRasterMetadata) -> List[str]:
        """Report input properties that prevent verification of model compatibility."""
        warnings: List[str] = []
        aliases = {
            "B1": {"B1", "B01", "BAND1", "BAND01"},
            "B2": {"B2", "B02", "BAND2", "BAND02"},
            "B3": {"B3", "B03", "BAND3", "BAND03"},
            "B4": {"B4", "B04", "BAND4", "BAND04"},
            "B5": {"B5", "B05", "BAND5", "BAND05"},
            "B6": {"B6", "B06", "BAND6", "BAND06"},
            "B7": {"B7", "B07", "BAND7", "BAND07"},
            "B8": {"B8", "B08", "BAND8", "BAND08"},
            "B8A": {"B8A", "BAND8A"},
            "B11": {"B11", "BAND11"},
            "B12": {"B12", "BAND12"},
        }
        descriptions = metadata.band_descriptions or []
        normalized_descriptions = [
            (description or "").strip().upper().replace(" ", "")
            for description in descriptions
        ]
        identified_bands = tuple(
            next((band for band in SENTINEL2_BAND_ORDER if value in aliases[band]), "")
            for value in normalized_descriptions
        )
        if identified_bands != SENTINEL2_BAND_ORDER:
            warnings.append(
                "The TIFF does not identify all bands in the expected order "
                "(B1, B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12). "
                "The analysis assumes this order; verify it against the source before relying on predictions."
            )
        units = metadata.band_units or []
        normalized_units = {(unit or "").strip().lower() for unit in units}
        if len(units) != len(SENTINEL2_BAND_ORDER) or not normalized_units or any(
            unit not in {"reflectance", "unitless", "dimensionless", "1"}
            for unit in normalized_units
        ):
            warnings.append(
                "The TIFF does not declare reflectance units for every band. The model assumes "
                "Sentinel-2 L2A surface reflectance; confirm the source calibration and scale/offset metadata."
            )
        data_types = metadata.band_dtypes or []
        if any(data_type not in {"float32", "float64"} for data_type in data_types):
            warnings.append(
                "The TIFF is not stored entirely as floating-point reflectance. Raster scales and offsets "
                "are applied, but confirm the resulting values match MARIDA training reflectance."
            )
        return warnings

    @classmethod
    def _execute_analysis(
        cls,
        bands: np.ndarray,
        meta: SatelliteRasterMetadata,
        site_info: Dict[str, Any],
        valid_pixels: np.ndarray,
    ) -> SatelliteAnalysisResponse:
        """Shared analysis engine: runs forward segmentation and builds structured result."""
        detector = cls.get_detector()

        # Sentinel-2 true-color preview: Band 4 (Red, idx 3), Band 3 (Green, idx 2), Band 2 (Blue, idx 1)
        preview_rgb = np.stack(
            [
                cls._normalize_band(bands[3], valid_pixels),
                cls._normalize_band(bands[2], valid_pixels),
                cls._normalize_band(bands[1], valid_pixels),
            ],
            axis=-1,
        )

        # Run U-Net inference and retain its per-pixel softmax confidence.
        image_tensor = torch.from_numpy(bands)
        try:
            predicted_classes, confidence = detector.predict_with_confidence(image_tensor)
            predicted_classes = predicted_classes.cpu().numpy()
            confidence = confidence.cpu().numpy()
        except ValueError as exc:
            raise RuntimeError("The U-Net rejected the validated raster tensor.") from exc
        if predicted_classes.shape != valid_pixels.shape:
            raise RuntimeError(
                f"U-Net returned a mask with shape {predicted_classes.shape}; expected {valid_pixels.shape}."
            )
        if np.any(predicted_classes < 0) or np.any(predicted_classes >= len(MARIDA_CLASSES)):
            raise RuntimeError("U-Net returned class IDs outside the configured MARIDA taxonomy.")

        classification = cls._classify_with_confidence(
            predicted_classes,
            confidence,
            valid_pixels,
            settings.SATELLITE_CONFIDENCE_THRESHOLD,
        )
        mask = classification.mask
        total_pixels = int(valid_pixels.size)
        valid_pixel_count = int(valid_pixels.sum())
        confident_pixel_count = int(classification.confident_pixels.sum())
        uncertain_pixel_count = int(classification.uncertain_pixels.sum())

        palette = np.zeros((INVALID_CLASS_ID + 1, 3), dtype=np.uint8)
        class_colors = np.asarray([
            [int(color[index:index + 2], 16) for index in (1, 3, 5)]
            for _, color in MARIDA_CLASSES
        ], dtype=np.uint8)
        palette[:len(MARIDA_CLASSES)] = class_colors
        palette[UNCERTAIN_CLASS_ID] = (148, 163, 184)
        class_rgb = palette[mask]
        class_rgb[~valid_pixels] = 0
        preview_rgb[~valid_pixels] = 0
        overlay_rgb = np.clip(
            preview_rgb.astype(np.float32) * 0.48 + class_rgb.astype(np.float32) * 0.52,
            0,
            255,
        ).astype(np.uint8)
        mask_rgb = class_rgb.astype(np.uint8)
        class_statistics = []
        class_definitions = [
            *[(class_id, name, color) for class_id, (name, color) in enumerate(MARIDA_CLASSES)],
            (UNCERTAIN_CLASS_ID, "Uncertain", "#94a3b8"),
            (INVALID_CLASS_ID, "Invalid / NoData", "#000000"),
        ]
        for class_id, class_name, color in class_definitions:
            pixel_count = int((mask == class_id).sum())
            class_statistics.append({
                "class_id": class_id,
                "class_name": class_name,
                "color": color,
                "pixel_count": pixel_count,
                "percentage": round((pixel_count / total_pixels) * 100.0, 4) if total_pixels else 0.0,
            })

        warnings = cls._input_warnings(meta)
        if confident_pixel_count == 0:
            warnings.append(
                "No valid pixels meet the configured confidence threshold; debris coverage is unavailable."
            )
        return SatelliteAnalysisResponse(
            id=site_info["id"],
            name=site_info["name"],
            image_name=site_info.get("image_name") or site_info.get("sample_file") or site_info["name"],
            coordinates=site_info["coordinates"],
            description=site_info.get("description", "Sentinel-2 GeoTIFF Analysis"),
            sample_file=site_info.get("sample_file"),
            debris_pixel_count=classification.debris_pixel_count,
            total_pixels=total_pixels,
            valid_pixel_count=valid_pixel_count,
            confident_pixel_count=confident_pixel_count,
            uncertain_pixel_count=uncertain_pixel_count,
            uncertain_pixel_percentage=round(uncertain_pixel_count / total_pixels * 100.0, 4),
            excluded_pixel_count=classification.excluded_pixel_count,
            excluded_pixel_percentage=classification.excluded_pixel_percentage,
            confidence_threshold=settings.SATELLITE_CONFIDENCE_THRESHOLD,
            average_confidence=round(classification.average_confidence, 4),
            debris_coverage_percentage=classification.debris_coverage_percentage,
            predicted_classes=[
                item["class_id"] for item in class_statistics
                if item["class_id"] < len(MARIDA_CLASSES) and item["pixel_count"] > 0
            ],
            class_statistics=class_statistics,
            preview_png_base64=cls._encode_png(preview_rgb, "RGB"),
            segmentation_mask_png_base64=cls._encode_png(mask_rgb, "RGB"),
            overlay_png_base64=cls._encode_png(overlay_rgb, "RGB"),
            segmentation_mask_geotiff_base64=cls._encode_geotiff_mask(mask, valid_pixels, meta),
            raster_metadata=meta,
            analysis_reliable=not warnings,
            warnings=warnings,
            status="warning" if warnings else "success",
        )

    @staticmethod
    def _encode_geotiff_mask(
        mask: np.ndarray,
        valid_pixels: np.ndarray,
        metadata: SatelliteRasterMetadata,
    ) -> str:
        """Encode class IDs as a one-band GeoTIFF with source CRS and affine transform."""
        if MemoryFile is None or Affine is None:
            raise SatelliteUnavailableError("Rasterio is required to preserve geospatial mask metadata.")
        if metadata.transform is None:
            raise InvalidSatelliteRasterError(
                "The source raster has no affine transform; a georeferenced mask cannot be created."
            )

        profile: Dict[str, Any] = {
            "driver": "GTiff",
            "width": metadata.width,
            "height": metadata.height,
            "count": 1,
            "dtype": "uint8",
            "nodata": 255,
            "compress": "deflate",
            "transform": Affine(*metadata.transform),
        }
        if metadata.crs is not None:
            profile["crs"] = metadata.crs
        output_mask = np.where(valid_pixels, mask, INVALID_CLASS_ID).astype(np.uint8)
        with MemoryFile() as memory_file:
            with memory_file.open(**profile) as dataset:
                dataset.write(output_mask, 1)
                dataset.set_band_description(1, "MARIDA class ID (254 = Uncertain, 255 = NoData)")
                dataset.update_tags(**{
                    f"class_{class_id}": class_name
                    for class_id, (class_name, _) in enumerate(MARIDA_CLASSES)
                })
                dataset.update_tags(class_254="Uncertain", class_255="NoData")
            encoded = memory_file.read()
        return base64.b64encode(encoded).decode("ascii")

    @classmethod
    def analyze_registered_hotspot(cls, hotspot_id: str) -> SatelliteAnalysisResponse:
        """Analyze a pre-registered coastal hotspot by ID."""
        if hotspot_id not in cls.CATALOG:
            raise KeyError(f"Unknown hotspot ID: '{hotspot_id}'. Available: {list(cls.CATALOG.keys())}")
        hotspot = cls.CATALOG[hotspot_id]
        if not hotspot["inference_available"]:
            raise InvalidSatelliteRasterError(
                f"Registered sample '{hotspot_id}' is not verified Sentinel-2 imagery. "
                "Upload an authentic 11-band Sentinel-2 L2A GeoTIFF instead."
            )
        if rasterio is None:
            raise SatelliteUnavailableError("Satellite analysis dependencies are unavailable; install rasterio to enable it.")

        sample_path = _BACKEND_ROOT / hotspot["sample_file"]
        if not sample_path.is_file():
            raise FileNotFoundError(f"Hotspot sample GeoTIFF not found: {sample_path}")

        try:
            with rasterio.open(sample_path) as dataset:
                bands, meta, valid_pixels = cls._validate_and_read_dataset(dataset)
        except Exception as exc:
            if isinstance(exc, (InvalidSatelliteRasterError, FileNotFoundError)):
                raise
            raise InvalidSatelliteRasterError(
                f"Error opening GeoTIFF file '{sample_path.name}': {exc}"
            ) from exc

        return cls._execute_analysis(bands, meta, hotspot, valid_pixels)

    @classmethod
    def analyze_geotiff_bytes(
        cls,
        file_bytes: bytes,
        site_name: Optional[str] = None,
        coordinates: Optional[List[float]] = None,
    ) -> SatelliteAnalysisResponse:
        """Analyze a user-uploaded Sentinel-2 GeoTIFF supplied as bytes."""
        if MemoryFile is None:
            raise SatelliteUnavailableError("Satellite analysis dependencies are unavailable; install rasterio to enable it.")
        if not file_bytes:
            raise InvalidSatelliteRasterError("Uploaded file payload is empty.")

        try:
            with MemoryFile(file_bytes) as mem_file:
                with mem_file.open() as dataset:
                    bands, meta, valid_pixels = cls._validate_and_read_dataset(dataset)
        except Exception as exc:
            if isinstance(exc, InvalidSatelliteRasterError):
                raise
            raise InvalidSatelliteRasterError(f"Invalid or unreadable GeoTIFF file: {exc}") from exc

        # Estimate centroid coordinates from GeoTIFF bounds if available and not supplied
        coords = coordinates or [0.0, 0.0]
        if coordinates is None and meta.bounds is not None:
            # If bounds look like lat/lon [-90..90, -180..180]
            lat_center = (meta.bounds[1] + meta.bounds[3]) / 2.0
            lon_center = (meta.bounds[0] + meta.bounds[2]) / 2.0
            if -90.0 <= lat_center <= 90.0 and -180.0 <= lon_center <= 180.0:
                coords = [round(lat_center, 4), round(lon_center, 4)]

        custom_site = {
            "id": "custom-upload",
            "name": site_name or "Custom Ingested Patch",
            "image_name": site_name or "uploaded-image.tif",
            "coordinates": coords,
            "description": "User-uploaded Sentinel-2 L2A 11-band GeoTIFF patch.",
            "sample_file": None,
        }
        return cls._execute_analysis(bands, meta, custom_site, valid_pixels)
