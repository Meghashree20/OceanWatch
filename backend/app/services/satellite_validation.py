"""Strict, pre-inference validation for Sentinel-2 inputs to the MARIDA model."""

from __future__ import annotations

import base64
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Optional, Sequence

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.io import MemoryFile

from app.core.config import settings

EXPECTED_BANDS = ("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12")
VALIDATION_STATUSES = {"VERIFIED_COMPATIBLE", "DECLARED_UNVERIFIED", "INCOMPATIBLE", "INVALID"}


@dataclass
class SatelliteValidationResult:
    compatibility_status: str
    validation_warnings: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    detected_band_count: Optional[int] = None
    verified_band_identities: Optional[list[str]] = None
    crs: Optional[str] = None
    spatial_resolution_m: Optional[float] = None
    geographic_bounds: Optional[list[float]] = None
    reflectance_calibration_status: str = "UNKNOWN"
    source_provenance_status: str = "UNVERIFIED"
    invalid_pixel_percentage: Optional[float] = None
    inference_permitted: bool = False
    raster_metadata: Optional[dict[str, Any]] = None
    band_statistics: list[dict[str, Optional[float]]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _failure(status: str, message: str, **values: Any) -> SatelliteValidationResult:
    return SatelliteValidationResult(
        compatibility_status=status,
        validation_errors=[message],
        **values,
    )


def _parse_manifest(raw: Optional[str]) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    if not raw:
        return None, None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, "Provenance manifest is not valid JSON."
    if not isinstance(value, dict) or not isinstance(value.get("payload"), dict) or not isinstance(value.get("signature"), str):
        return None, "Manifest must contain a payload object and a signature."
    return value, None


def _verify_manifest(manifest: dict[str, Any], raster_bytes: bytes) -> tuple[bool, str, Optional[dict[str, Any]]]:
    public_key_pem = settings.SATELLITE_PROVENANCE_PUBLIC_KEY
    payload = manifest["payload"]
    if not public_key_pem:
        return False, "No server trust key is configured for independent provenance verification.", payload
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        if not isinstance(key, Ed25519PublicKey):
            return False, "Configured provenance trust key is not an Ed25519 key.", payload
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        key.verify(base64.b64decode(manifest["signature"], validate=True), canonical)
    except Exception:
        return False, "Provenance signature is not trusted or is invalid.", payload
    digest = hashlib.sha256(raster_bytes).hexdigest()
    if payload.get("raster_sha256") != digest:
        return False, "Signed provenance manifest does not match this raster file.", payload
    required = (
        "source_product_id", "acquisition_date", "processing_level", "processing_baseline", "band_order",
        "stored_values", "reflectance_units", "raster_scales", "raster_offsets",
        "calibration_method", "source_metadata_refs", "pixel_size_m",
    )
    if any(key not in payload for key in required):
        return False, "Signed provenance manifest is missing required source or calibration fields.", payload
    try:
        date.fromisoformat(payload["acquisition_date"])
    except (TypeError, ValueError):
        return False, "Manifest acquisition_date must use ISO format YYYY-MM-DD.", payload
    if payload.get("processing_level") != "L2A":
        return False, "Manifest processing level must identify Sentinel-2 L2A.", payload
    if not isinstance(payload.get("source_product_id"), str) or not payload["source_product_id"].strip():
        return False, "Manifest must identify a non-empty Sentinel-2 source product.", payload
    if not isinstance(payload.get("processing_baseline"), str) or not payload["processing_baseline"].strip():
        return False, "Manifest must preserve the Sentinel-2 processing baseline.", payload
    if payload.get("band_order") != list(EXPECTED_BANDS):
        return False, "Signed manifest band order does not match the MARIDA model input order.", payload
    if payload.get("stored_values") not in {"surface_reflectance", "digital_numbers"} or payload.get("reflectance_units") not in {"1", "unitless", "reflectance"}:
        return False, "Manifest must identify source values as digital numbers or calibrated surface reflectance.", payload
    expected_method = "identity_reflectance" if payload.get("stored_values") == "surface_reflectance" else "sentinel_l2a_dn_metadata"
    if payload.get("calibration_method") != expected_method:
        return False, "Manifest calibration method does not match the declared stored values.", payload
    calibration_fields = ["raster_scales", "raster_offsets"]
    if payload.get("stored_values") == "digital_numbers":
        calibration_fields += ["quantification_values", "boa_add_offsets"]
    for field_name in calibration_fields:
        values = payload.get(field_name)
        if (not isinstance(values, list) or len(values) != len(EXPECTED_BANDS)
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values)):
            return False, f"Manifest {field_name} must contain 11 finite calibration values.", payload
    if payload.get("stored_values") == "digital_numbers":
        qvalues = np.asarray(payload["quantification_values"], dtype=np.float64)
        offsets = np.asarray(payload["boa_add_offsets"], dtype=np.float64)
        scales = np.asarray(payload["raster_scales"], dtype=np.float64)
        effective_offsets = np.asarray(payload["raster_offsets"], dtype=np.float64)
        if np.any(qvalues <= 0) or not np.allclose(scales, 1.0 / qvalues, rtol=1e-12, atol=0.0) or not np.allclose(effective_offsets, offsets / qvalues, rtol=1e-12, atol=0.0):
            return False, "Manifest DN scale/offset does not match the Sentinel-2 L2A quantification and BOA offset metadata.", payload
    if (not isinstance(payload.get("source_metadata_refs"), list) or not payload["source_metadata_refs"]
            or any(not isinstance(item, str) or not item.strip() for item in payload["source_metadata_refs"])):
        return False, "Manifest must reference the original product metadata used to verify provenance.", payload
    if (isinstance(payload.get("pixel_size_m"), bool) or not isinstance(payload.get("pixel_size_m"), (int, float))
            or not math.isfinite(payload["pixel_size_m"]) or payload["pixel_size_m"] <= 0):
        return False, "Manifest pixel_size_m must be a positive finite product resolution.", payload
    return True, "Signed provenance and raster hash verified.", payload


