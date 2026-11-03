"""Tests for Sentinel-2 MARIDA U-Net satellite analysis service and API."""

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.satellite_service import SatelliteService, rasterio, torch

SAMPLE_TIF = Path(__file__).resolve().parents[1] / "samples" / "accra-coast.tif"
SATELLITE_AVAILABLE = rasterio is not None and torch is not None


@pytest.fixture(scope="module")
def client(authenticated_app):
    with TestClient(authenticated_app) as test_client:
        yield test_client


def test_satellite_catalog(client):
    response = client.get("/api/satellite/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog) >= 4
    accra = next((item for item in catalog if item["id"] == "accra-coast"), None)
    assert accra is not None
    assert accra["name"] == "Accra Coast, Ghana"
    assert len(accra["coordinates"]) == 2
    assert accra["has_local_sample"] is True


def test_analyze_registered_hotspot_via_post(client):
    response = client.post("/api/satellite/analyze", data={"hotspot_id": "accra-coast"})
    if not SATELLITE_AVAILABLE:
        assert response.status_code == 503
        return
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "accra-coast"
    assert data["total_pixels"] == 256 * 256
    assert data["debris_pixel_count"] >= 0
    assert 0.0 <= data["debris_coverage_percentage"] <= 100.0
    assert data["image_name"] == "samples/accra-coast.tif"
    assert len(data["class_statistics"]) == 11
    assert sum(item["pixel_count"] for item in data["class_statistics"]) == data["total_pixels"]
    assert sum(item["class_id"] == 0 and item["class_name"] == "Marine Debris" for item in data["class_statistics"]) == 1
    assert len(data["segmentation_mask_png_base64"]) > 100
    assert len(data["preview_png_base64"]) > 100
    assert len(data["overlay_png_base64"]) > 100
    assert data["raster_metadata"]["count"] == 11


def test_analyze_registered_hotspot_by_id_endpoint(client):
    response = client.get("/api/satellite/hotspots/accra-coast/analyze")
    if not SATELLITE_AVAILABLE:
        assert response.status_code == 503
        return
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "accra-coast"
    assert data["total_pixels"] == 65536


def test_analyze_uploaded_geotiff(client):
    assert SAMPLE_TIF.is_file(), f"Sample GeoTIFF not found at {SAMPLE_TIF}"
    with open(SAMPLE_TIF, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/satellite/analyze",
        files={"file": ("accra-upload.tif", file_bytes, "image/tiff")},
    )
    if not SATELLITE_AVAILABLE:
        assert response.status_code == 503
        return
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "custom-upload"
    assert data["total_pixels"] == 256 * 256
    assert data["debris_pixel_count"] >= 0
    assert len(data["class_statistics"]) == 11
    assert sum(item["pixel_count"] for item in data["class_statistics"]) == data["total_pixels"]
    assert len(data["segmentation_mask_png_base64"]) > 100
    assert data["raster_metadata"]["count"] == 11
    assert data["preview_png_base64"]
    assert data["overlay_png_base64"]


def test_analyze_unknown_hotspot_returns_404(client):
    response = client.post("/api/satellite/analyze", data={"hotspot_id": "nonexistent-site"})
    assert response.status_code == 404


def test_analyze_empty_request_returns_422(client):
    response = client.post("/api/satellite/analyze")
    assert response.status_code == 422


def test_analyze_invalid_file_returns_422(client):
    fake_bytes = b"this is not a valid GeoTIFF file"
    response = client.post(
        "/api/satellite/analyze",
        files={"file": ("fake.tif", fake_bytes, "image/tiff")},
    )
    if not SATELLITE_AVAILABLE:
        assert response.status_code == 503
        return
    assert response.status_code == 422
    assert "Invalid or unreadable GeoTIFF" in response.json()["error"]["message"]


def test_analyze_rejects_non_geotiff_extension(client):
    response = client.post(
        "/api/satellite/analyze",
        files={"file": ("image.png", b"fake", "image/png")},
    )
    assert response.status_code == 422
    assert "must be a .tif or .tiff" in response.json()["error"]["message"]
