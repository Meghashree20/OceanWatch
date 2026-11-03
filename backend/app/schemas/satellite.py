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
    transform: Optional[List[float]] = None


class SatelliteClassStatistic(BaseModel):
    class_id: int
    class_name: str
    color: str
    pixel_count: int
    percentage: float


class SatelliteAnalysisResponse(BaseModel):
    id: str
    name: str
    image_name: str = "uploaded-image.tif"
    coordinates: List[float] = Field(..., description="[Latitude, Longitude]")
    description: str
    sample_file: Optional[str] = None
    debris_pixel_count: int
    total_pixels: int
    debris_coverage_percentage: float
    predicted_classes: List[int] = Field(default_factory=list)
    class_statistics: List[SatelliteClassStatistic] = Field(default_factory=list)
    preview_png_base64: str
    segmentation_mask_png_base64: str = ""
    segmentation_mask_geotiff_base64: str = ""
    overlay_png_base64: str
    raster_metadata: Optional[SatelliteRasterMetadata] = None
    status: str = "success"
