"""Validation gate tests use generated rasters only; none are registered as imagery."""

import base64
import hashlib
import json

import numpy as np
import pytest
import rasterio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from app.core.config import settings
from app.services.satellite_service import SatelliteService
from app.services.satellite_validation import EXPECTED_BANDS, validate_satellite_raster
from app.services.satellite_service import InvalidSatelliteRasterError


def make_raster(*, count=11, crs="EPSG:32616", transform=None, descriptions=True, band_order=None,
                units=None, scales=None, offsets=None, nodata=None, values=None):
    width = height = 10
    transform = transform or from_origin(500000, 4500000, 10, 10)
    array = values if values is not None else np.stack([
        np.full((height, width), i / 100 + 0.02, dtype=np.float32)
        + np.indices((height, width))[1] / 1000
        for i in range(count)
    ])
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", width=width, height=height, count=count, dtype=array.dtype,
                      crs=crs, transform=transform, nodata=nodata) as ds:
            ds.write(array)
            if descriptions and count == 11:
                for index, band in enumerate(band_order or EXPECTED_BANDS, 1):
                    ds.set_band_description(index, band)
            if units:
                for index, unit in enumerate(units, 1):
                    ds.set_band_unit(index, unit)
            if scales:
                ds.scales = scales
            if offsets:
                ds.offsets = offsets
        return mem.read()


def trusted_manifest(raster_bytes, monkeypatch, *, max_invalid=0.2, pixel_size=10.0,
                     stored_values="surface_reflectance", scales=None, offsets=None,
                     quantification_values=None, boa_add_offsets=None):
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(settings, "SATELLITE_PROVENANCE_PUBLIC_KEY", public_pem)
    payload = {
        "raster_sha256": hashlib.sha256(raster_bytes).hexdigest(),
        "source_product_id": "S2A_TEST_PRODUCT",
        "acquisition_date": "2024-05-02",
        "processing_level": "L2A",
        "processing_baseline": "TEST_BASELINE",
        "band_order": list(EXPECTED_BANDS),
        "stored_values": stored_values,
        "reflectance_units": "1",
        "calibration_method": "identity_reflectance" if stored_values == "surface_reflectance" else "sentinel_l2a_dn_metadata",
        "raster_scales": scales or [1.0] * 11,
        "raster_offsets": offsets or [0.0] * 11,
        "source_metadata_refs": ["test-only synthetic fixture metadata"],
        "pixel_size_m": pixel_size,
        "max_invalid_pixel_fraction": max_invalid,
    }
    if stored_values == "digital_numbers":
        payload["quantification_values"] = quantification_values or [10000.0] * 11
        payload["boa_add_offsets"] = boa_add_offsets or [0.0] * 11
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    envelope = {"payload": payload, "signature": base64.b64encode(private.sign(canonical)).decode()}
    return json.dumps(envelope)


def test_signed_independently_verified_test_input_is_eligible(monkeypatch):
    raster = make_raster()
    result, calibrated, valid = validate_satellite_raster(raster, trusted_manifest(raster, monkeypatch))
    assert result.compatibility_status == "VERIFIED_COMPATIBLE"
    assert result.inference_permitted is True
    assert result.verified_band_identities == list(EXPECTED_BANDS)
    assert result.source_provenance_status == "INDEPENDENTLY_VERIFIED"
    assert calibrated.shape == (11, 10, 10)
    assert valid.all()


def test_signed_digital_numbers_use_raster_scale_and_offset_exactly_once(monkeypatch):
    values = np.stack([np.full((10, 10), 1000 + i * 10, dtype=np.uint16)
                       + np.indices((10, 10), dtype=np.uint16)[1] for i in range(11)]).astype(np.uint16)
    raster = make_raster(values=values, units=["DN"] * 11,
                         scales=[0.0001] * 11, offsets=[0.0] * 11)
    manifest = trusted_manifest(raster, monkeypatch, stored_values="digital_numbers",
                                scales=[0.0001] * 11, offsets=[0.0] * 11,
                                quantification_values=[10000.0] * 11, boa_add_offsets=[0.0] * 11)
    result, calibrated, _ = validate_satellite_raster(raster, manifest)
    assert result.compatibility_status == "VERIFIED_COMPATIBLE"
    assert result.reflectance_calibration_status == "VERIFIED_DN_PRODUCT_METADATA"
    assert calibrated[0, 0, 0] == pytest.approx(0.1)


def test_l2a_boa_offset_is_applied_once_and_dn_zero_is_nodata(monkeypatch):
    values = np.stack([np.full((10, 10), 2000 + i * 10, dtype=np.uint16)
                       + np.indices((10, 10), dtype=np.uint16)[1] for i in range(11)]).astype(np.uint16)
    values[:, 0, 0] = 0
    scales = [0.0001] * 11
    effective_offsets = [-0.01] * 11
    raster = make_raster(values=values, units=["DN"] * 11)
    manifest = trusted_manifest(raster, monkeypatch, stored_values="digital_numbers",
                                scales=scales, offsets=effective_offsets,
                                quantification_values=[10000.0] * 11,
                                boa_add_offsets=[-100.0] * 11)
    result, calibrated, valid = validate_satellite_raster(raster, manifest)
    assert result.compatibility_status == "VERIFIED_COMPATIBLE"
    assert not valid[0, 0]
    assert result.invalid_pixel_percentage == pytest.approx(1.0)
    assert calibrated[0, 1, 0] == pytest.approx(0.19)


