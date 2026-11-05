from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.observation import NormalizedObservation
from app.schemas.satellite import SatelliteAnalysisResponse, SatelliteRasterMetadata
from app.services.observation_service import ObservationService


def test_noaa_record_normalizes_without_changing_measurement_semantics():
    sample_date = datetime(2025, 3, 4, tzinfo=timezone.utc)
    normalized = ObservationService.from_noaa(
        {
            "unique_id": "noaa-123",
            "sample_date": sample_date,
            "latitude": 12.5,
            "longitude": -45.25,
            "measurement": 3.75,
            "unit": "pieces/m3",
            "concentration_class": "low",
            "region": "Atlantic",
            "ocean": "Atlantic Ocean",
            "country": "Ghana",
            "sampling_method": "net tow",
        }
    )

    assert normalized.source_type == "noaa"
    assert normalized.source_id == "noaa-123"
    assert normalized.observed_at == sample_date
    assert normalized.metric == "microplastic_concentration"
    assert normalized.value == 3.75
    assert normalized.unit == "pieces/m3"
    assert normalized.source_metadata == {
        "concentration_class": "low",
        "sampling_method": "net tow",
    }


def test_satellite_result_normalizes_scientific_metrics_without_preview_data():
    result = SatelliteAnalysisResponse(
        id="accra-coast",
        name="Accra Coast, Ghana",
        coordinates=[5.55, -0.2],
        description="Registered site",
        debris_pixel_count=1205,
        total_pixels=65536,
        valid_pixel_count=65536,
        confident_pixel_count=65536,
        uncertain_pixel_count=0,
        uncertain_pixel_percentage=0.0,
        excluded_pixel_count=0,
        excluded_pixel_percentage=0.0,
        confidence_threshold=0.5,
        average_confidence=0.9,
        debris_coverage_percentage=1.8387,
        preview_png_base64="preview-not-to-be-persisted",
        overlay_png_base64="overlay-not-to-be-persisted",
        analysis_reliable=True,
        raster_metadata=SatelliteRasterMetadata(
            width=256,
            height=256,
            count=11,
            crs="EPSG:4326",
            bounds=[-0.3, 5.4, -0.1, 5.7],
        ),
    )
    analyzed_at = datetime(2025, 3, 4, tzinfo=timezone.utc)

    normalized = ObservationService.from_satellite(result, analyzed_at=analyzed_at)

    assert normalized.source_type == "sentinel2"
    assert normalized.source_id == "accra-coast"
    assert normalized.analyzed_at == analyzed_at
    assert normalized.observed_at is None
    assert normalized.latitude == 5.55
    assert normalized.longitude == -0.2
    assert normalized.metric == "marine_debris_coverage"
    assert normalized.value == 1.8387
    assert normalized.unit == "percent"
    assert normalized.source_metadata["debris_pixel_count"] == 1205
    assert normalized.source_metadata["total_pixels"] == 65536
    assert normalized.source_metadata["model"]["debris_class_index"] == 0
    assert normalized.source_metadata["raster_metadata"]["crs"] == "EPSG:4326"
    assert "preview_png_base64" not in normalized.model_dump()
    assert "overlay_png_base64" not in normalized.model_dump()


def test_satellite_placeholder_coordinates_are_not_normalized_as_real_location():
    result = SatelliteAnalysisResponse(
        id="custom-upload",
        name="Unlocated upload",
        coordinates=[0.0, 0.0],
        description="Uploaded patch",
        debris_pixel_count=0,
        total_pixels=256,
        valid_pixel_count=256,
        confident_pixel_count=256,
        uncertain_pixel_count=0,
        uncertain_pixel_percentage=0.0,
        excluded_pixel_count=0,
        excluded_pixel_percentage=0.0,
        confidence_threshold=0.5,
        average_confidence=0.9,
        debris_coverage_percentage=0.0,
        preview_png_base64="",
        overlay_png_base64="",
        analysis_reliable=True,
    )

    normalized = ObservationService.from_satellite(result)

    assert normalized.latitude is None
    assert normalized.longitude is None


def test_satellite_observation_rejects_coverage_when_no_pixels_are_confident():
    result = SatelliteAnalysisResponse(
        id="custom-upload",
        name="Uncertain upload",
        coordinates=[0.0, 0.0],
        description="Uploaded patch",
        debris_pixel_count=0,
        total_pixels=2,
        valid_pixel_count=2,
        confident_pixel_count=0,
        uncertain_pixel_count=2,
        uncertain_pixel_percentage=100.0,
        excluded_pixel_count=2,
        excluded_pixel_percentage=100.0,
        confidence_threshold=0.5,
        average_confidence=0.2,
        debris_coverage_percentage=None,
        preview_png_base64="",
        overlay_png_base64="",
        analysis_reliable=False,
    )

    with pytest.raises(ValueError, match="no sufficiently confident pixels"):
        ObservationService.from_satellite(result)


def test_normalized_observation_requires_coordinate_pair():
    with pytest.raises(ValidationError):
        NormalizedObservation(
            source_type="oceanscan",
            source_id="sensor-1",
            latitude=1.0,
            metric="plastic_count",
            value=2.0,
            unit="count",
        )


def test_normalized_schema_can_represent_oceanscan_without_source_adapter():
    normalized = NormalizedObservation(
        source_type="oceanscan",
        source_id="sensor-1",
        metric="plastic_count",
        value=2.0,
        unit="count",
        source_metadata={"sensor_model": "future-integration"},
    )

    assert normalized.source_type == "oceanscan"
    assert normalized.metric == "plastic_count"
    assert normalized.source_metadata["sensor_model"] == "future-integration"
