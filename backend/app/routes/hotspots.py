from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.schemas.hotspot import (
    DetectHotspotsRequest,
    DetectHotspotsResponse,
    HotspotListResponse,
    HotspotResponse,
    HotspotRunListResponse,
    HotspotRunResponse,
    HotspotStatsResponse,
)
from app.services.hotspot_service import HotspotService

router = APIRouter()


@router.post("/detect", response_model=DetectHotspotsResponse, summary="Detect pollution hotspots")
async def detect_hotspots(body: DetectHotspotsRequest):
    """
    Run DBSCAN hotspot detection on stored ocean-water observations.

    Parameters allow tuning of:
    - **eps_km**: neighbourhood radius in kilometres (default 150)
    - **min_samples**: minimum points per cluster (default 10)
    - **region**: optional filter by region name
    - **start_date** / **end_date**: optional ISO date strings (YYYY-MM-DD)

    Date-only end bounds include the full UTC calendar day. All datetime inputs are
    normalized to UTC, and an end date before a start date returns HTTP 400.

    Results are saved to MongoDB and can be queried via GET /api/hotspots.
    """
    try:
        result = await HotspotService.detect_hotspots(
            eps_km=body.eps_km,
            min_samples=body.min_samples,
            region=body.region,
            start_date=body.start_date,
            end_date=body.end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.get("status") == "no_data":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("/stats", response_model=HotspotStatsResponse, summary="Get hotspot statistics")
async def get_stats():
    """
    Returns aggregate statistics for all stored hotspot clusters.
    """
    stats = await HotspotService.get_stats()
    return stats


@router.get("/runs", response_model=HotspotRunListResponse, summary="List hotspot detection runs")
async def get_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return await HotspotService.get_runs(skip=skip, limit=limit)


@router.get("/runs/{run_id}", response_model=HotspotRunResponse, summary="Get a hotspot detection run")
async def get_run(run_id: str):
    result = await HotspotService.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Hotspot detection run {run_id} not found")
    return result


@router.get("/runs/{run_id}/{cluster_id}", response_model=HotspotResponse, summary="Get a hotspot from a detection run")
async def get_run_hotspot(run_id: str, cluster_id: int):
    result = await HotspotService.get_hotspot_by_run_and_id(run_id, cluster_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Hotspot cluster {cluster_id} not found in run {run_id}")
    return result


@router.get("/{cluster_id}", response_model=HotspotResponse)
async def get_hotspot(cluster_id: int):
    """
    Get a single detected hotspot cluster by its cluster_id.
    """
    doc = await HotspotService.get_hotspot_by_id(cluster_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Hotspot cluster {cluster_id} not found")
    return doc


@router.get("", response_model=HotspotListResponse, summary="List detected hotspots")
async def get_hotspots(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    severity: Optional[str] = Query(None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    ocean: Optional[str] = None,
    region: Optional[str] = None,
    detection_run_id: Optional[str] = None,
):
    """
    List all detected potential pollution hotspots.

    Supports filtering by severity level, ocean, and region.
    Results are paginated via skip/limit.
    """
    result = await HotspotService.get_hotspots(
        skip=skip,
        limit=limit,
        severity=severity,
        ocean=ocean,
        region=region,
        detection_run_id=detection_run_id,
    )
    return result
