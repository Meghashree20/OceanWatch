from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ForecastTrainRequest(BaseModel):
    min_periods: int = Field(6, ge=4, le=120)


class ForecastTrainResponse(BaseModel):
    status: str
    message: str
    aggregation: str
    zones: List[str]
    metrics: Dict[str, Any]
    validation_metrics: Optional[Dict[str, Any]] = None
    selected_params: Optional[Dict[str, Any]] = None
    periods: Optional[Dict[str, Any]] = None
    coverage: Optional[Dict[str, Any]] = None
    train_rows: int
    validation_rows: int
    test_rows: int


class ForecastResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    zone: str
    horizon: int
    historical_values: List[Dict[str, Any]]
    predicted_values: List[Dict[str, Any]]
    forecast_dates: List[str]
    model_metrics: Dict[str, Any]
    message: str


class ForecastMetricsResponse(BaseModel):
    status: str
    metrics: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    aggregation: Optional[str] = None
    zones: Optional[List[str]] = None
    train_rows: Optional[int] = None
    validation_rows: Optional[int] = None
    test_rows: Optional[int] = None
    validation_metrics: Optional[Dict[str, Any]] = None
    selected_params: Optional[Dict[str, Any]] = None
    periods: Optional[Dict[str, Any]] = None
    coverage: Optional[Dict[str, Any]] = None