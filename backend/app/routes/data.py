from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
from pathlib import Path

from app.schemas.pollution import DataImportResponse, DataStatsResponse, PaginatedResponse, PollutionObservationResponse
from app.services.data_service import DataService
from app.core.dates import parse_date_range

router = APIRouter()

@router.post("/import", response_model=DataImportResponse, summary="Import cleaned NOAA observations")
async def import_data():
    """
    Imports the cleaned NOAA dataset into MongoDB.
    """
    # Assuming the server runs from backend/ directory or we construct absolute path
    csv_path = Path(__file__).parent.parent.parent / "data" / "processed" / "ocean_water_clean.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Cleaned CSV not found. Please run preprocessing first.")
    
    try:
        result = await DataService.import_data(str(csv_path))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result

@router.get("/stats", response_model=DataStatsResponse, summary="Get observation statistics")
async def get_stats():
    """
    Returns statistics about the stored data.
    """
    stats = await DataService.get_stats()
    return stats

@router.get("/{unique_id}", response_model=PollutionObservationResponse)
async def get_observation(unique_id: str):
    """
    Gets a single observation by unique ID.
    """
    doc = await DataService.get_observation_by_id(unique_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Observation not found")
    return doc

@router.get("", response_model=PaginatedResponse)
async def get_observations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = Query(None, description="ISO date or datetime interpreted in UTC"),
    end_date: Optional[str] = Query(None, description="ISO date or datetime; date-only values include the full UTC day"),
    region: Optional[str] = None,
    ocean: Optional[str] = None,
    concentration_class: Optional[str] = None
):
    """
    Gets a paginated list of observations with optional filters.

    ISO date-only end bounds include the entire UTC calendar day. Datetimes with
    offsets are converted to UTC before querying MongoDB.
    """
    try:
        start_bound, end_bound = parse_date_range(start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = await DataService.get_observations(
        skip=skip,
        limit=limit,
        start_date=start_bound,
        end_date=end_bound,
        region=region,
        ocean=ocean,
        concentration_class=concentration_class
    )
    return response