def _resolution_m(dataset: Any) -> Optional[float]:
    if dataset.crs is None:
        return None
    crs = CRS.from_user_input(dataset.crs)
    xres = math.hypot(dataset.transform.a, dataset.transform.d)
    yres = math.hypot(dataset.transform.b, dataset.transform.e)
    if crs.is_geographic:
        center_lat = dataset.bounds.bottom + (dataset.bounds.top - dataset.bounds.bottom) / 2
        meters_per_degree_lat = 111132.0
        meters_per_degree_lon = 111320.0 * math.cos(math.radians(center_lat))
        return (xres * meters_per_degree_lon + yres * meters_per_degree_lat) / 2
    axes = crs.axis_info
    unit_factor = axes[0].unit_conversion_factor if axes and axes[0].unit_conversion_factor else 1.0
    return (xres + yres) * unit_factor / 2


def validate_satellite_raster(
    raster_bytes: bytes,
    provenance_manifest_json: Optional[str] = None,
    site_coordinates: Optional[Sequence[float]] = None,
) -> tuple[SatelliteValidationResult, Optional[np.ndarray], Optional[np.ndarray]]:
    """Validate a raster and return calibrated channels and valid-pixel mask when readable."""
    if not raster_bytes:
        return _failure("INVALID", "Raster file is empty."), None, None
    manifest, manifest_error = _parse_manifest(provenance_manifest_json)
    if manifest_error:
        return _failure("INVALID", manifest_error), None, None
    try:
        memory_file = MemoryFile(raster_bytes)
        with memory_file.open() as ds:
            if ds.driver != "GTiff":
                return _failure("INVALID", "Input is readable but is not a GeoTIFF.", detected_band_count=ds.count), None, None
            count = ds.count
            crs = str(ds.crs) if ds.crs else None
            basic = dict(detected_band_count=count, crs=crs)
            if count != len(EXPECTED_BANDS):
                return _failure("INCOMPATIBLE", f"Expected 11 Sentinel-2 model channels; found {count}.", **basic), None, None
            if ds.width <= 0 or ds.height <= 0:
                return _failure("INVALID", "Raster has empty dimensions.", **basic), None, None
            if ds.crs is None:
                return _failure("INCOMPATIBLE", "A valid CRS is required for geospatial validation.", **basic), None, None
            try:
                CRS.from_user_input(ds.crs)
                transform = ds.transform
                if not all(math.isfinite(value) for value in tuple(transform)[:6]) or abs(transform.a * transform.e - transform.b * transform.d) < 1e-12:
                    raise ValueError("invalid affine transform")
                geographic_bounds = list(Transformer.from_crs(ds.crs, "EPSG:4326", always_xy=True).transform_bounds(*ds.bounds, densify_pts=21))
                left, bottom, right, top = geographic_bounds
                if not all(math.isfinite(value) for value in geographic_bounds) or left < -180 or right > 180 or bottom < -90 or top > 90 or left >= right or bottom >= top:
                    raise ValueError("raster footprint is outside valid geographic bounds")
            except Exception:
                return _failure("INCOMPATIBLE", "CRS, affine transform, or geographic footprint is invalid or impossible.", **basic), None, None
            resolution = _resolution_m(ds)
            profile = {
                **basic,
                "spatial_resolution_m": resolution,
                "geographic_bounds": geographic_bounds,
                "raster_metadata": {
                    "width": ds.width, "height": ds.height, "dtypes": list(ds.dtypes),
                    "nodata": ds.nodata, "scales": list(ds.scales), "offsets": list(ds.offsets),
                    "units": list(ds.units), "descriptions": list(ds.descriptions),
                    "transform": list(tuple(ds.transform)[:6]),
                },
            }
            unsupported = [dtype for dtype in ds.dtypes if dtype not in {"uint16", "int16", "float32", "float64"}]
            if unsupported:
                return _failure("INCOMPATIBLE", f"Unsupported band data types: {', '.join(unsupported)}.", **profile), None, None
            payload = manifest["payload"] if manifest else None
            claimed_order = payload.get("band_order") if payload else None
            if not claimed_order:
                descriptions = [str(item or "").strip().upper().replace(" ", "") for item in ds.descriptions]
                aliases = [{band, band.replace("B", "B0", 1)} for band in EXPECTED_BANDS]
                claimed_order = [next((band for band, names in zip(EXPECTED_BANDS, aliases) if description in names), None) for description in descriptions]
            identities = list(claimed_order) if claimed_order else None
            identity_issue: Optional[tuple[str, str]] = None
            if identities != list(EXPECTED_BANDS):
                identity_status = "INCOMPATIBLE" if identities and all(identities) else "DECLARED_UNVERIFIED"
                msg = "Band identities are missing; 11 band positions alone do not establish Sentinel-2 channel order." if identity_status == "DECLARED_UNVERIFIED" else "Band identities or order do not match the required Sentinel-2 sequence."
                identity_issue = (identity_status, msg)
            declared_verified = False
            provenance_message = "No independently verifiable provenance manifest was supplied."
            if manifest:
                declared_verified, provenance_message, payload = _verify_manifest(manifest, raster_bytes)
            profile["verified_band_identities"] = identities if declared_verified else None
            profile["source_provenance_status"] = "INDEPENDENTLY_VERIFIED" if declared_verified else "UNVERIFIED"
            raster_scales = np.asarray(ds.scales, dtype=np.float64)
            raster_offsets = np.asarray(ds.offsets, dtype=np.float64)
            if not np.isfinite(raster_scales).all() or not np.isfinite(raster_offsets).all():
                return _failure("INVALID", "Raster contains non-finite scale or offset calibration.", **profile), None, None
            scales, offsets = raster_scales, raster_offsets
            if declared_verified:
                manifest_scales = np.asarray(payload["raster_scales"], dtype=np.float64)
                manifest_offsets = np.asarray(payload["raster_offsets"], dtype=np.float64)
                if payload.get("stored_values") == "surface_reflectance":
                    if not np.all(manifest_scales == 1) or not np.all(manifest_offsets == 0):
                        return _failure("INCOMPATIBLE", "Surface-reflectance inputs must not be scaled a second time.", **profile), None, None
                    if not np.all(raster_scales == 1) or not np.all(raster_offsets == 0):
                        return _failure("INCOMPATIBLE", "Surface-reflectance raster tags request an additional scale or offset.", **profile), None, None
                else:
                    if any(dtype != "uint16" for dtype in ds.dtypes):
                        return _failure("INCOMPATIBLE", "Sentinel-2 L2A digital-number inputs must use UInt16 bands.", **profile), None, None
                    raster_tags_are_identity = np.all(raster_scales == 1) and np.all(raster_offsets == 0)
                    if not raster_tags_are_identity and (not np.array_equal(raster_scales, manifest_scales) or not np.array_equal(raster_offsets, manifest_offsets)):
                        return _failure("INCOMPATIBLE", "Signed product calibration contradicts the raster scale/offset tags.", **profile), None, None
                    scales, offsets = manifest_scales, manifest_offsets
            descriptions = [str(value or "").strip().upper().replace(" ", "") for value in ds.descriptions]
            if any(descriptions) and descriptions != list(EXPECTED_BANDS):
                return _failure("INCOMPATIBLE", "Raster band descriptions contradict the required Sentinel-2 band order.", **profile), None, None
            declared_units = [str(value or "").strip().lower() for value in ds.units]
            accepted_units = {"1", "unitless", "reflectance", "dimensionless"}
            if declared_verified and payload.get("stored_values") == "digital_numbers":
                accepted_units = {"dn", "digital number", "digital numbers"}
            if any(declared_units) and any(value not in accepted_units for value in declared_units):
                return _failure("INCOMPATIBLE", "Raster band units contradict the signed input calibration declaration.", **profile), None, None
            raw = ds.read(masked=True)
            data = np.asarray(raw.data, dtype=np.float64).copy()
            raster_mask = np.ma.getmaskarray(raw).copy()
            if declared_verified and payload.get("stored_values") == "digital_numbers":
                # Sentinel-2 L2A product metadata reserves DN=0 as NoData.
                raster_mask |= data == 0
            data[raster_mask] = np.nan
            if np.isinf(data).any():
                return _failure("INCOMPATIBLE", "Raster contains infinite pixel values.", **profile), None, None
            calibrated = data * scales[:, None, None] + offsets[:, None, None]
            valid = ~raster_mask.any(axis=0) & np.isfinite(calibrated).all(axis=0)
            invalid_percentage = 100.0 * (1 - float(valid.mean()))
            stats = []
            constant_bands = []
            for index, band in enumerate(calibrated):
                values = band[np.isfinite(band)]
                stats.append({"minimum": float(values.min()) if values.size else None, "maximum": float(values.max()) if values.size else None, "mean": float(values.mean()) if values.size else None, "standard_deviation": float(values.std()) if values.size else None})
                if values.size and float(values.min()) == float(values.max()):
                    constant_bands.append(index + 1)
            profile["invalid_pixel_percentage"] = invalid_percentage
            profile["band_statistics"] = stats
            if constant_bands:
                return _failure("INCOMPATIBLE", f"Band(s) {', '.join(map(str, constant_bands))} are constant and contain no spectral variation.", **profile), None, None
            if not valid.any():
                return _failure("INVALID", "Raster contains no valid pixels.", **profile), None, None
            if payload and declared_verified:
                max_invalid = payload.get("max_invalid_pixel_fraction")
                if not isinstance(max_invalid, (int, float)) or not 0 <= max_invalid <= 1:
                    return _failure("INCOMPATIBLE", "Trusted manifest must specify a product-specific invalid-pixel fraction limit.", **profile), None, None
                if 1 - float(valid.mean()) > max_invalid:
                    return _failure("INCOMPATIBLE", "Raster invalid-pixel fraction exceeds the trusted product policy.", **profile), None, None
                expected_resolution = payload.get("pixel_size_m")
                if not isinstance(expected_resolution, (int, float)) or resolution is None or not math.isclose(resolution, expected_resolution, rel_tol=0.02):
                    return _failure("INCOMPATIBLE", "Raster spatial resolution does not match the trusted product manifest.", **profile), None, None
            if site_coordinates is not None:
                lat, lon = float(site_coordinates[0]), float(site_coordinates[1])
                if not (bottom <= lat <= top and left <= lon <= right):
                    return _failure("INCOMPATIBLE", "Raster footprint does not overlap the selected monitoring location.", **profile), None, None
            if identity_issue:
                return _failure(identity_issue[0], identity_issue[1], **profile), calibrated.astype(np.float32), valid
            if not declared_verified:
                profile["reflectance_calibration_status"] = "DECLARED_UNVERIFIED" if payload else "UNKNOWN"
                return _failure("DECLARED_UNVERIFIED", provenance_message, **profile), calibrated.astype(np.float32), valid
            profile["reflectance_calibration_status"] = "VERIFIED_DN_PRODUCT_METADATA" if payload.get("stored_values") == "digital_numbers" else "VERIFIED_REFLECTANCE_IDENTITY"
            profile["inference_permitted"] = True
            return SatelliteValidationResult(compatibility_status="VERIFIED_COMPATIBLE", **profile), calibrated.astype(np.float32), valid
    except Exception as exc:
        return _failure("INVALID", f"GeoTIFF is corrupted or unreadable: {type(exc).__name__}."), None, None
