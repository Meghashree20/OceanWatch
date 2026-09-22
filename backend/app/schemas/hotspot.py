from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Optional, List, Dict

from app.core.config import settings

class Centroid(BaseModel):
    latitude: float
    longitude: float

class HotspotResponse(BaseModel):
    cluster_id: int
    hotspot_id: Optional[str] = None
    detection_run_id: Optional[str] = None
    created_at: Optional[datetime] = None
    dataset_hash: Optional[str] = None
    eps_km: Optional[float] = None
    min_samples: Optional[int] = None
    observation_count: int
    centroid: Centroid
    centroid_latitude: Optional[float] = None
    centroid_longitude: Optional[float] = None
    average_pollution: float
    median_pollution: Optional[float] = None
    maximum_pollution: float
    minimum_pollution: float
    pollution_std: float
    date_range: Dict[str, Optional[str]]
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    region: Optional[str] = None
    dominant_region: Optional[str] = None
    ocean: Optional[str] = None
    severity: str
    label: str = "Potential Pollution Hotspot"

class HotspotStatsResponse(BaseModel):
    total_clusters: int
    total_observations_in_clusters: int
    severity_distribution: Dict[str, int]
    last_run_eps_km: Optional[float] = None
    last_run_min_samples: Optional[int] = None


class HotspotListResponse(BaseModel):
    data: List[HotspotResponse]
    total: int
    skip: int
    limit: int


class DetectHotspotsResponse(BaseModel):
    status: str
    detection_run_id: Optional[str] = None
    created_at: Optional[datetime] = None
    dataset_hash: Optional[str] = None
    total_clusters: int
    noise_points: int
    total_observations_used: int
    eps_km: float
    min_samples: int
    severity_distribution: Dict[str, int]


class HotspotRunResponse(BaseModel):
    run_id: str
    created_at: datetime
    eps_km: float
    min_samples: int
    dataset_hash: str
    total_clusters: int
    noise_points: int
    total_observations_used: int
    severity_distribution: Dict[str, int]
    filters: Dict[str, Any] = Field(default_factory=dict)
    status: str = "success"


class HotspotRunListResponse(BaseModel):
    data: List[HotspotRunResponse]
    total: int
    skip: int
    limit: int

class DetectHotspotsRequest(BaseModel):
    eps_km: float = Field(settings.DBSCAN_EPS_KM, gt=0, le=2000)
    min_samples: int = Field(settings.DBSCAN_MIN_SAMPLES, ge=1, le=10000)
    region: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