def test_wrong_band_count_is_incompatible():
    result, _, _ = validate_satellite_raster(make_raster(count=10, descriptions=False))
    assert result.compatibility_status == "INCOMPATIBLE"
    assert result.detected_band_count == 10
    assert not result.inference_permitted


def test_incorrect_band_order_is_incompatible():
    band_order = ("B2", "B1", *EXPECTED_BANDS[2:])
    result, _, _ = validate_satellite_raster(make_raster(band_order=band_order))
    assert result.compatibility_status == "INCOMPATIBLE"


def test_missing_band_descriptions_are_unverified():
    result, _, _ = validate_satellite_raster(make_raster(descriptions=False))
    assert result.compatibility_status == "DECLARED_UNVERIFIED"
    assert result.verified_band_identities is None


def test_missing_calibration_information_is_unverified():
    result, _, _ = validate_satellite_raster(make_raster(descriptions=False))
    assert result.reflectance_calibration_status == "UNKNOWN"
    assert result.source_provenance_status == "UNVERIFIED"


def test_contradictory_reflectance_units_are_incompatible():
    result, _, _ = validate_satellite_raster(make_raster(units=["meters"] * 11))
    assert result.compatibility_status == "INCOMPATIBLE"


def test_raster_scale_mismatch_with_signed_manifest_is_incompatible(monkeypatch):
    raster = make_raster(scales=[0.5] * 11)
    manifest = trusted_manifest(raster, monkeypatch)
    result, _, _ = validate_satellite_raster(raster, manifest)
    assert result.compatibility_status == "INCOMPATIBLE"


def test_raster_offset_mismatch_with_signed_manifest_is_incompatible(monkeypatch):
    raster = make_raster(offsets=[0.01] * 11)
    result, _, _ = validate_satellite_raster(raster, trusted_manifest(raster, monkeypatch))
    assert result.compatibility_status == "INCOMPATIBLE"


def test_surface_reflectance_cannot_be_scaled_a_second_time(monkeypatch):
    raster = make_raster(scales=[0.01] * 11)
    private_manifest = trusted_manifest(raster, monkeypatch, scales=[0.01] * 11)
    result, _, _ = validate_satellite_raster(raster, private_manifest)
    assert result.compatibility_status == "INCOMPATIBLE"
    assert "second time" in result.validation_errors[0]


def test_missing_crs_is_incompatible():
    result, _, _ = validate_satellite_raster(make_raster(crs=None))
    assert result.compatibility_status == "INCOMPATIBLE"


def test_impossible_geographic_transform_is_incompatible():
    raster = make_raster(crs="EPSG:4326", transform=from_origin(-0.2, 5.55, 10, 10))
    result, _, _ = validate_satellite_raster(raster)
    assert result.compatibility_status == "INCOMPATIBLE"


def test_raster_outside_selected_site_is_incompatible(monkeypatch):
    raster = make_raster()
    result, _, _ = validate_satellite_raster(
        raster, trusted_manifest(raster, monkeypatch), site_coordinates=[5.55, -0.20]
    )
    assert result.compatibility_status == "INCOMPATIBLE"
    assert "does not overlap" in result.validation_errors[0]


def test_infinite_pixels_are_rejected():
    values = np.stack([np.full((10, 10), 0.1 + i / 100, dtype=np.float32) for i in range(11)])
    values[0, 0, 0] = np.inf
    result, _, _ = validate_satellite_raster(make_raster(values=values))
    assert result.compatibility_status == "INCOMPATIBLE"
    assert "infinite" in result.validation_errors[0]


def test_nan_pixels_count_as_invalid_pixels():
    values = np.stack([np.full((10, 10), 0.1 + i / 100, dtype=np.float32)
                       + np.indices((10, 10))[1] / 1000 for i in range(11)])
    values[:, 0, 0] = np.nan
    result, _, valid = validate_satellite_raster(make_raster(values=values, nodata=np.nan))
    assert result.invalid_pixel_percentage == pytest.approx(1.0)
    assert valid.sum() == 99
    assert result.compatibility_status == "DECLARED_UNVERIFIED"


def test_product_policy_rejects_excessive_nodata(monkeypatch):
    values = np.stack([np.full((10, 10), 0.1 + i / 100, dtype=np.float32)
                       + np.indices((10, 10))[1] / 1000 for i in range(11)])
    values[:, :2, :] = np.nan
    raster = make_raster(values=values, nodata=np.nan)
    result, _, _ = validate_satellite_raster(raster, trusted_manifest(raster, monkeypatch, max_invalid=0.1))
    assert result.compatibility_status == "INCOMPATIBLE"
    assert result.invalid_pixel_percentage == pytest.approx(20.0)


