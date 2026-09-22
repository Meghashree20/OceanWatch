from fastapi import APIRouter, HTTPException, Query

from app.schemas.forecast import ForecastMetricsResponse, ForecastResponse, ForecastTrainRequest, ForecastTrainResponse
from app.services.forecast_service import ForecastService


router = APIRouter()


@router.post("/train", response_model=ForecastTrainResponse, summary="Train the pollution forecast model")
async def train_forecast(body: ForecastTrainRequest = ForecastTrainRequest()):
    try:
        return await ForecastService.train(min_periods=body.min_periods)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/model-metrics", response_model=ForecastMetricsResponse)
async def get_model_metrics():
    result = ForecastService.get_metrics()
    if result["status"] == "not_trained":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("/{zone_id}", response_model=ForecastResponse)
async def get_forecast(zone_id: str, horizon: int = Query(3, ge=1, le=12)):
    try:
        return await ForecastService.forecast(zone_id, horizon)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc