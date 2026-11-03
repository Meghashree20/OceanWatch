from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HotspotCatalogItem(BaseModel):
    id: str
    name: str
    coordinates: List[float] = Field(..., description="[Latitude, Longitude]")
    description: str
    sample_file: str
    has_local_sample: bool = True


class SatelliteRasterMetadata(BaseModel):
    driver: Optional[str] = None
    width: int
    height: int
    count: int
    nodata: Optional[float] = None
    crs: Optional[str] = None
    bounds: Optional[List[float]] = None


class SatelliteAnalysisResponse(BaseModel):
    id: str
    name: str
    coordinates: List[float] = Field(..., description="[Latitude, Longitude]")
    description: str
    sample_file: Optional[str] = None
    debris_pixel_count: int
    total_pixels: int
    debris_coverage_percentage: float
    preview_png_base64: str
    overlay_png_base64: str
    raster_metadata: Optional[SatelliteRasterMetadata] = None
    status: str = "success"
