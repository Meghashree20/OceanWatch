"""Tests for Sentinel-2 MARIDA U-Net satellite analysis service and API."""

from pathlib import Path
import base64

import numpy as np
import pytest
import rasterio
import torch
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from starlette.testclient import TestClient

from app.main import app
from app.ml.satellite.detector import DebrisDetector
from app.ml.satellite.unet import UNet
from app.schemas.satellite import SatelliteRasterMetadata
from app.services.satellite_service import SatelliteService

SAMPLE_TIF = Path(__file__).resolve().parents[1] / "samples" / "accra-coast.tif"
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "model.pth"
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
    assert response.status_code == 503
    assert "Checkpoint metadata is missing" in response.json()["error"]["message"]


def test_analyze_registered_hotspot_by_id_endpoint(client):
    response = client.get("/api/satellite/hotspots/accra-coast/analyze")
    assert response.status_code == 503
    assert "Checkpoint metadata is missing" in response.json()["error"]["message"]


def test_analyze_uploaded_geotiff(client):
    assert SAMPLE_TIF.is_file(), f"Sample GeoTIFF not found at {SAMPLE_TIF}"
    with open(SAMPLE_TIF, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/satellite/analyze",
        files={"file": ("accra-upload.tif", file_bytes, "image/tiff")},
    )
    assert response.status_code == 503
    assert "Checkpoint metadata is missing" in response.json()["error"]["message"]


def test_analyze_unknown_hotspot_returns_404(client):
    response = client.post("/api/satellite/analyze", data={"hotspot_id": "nonexistent-site"})
    assert response.status_code == 404


def test_analyze_empty_request_returns_422(client):
    response = client.post("/api/satellite/analyze")
    assert response.status_code == 422


def test_analyze_invalid_json_returns_422(client):
    response = client.post(
        "/api/satellite/analyze",
        content="{invalid",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert "valid JSON" in response.json()["error"]["message"]


def test_analyze_invalid_file_returns_422(client):
    fake_bytes = b"this is not a valid GeoTIFF file"
    response = client.post(
        "/api/satellite/analyze",
        files={"file": ("fake.tif", fake_bytes, "image/tiff")},
    )
    assert response.status_code == 422
    assert "Invalid or unreadable GeoTIFF" in response.json()["error"]["message"]


def test_analyze_rejects_non_geotiff_extension(client):
    response = client.post(
        "/api/satellite/analyze",
        files={"file": ("image.png", b"fake", "image/png")},
    )
    assert response.status_code == 422
    assert "must be a .tif or .tiff" in response.json()["error"]["message"]


def test_checkpoint_is_architecture_compatible_but_lacks_verifiable_provenance():
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
    model = UNet(input_bands=11, output_classes=11, hidden_channels=16)
    model.load_state_dict(checkpoint, strict=True)

    with rasterio.open(SAMPLE_TIF) as dataset:
        image = torch.from_numpy(dataset.read().astype(np.float32))
    model.eval()
    with torch.inference_mode():
        logits = model(image.unsqueeze(0))
        predicted_mask = logits.argmax(dim=1)

    assert tuple(logits.shape) == (1, 11, 256, 256)
    assert tuple(predicted_mask.shape) == (1, 256, 256)
    assert int(predicted_mask.min()) >= 0
    assert int(predicted_mask.max()) < 11
    with pytest.raises(ValueError, match="Checkpoint metadata is missing"):
        DebrisDetector(
            model_path=MODEL_PATH,
            class_names=[
                "Marine Debris", "Dense Sargassum", "Sparse Sargassum",
                "Natural Organic Material", "Ship", "Clouds", "Marine Water",
                "Sediment-Laden Water", "Foam", "Turbid Water", "Shallow Water",
            ],
            band_order=["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"],
        )


def test_raster_read_preserves_transform_and_masks_nodata():
    transform = from_origin(12.5, 23.5, 10, 10)
    values = np.ones((11, 3, 4), dtype=np.float32)
    values[:, 0, 0] = -9999
    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            width=4,
            height=3,
            count=11,
            dtype="float32",
            nodata=-9999,
            crs="EPSG:4326",
            transform=transform,
        ) as dataset:
            dataset.write(values)
        with memory_file.open() as dataset:
            bands, metadata, valid_pixels = SatelliteService._validate_and_read_dataset(dataset)

    assert bands.shape == (11, 3, 4)
    assert not valid_pixels[0, 0]
    assert valid_pixels.sum() == 11
    assert metadata.crs == "EPSG:4326"
    assert metadata.transform == list(tuple(transform)[:6])


def test_geotiff_mask_encoding_preserves_georeferencing_and_nodata():
    transform = from_origin(12.5, 23.5, 10, 10)
    metadata = SatelliteRasterMetadata(
        width=2,
        height=2,
        count=11,
        crs="EPSG:4326",
        transform=list(tuple(transform)[:6]),
    )
    mask = np.array([[0, 1], [2, 3]], dtype=np.uint8)
    valid_pixels = np.array([[True, False], [True, True]])

    encoded = SatelliteService._encode_geotiff_mask(mask, valid_pixels, metadata)
    with MemoryFile(base64.b64decode(encoded)) as memory_file:
        with memory_file.open() as dataset:
            output_mask = dataset.read(1)
            assert dataset.count == 1
            assert dataset.crs.to_string() == "EPSG:4326"
            assert dataset.transform == transform
            assert dataset.nodata == 255
            assert output_mask.tolist() == [[0, 255], [2, 3]]