def test_constant_spectral_band_is_incompatible():
    values = np.stack([np.full((10, 10), 0.1 + i / 100, dtype=np.float32) for i in range(11)])
    values[4] = 0.25
    result, _, _ = validate_satellite_raster(make_raster(values=values))
    assert result.compatibility_status == "INCOMPATIBLE"
    assert "constant" in result.validation_errors[0]


def test_corrupted_tiff_is_invalid():
    result, _, _ = validate_satellite_raster(b"not a tiff")
    assert result.compatibility_status == "INVALID"
    assert not result.inference_permitted


def test_untrusted_manifest_does_not_enable_inference(monkeypatch):
    raster = make_raster()
    manifest = trusted_manifest(raster, monkeypatch)
    monkeypatch.setattr(settings, "SATELLITE_PROVENANCE_PUBLIC_KEY", None)
    result, _, _ = validate_satellite_raster(raster, manifest)
    assert result.compatibility_status == "DECLARED_UNVERIFIED"
    assert not result.inference_permitted


def test_unsigned_user_manifest_cannot_enable_inference(monkeypatch):
    raster = make_raster()
    signed = json.loads(trusted_manifest(raster, monkeypatch))
    unsigned = json.dumps({"payload": signed["payload"]})
    result, _, _ = validate_satellite_raster(raster, unsigned)
    assert result.compatibility_status == "INVALID"
    assert not result.inference_permitted


def test_changing_raster_bytes_invalidates_old_signature(monkeypatch):
    raster = make_raster()
    manifest = trusted_manifest(raster, monkeypatch)
    changed = raster + b"\x00"
    result, _, _ = validate_satellite_raster(changed, manifest)
    assert result.compatibility_status == "DECLARED_UNVERIFIED"
    assert "does not match" in result.validation_errors[0]
    assert not result.inference_permitted


def test_changing_signed_manifest_field_invalidates_signature(monkeypatch):
    raster = make_raster()
    envelope = json.loads(trusted_manifest(raster, monkeypatch))
    envelope["payload"]["source_product_id"] = "ATTACKER-REPLACEMENT"
    result, _, _ = validate_satellite_raster(raster, json.dumps(envelope))
    assert result.compatibility_status == "DECLARED_UNVERIFIED"
    assert "signature" in result.validation_errors[0]
    assert not result.inference_permitted


def test_changing_signed_band_order_cannot_reach_inference(monkeypatch):
    raster = make_raster()
    envelope = json.loads(trusted_manifest(raster, monkeypatch))
    envelope["payload"]["band_order"][0] = "B2"
    result, _, _ = validate_satellite_raster(raster, json.dumps(envelope))
    assert result.compatibility_status != "VERIFIED_COMPATIBLE"
    assert not result.inference_permitted


def test_processing_level_must_be_l2a(monkeypatch):
    raster = make_raster()
    envelope = json.loads(trusted_manifest(raster, monkeypatch))
    envelope["payload"]["processing_level"] = "L1C"
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(settings, "SATELLITE_PROVENANCE_PUBLIC_KEY", public_pem)
    canonical = json.dumps(envelope["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    envelope["signature"] = base64.b64encode(private.sign(canonical)).decode()
    result, _, _ = validate_satellite_raster(raster, json.dumps(envelope))
    assert result.compatibility_status == "DECLARED_UNVERIFIED"
    assert not result.inference_permitted


def test_existing_catalog_samples_remain_unavailable():
    assert len(SatelliteService.CATALOG) == 4
    assert all(item["inference_available"] is False for item in SatelliteService.CATALOG.values())
    assert all(item["validation_status"] == "DECLARED_UNVERIFIED" for item in SatelliteService.CATALOG.values())


def test_every_registered_sample_is_rejected_before_inference(monkeypatch):
    monkeypatch.setattr(SatelliteService, "get_detector", lambda: pytest.fail("unverified catalog sample reached inference"))
    for site_id in SatelliteService.CATALOG:
        with pytest.raises(InvalidSatelliteRasterError):
            SatelliteService.analyze_registered_hotspot(site_id)


def test_analysis_service_stops_before_model_inference_for_unverified_patch(monkeypatch):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "marida" / "S2_12-12-20_16PCC_0.tif"
    monkeypatch.setattr(SatelliteService, "get_detector", lambda: pytest.fail("unverified raster reached inference"))
    with pytest.raises(InvalidSatelliteRasterError) as error:
        SatelliteService.analyze_geotiff_bytes(fixture.read_bytes())
    assert error.value.args[0]["compatibility_status"] == "DECLARED_UNVERIFIED"


def test_signed_compatible_fixture_completes_service_inference(monkeypatch):
    raster = make_raster()
    manifest = trusted_manifest(raster, monkeypatch)
    monkeypatch.setattr(SatelliteService, "_detector", None)
    result = SatelliteService.analyze_geotiff_bytes(
        raster,
        site_name="synthetic-validation-test.tif",
        provenance_manifest_json=manifest,
    )
    assert result.total_pixels == 100
    assert result.valid_pixel_count == 100
    assert result.raster_metadata.crs == "EPSG:32616"
    assert result.analysis_reliable is True
