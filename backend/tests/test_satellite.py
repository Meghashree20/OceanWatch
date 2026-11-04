"""Tests for Sentinel-2 MARIDA U-Net satellite analysis service and API."""

from pathlib import Path
import base64
import shutil

import numpy as np
import pytest
import rasterio
import torch
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from starlette.testclient import TestClient

from app.ml.satellite.detector import DebrisDetector
from app.ml.satellite.unet import UNet
from app.schemas.satellite import SatelliteRasterMetadata
from app.services.satellite_service import SatelliteService

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "marida"
SAMPLE_TIF = FIXTURE_DIR / "S2_12-12-20_16PCC_0.tif"
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "model.pth"
CLASS_NAMES = [
    "Marine Debris", "Dense Sargassum", "Sparse Sargassum",
    "Natural Organic Material", "Ship", "Clouds", "Marine Water",
    "Sediment-Laden Water", "Foam", "Turbid Water", "Shallow Water",
]
BAND_ORDER = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]


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
    assert accra["inference_available"] is False


def test_analyze_registered_hotspot_via_post(client):
    response = client.post("/api/satellite/analyze", data={"hotspot_id": "accra-coast"})
    assert response.status_code == 422
    assert "not verified Sentinel-2 imagery" in response.json()["error"]["message"]


def test_analyze_registered_hotspot_by_id_endpoint(client):
    response = client.get("/api/satellite/hotspots/accra-coast/analyze")
    assert response.status_code == 422
    assert "not verified Sentinel-2 imagery" in response.json()["error"]["message"]


def test_analyze_uploaded_geotiff(client):
    assert SAMPLE_TIF.is_file(), f"Sample GeoTIFF not found at {SAMPLE_TIF}"
    with SAMPLE_TIF.open("rb") as sample_file:
        file_bytes = sample_file.read()
    with rasterio.open(SAMPLE_TIF) as source:
        expected_transform = source.transform

    response = client.post(
        "/api/satellite/analyze",
        files={"file": ("marida-test.tif", file_bytes, "image/tiff")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "custom-upload"
    assert data["total_pixels"] == 256 * 256
    assert sum(item["pixel_count"] for item in data["class_statistics"]) == data["total_pixels"]
    assert data["raster_metadata"]["count"] == 11
    assert data["raster_metadata"]["crs"] == "EPSG:32616"
    assert data["predicted_classes"]
    assert len(data["preview_png_base64"]) > 100
    assert len(data["overlay_png_base64"]) > 100

    encoded_mask = base64.b64decode(data["segmentation_mask_geotiff_base64"])
    with MemoryFile(encoded_mask) as memory_file:
        with memory_file.open() as dataset:
            mask = dataset.read(1)
            assert (dataset.width, dataset.height) == (256, 256)
            assert dataset.crs.to_string() == "EPSG:32616"
            assert dataset.transform == expected_transform
            assert set(np.unique(mask)).issubset(set(range(11)) | {255})


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


def test_official_checkpoint_is_provenance_verified_and_architecture_compatible():
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
    model = UNet(input_bands=11, output_classes=11, hidden_channels=16)
    model.load_state_dict(checkpoint, strict=True)

    detector = DebrisDetector(
        model_path=MODEL_PATH,
        class_names=CLASS_NAMES,
        band_order=BAND_ORDER,
    )
    assert not detector.model.training

    with rasterio.open(SAMPLE_TIF) as dataset:
        image = torch.from_numpy(dataset.read().astype(np.float32))
    predicted_mask = detector.predict(image)

    assert tuple(predicted_mask.shape) == (256, 256)
    assert int(predicted_mask.min()) >= 0
    assert int(predicted_mask.max()) < 11


def test_inference_imputes_nonfinite_bands_with_training_mean():
    detector = DebrisDetector(
        model_path=MODEL_PATH,
        class_names=CLASS_NAMES,
        band_order=BAND_ORDER,
    )
    with rasterio.open(SAMPLE_TIF) as dataset:
        image = torch.from_numpy(dataset.read().astype(np.float32))

    image_with_nodata = image.clone()
    image_with_nodata[0, 10, 10] = float("nan")
    image_imputed = image.clone()
    image_imputed[0, 10, 10] = detector.preprocessing["mean"][0, 0, 0, 0]

    assert torch.equal(detector.predict(image_with_nodata), detector.predict(image_imputed))


def test_official_test_patch_matches_its_labeled_pixels():
    detector = DebrisDetector(
        model_path=MODEL_PATH,
        class_names=CLASS_NAMES,
        band_order=BAND_ORDER,
    )
    with rasterio.open(SAMPLE_TIF) as dataset:
        image = torch.from_numpy(dataset.read().astype(np.float32))
    with rasterio.open(FIXTURE_DIR / "S2_12-12-20_16PCC_0_cl.tif") as dataset:
        labels = dataset.read(1).astype(np.int16)

    for source_class in (12, 13, 14, 15):
        labels[labels == source_class] = 7
    labels -= 1
    annotated = labels >= 0
    prediction = detector.predict(image).numpy()

    assert annotated.sum() == 13
    assert np.array_equal(prediction[annotated], labels[annotated])


def test_modified_checkpoint_fails_sha256_verification(tmp_path):
    checkpoint_path = tmp_path / "model.pth"
    metadata_path = tmp_path / "model.pth.metadata.json"
    shutil.copyfile(MODEL_PATH, checkpoint_path)
    shutil.copyfile(MODEL_PATH.with_name("model.pth.metadata.json"), metadata_path)
    checkpoint_path.write_bytes(checkpoint_path.read_bytes() + b"tampered")

    with pytest.raises(ValueError, match="SHA-256"):
        DebrisDetector(
            model_path=checkpoint_path,
            class_names=CLASS_NAMES,
            band_order=BAND_ORDER,
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
