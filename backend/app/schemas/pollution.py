from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class PollutionObservationBase(BaseModel):
    unique_id: str
    sample_date: Optional[datetime] = None
    latitude: float
    longitude: float
    measurement: float
    unit: str = "pieces/m3"
    concentration_class: Optional[str] = None
    ocean: Optional[str] = None
    region: Optional[str] = None
    subregion: Optional[str] = None
    country: Optional[str] = None
    sampling_method: Optional[str] = None
    organization: Optional[str] = None
    study_type: Optional[str] = None

class PollutionObservationResponse(PollutionObservationBase):
    pass

class PaginatedResponse(BaseModel):
    data: List[PollutionObservationResponse]
    total: int
    skip: int
    limit: int


class DataImportResponse(BaseModel):
    status: str
    total_documents: int


class DataStatsResponse(BaseModel):
    total_observations: int
