from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NormalizedObservation(BaseModel):
    """Source-neutral envelope that retains each source's metric semantics."""

    model_config = ConfigDict(extra="forbid")

    source_type: Literal["noaa", "oceanscan", "sentinel2"]
    source_id: str = Field(min_length=1)
    observed_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    metric: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    region: Optional[str] = None
    ocean: Optional[str] = None
    country: Optional[str] = None
    quality_info: Optional[Dict[str, Any]] = None
    source_metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> NormalizedObservation:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be provided or both be omitted")
        return self
