from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from app.schemas.observation import NormalizedObservation
from app.schemas.pollution import PollutionObservationBase
from app.schemas.satellite import SatelliteAnalysisResponse


class ObservationService:
    """Adapts source-specific observations without changing source storage."""

    @staticmethod
    def from_noaa(
        observation: PollutionObservationBase | Mapping[str, Any],
    ) -> NormalizedObservation:
        record = PollutionObservationBase.model_validate(observation)
        metadata = {
            key: value
            for key, value in {
                "concentration_class": record.concentration_class,
                "subregion": record.subregion,
                "sampling_method": record.sampling_method,
                "organization": record.organization,
                "study_type": record.study_type,
            }.items()
            if value is not None
        }
        return NormalizedObservation(
            source_type="noaa",
            source_id=record.unique_id,
            observed_at=record.sample_date,
            latitude=record.latitude,
            longitude=record.longitude,
            metric="microplastic_concentration",
            value=record.measurement,
            unit=record.unit,
            region=record.region,
            ocean=record.ocean,
            country=record.country,
            source_metadata=metadata,
        )

    @staticmethod
    def from_satellite(
        result: SatelliteAnalysisResponse | Mapping[str, Any],
        *,
        observed_at: Optional[datetime] = None,
        analyzed_at: Optional[datetime] = None,
    ) -> NormalizedObservation:
        analysis = SatelliteAnalysisResponse.model_validate(result)
        if analysis.debris_coverage_percentage is None:
            raise ValueError(
                "Satellite analysis has no sufficiently confident pixels; debris coverage is unavailable."
            )
        latitude, longitude = analysis.coordinates

        # SatelliteService uses (0, 0) as a placeholder when uploaded imagery
        # has no supplied coordinates and no usable geographic bounds.
        has_coordinates = (
            analysis.id != "custom-upload" or (latitude != 0.0 or longitude != 0.0)
        )
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            has_coordinates = False

        source_metadata: dict[str, Any] = {
            "site_name": analysis.name,
            "debris_pixel_count": analysis.debris_pixel_count,
            "total_pixels": analysis.total_pixels,
            "debris_coverage_percentage": analysis.debris_coverage_percentage,
            "valid_pixel_count": analysis.valid_pixel_count,
            "confident_pixel_count": analysis.confident_pixel_count,
            "uncertain_pixel_count": analysis.uncertain_pixel_count,
            "uncertain_pixel_percentage": analysis.uncertain_pixel_percentage,
            "average_confidence": analysis.average_confidence,
            "confidence_threshold": analysis.confidence_threshold,
            "analysis_reliable": analysis.analysis_reliable,
            "warnings": analysis.warnings,
            "description": analysis.description,
            "sample_file": analysis.sample_file,
            "raster_metadata": (
                analysis.raster_metadata.model_dump(exclude_none=True)
                if analysis.raster_metadata
                else None
            ),
            "model": {
                "name": "MARIDA U-Net",
                "debris_class_index": 0,
                "debris_class": "Marine Debris",
            },
        }
        source_metadata = {
            key: value for key, value in source_metadata.items() if value is not None
        }

        return NormalizedObservation(
            source_type="sentinel2",
            source_id=analysis.id,
            observed_at=observed_at,
            analyzed_at=analyzed_at,
            latitude=latitude if has_coordinates else None,
            longitude=longitude if has_coordinates else None,
            metric="marine_debris_coverage",
            value=analysis.debris_coverage_percentage,
            unit="percent",
            source_metadata=source_metadata,
        )
