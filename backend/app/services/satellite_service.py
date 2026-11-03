"""Satellite service for Sentinel-2 11-band MARIDA U-Net inference."""

from __future__ import annotations

import base64
from io import BytesIO
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from PIL import Image
try:
    import rasterio
    from rasterio.io import MemoryFile
except ModuleNotFoundError:
    rasterio = None
    MemoryFile = None
try:
    import torch
except ModuleNotFoundError:
    torch = None

from app.core.config import settings
try:
    from app.ml.satellite.detector import DebrisDetector
except ModuleNotFoundError:
    DebrisDetector = None
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


class SatelliteUnavailableError(RuntimeError):
    """Raised when satellite inference cannot run in the current environment."""


class SatelliteService:
    """Singleton service for MARIDA U-Net Sentinel-2 satellite analysis."""

    _detector: Optional[DebrisDetector] = None

    # Pre-registered verified coastal monitoring sites with Sentinel-2 L2A samples
    CATALOG: Dict[str, Dict[str, Any]] = {
        "accra-coast": {
            "id": "accra-coast",
            "name": "Accra Coast, Ghana",
            "coordinates": [5.55, -0.20],
            "description": "Verified MARIDA coastal monitoring site near Accra.",
            "sample_file": "samples/accra-coast.tif",
        },
        "gulf-of-honduras": {
            "id": "gulf-of-honduras",
            "name": "Gulf of Honduras",
            "coordinates": [15.80, -87.90],
            "description": "Verified MARIDA coastal monitoring site in the Gulf of Honduras.",
            "sample_file": "samples/gulf-of-honduras.tif",
        },
        "durban-harbor": {
            "id": "durban-harbor",
            "name": "Durban Harbor, South Africa",
            "coordinates": [-29.86, 31.02],
            "description": "Verified MARIDA coastal monitoring site near Durban Harbor.",
            "sample_file": "samples/durban-harbor.tif",
        },
        "coastal-demo-site": {
            "id": "coastal-demo-site",
            "name": "Coastal Demo Site",
            "coordinates": [12.91, 74.85],
            "description": "Verified MARIDA coastal monitoring demonstration site.",
            "sample_file": "samples/coastal-demo-site.tif",
        },
    }

    @classmethod
    def initialize(cls) -> None:
        """Load the U-Net model once during application startup."""
        if rasterio is None or torch is None or DebrisDetector is None:
            raise SatelliteUnavailableError(
                "Satellite analysis dependencies are unavailable; install rasterio and torch to enable it."
            )
        if cls._detector is None:
            model_path = _BACKEND_ROOT / settings.SATELLITE_MODEL_PATH
            if not model_path.is_file():
                raise SatelliteUnavailableError(
                    f"Satellite model checkpoint is unavailable at {model_path}."
                )
            logger.info(f"Initializing SatelliteService with model at {model_path}...")
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
                )
            except (EOFError, OSError, RuntimeError, TypeError, ValueError, pickle.UnpicklingError) as exc:
                raise SatelliteUnavailableError(
                    f"Satellite model could not be loaded: {exc}"
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
                )
            )
        return items

    @staticmethod
    def _normalize_band(band: np.ndarray) -> np.ndarray:
        """Normalize band reflectance to 0-255 uint8 for preview visualization."""
        values = band.astype(np.float32, copy=False)
        finite = np.isfinite(values)
        if not finite.any():
            return np.zeros(values.shape, dtype=np.uint8)
        low, high = float(values[finite].min()), float(values[finite].max())
        if high <= low:
            return np.zeros(values.shape, dtype=np.uint8)
        normalized = (values - low) / (high - low)
        return (np.clip(np.nan_to_num(normalized), 0.0, 1.0) * 255).astype(np.uint8)

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
            raise ValueError(
                f"Sentinel-2 MARIDA model requires exactly 11 spectral bands "
                f"(B1, B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12). Got {dataset.count} bands."
            )
        if dataset.width <= 0 or dataset.height <= 0:
            raise ValueError(f"Invalid raster dimensions: width={dataset.width}, height={dataset.height}.")

        try:
            masked_bands = dataset.read(masked=True)
        except Exception as exc:
            raise ValueError(f"Failed to read raster pixel data: {exc}") from exc

        if not np.issubdtype(masked_bands.dtype, np.number):
            raise ValueError(f"Raster pixel data must be numeric. Found dtype: {masked_bands.dtype}")

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
        )
        valid_pixels = ~np.ma.getmaskarray(masked_bands).any(axis=0)
        bands = np.asarray(masked_bands.filled(np.nan), dtype=np.float32)
        valid_pixels &= np.isfinite(bands).all(axis=0)
        if not valid_pixels.any():
            raise ValueError("Raster data contains no valid numeric pixels.")
        bands[:, ~valid_pixels] = 0.0
        return bands, metadata, valid_pixels

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
            [cls._normalize_band(bands[3]), cls._normalize_band(bands[2]), cls._normalize_band(bands[1])],
            axis=-1,
        )

        # Run U-Net CPU inference
        image_tensor = torch.from_numpy(bands)
        mask = detector.predict(image_tensor).numpy()

        # Class 0 = Marine Debris in MARIDA taxonomy
        debris_mask = (mask == 0) & valid_pixels
        total_pixels = int(valid_pixels.sum())
        debris_pixels = int(debris_mask.sum())
        coverage_pct = round((debris_pixels / total_pixels) * 100.0, 4) if total_pixels > 0 else 0.0

        # Fixed MARIDA palette: the mask remains a class-index raster while the
        # overlay blends every predicted class over the true-color preview.
        palette = np.asarray([
            [int(color[index:index + 2], 16) for index in (1, 3, 5)]
            for _, color in MARIDA_CLASSES
        ], dtype=np.uint8)
        class_rgb = palette[mask]
        overlay_rgb = np.clip(
            preview_rgb.astype(np.float32) * 0.48 + class_rgb.astype(np.float32) * 0.52,
            0,
            255,
        ).astype(np.uint8)
        mask_rgb = class_rgb.astype(np.uint8)
        class_statistics = []
        for class_id, (class_name, color) in enumerate(MARIDA_CLASSES):
            pixel_count = int((mask == class_id).sum())
            class_statistics.append({
                "class_id": class_id,
                "class_name": class_name,
                "color": color,
                "pixel_count": pixel_count,
                "percentage": round((pixel_count / total_pixels) * 100.0, 4) if total_pixels else 0.0,
            })

        return SatelliteAnalysisResponse(
            id=site_info["id"],
            name=site_info["name"],
            image_name=site_info.get("image_name") or site_info.get("sample_file") or site_info["name"],
            coordinates=site_info["coordinates"],
            description=site_info.get("description", "Sentinel-2 GeoTIFF Analysis"),
            sample_file=site_info.get("sample_file"),
            debris_pixel_count=debris_pixels,
            total_pixels=total_pixels,
            debris_coverage_percentage=coverage_pct,
            predicted_classes=[item["class_id"] for item in class_statistics if item["pixel_count"] > 0],
            class_statistics=class_statistics,
            preview_png_base64=cls._encode_png(preview_rgb, "RGB"),
            segmentation_mask_png_base64=cls._encode_png(mask_rgb, "RGB"),
            overlay_png_base64=cls._encode_png(overlay_rgb, "RGB"),
            raster_metadata=meta,
            status="success",
        )

    @classmethod
    def analyze_registered_hotspot(cls, hotspot_id: str) -> SatelliteAnalysisResponse:
        """Analyze a pre-registered coastal hotspot by ID."""
        if hotspot_id not in cls.CATALOG:
            raise KeyError(f"Unknown hotspot ID: '{hotspot_id}'. Available: {list(cls.CATALOG.keys())}")
        if rasterio is None:
            raise SatelliteUnavailableError("Satellite analysis dependencies are unavailable; install rasterio to enable it.")

        hotspot = cls.CATALOG[hotspot_id]
        sample_path = _BACKEND_ROOT / hotspot["sample_file"]
        if not sample_path.is_file():
            raise FileNotFoundError(f"Hotspot sample GeoTIFF not found: {sample_path}")

        try:
            with rasterio.open(sample_path) as dataset:
                bands, meta, valid_pixels = cls._validate_and_read_dataset(dataset)
        except Exception as exc:
            if isinstance(exc, (ValueError, FileNotFoundError)):
                raise
            raise ValueError(f"Error opening GeoTIFF file '{sample_path.name}': {exc}") from exc

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
            raise ValueError("Uploaded file payload is empty.")

        try:
            with MemoryFile(file_bytes) as mem_file:
                with mem_file.open() as dataset:
                    bands, meta, valid_pixels = cls._validate_and_read_dataset(dataset)
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Invalid or unreadable GeoTIFF file: {exc}") from exc

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
