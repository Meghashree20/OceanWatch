from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.recommendation import RecommendationCalculateRequest, RecommendationListResponse, RecommendationResponse
from app.services.recommendation_service import RecommendationService


router = APIRouter()


@router.post("/calculate", response_model=RecommendationResponse, summary="Calculate a cleanup priority")
async def calculate_recommendation(body: RecommendationCalculateRequest):
    try:
        result = await RecommendationService.calculate(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Hotspot cluster {body.cluster_id} not found in run {body.detection_run_id}")
    return result


@router.get("", response_model=RecommendationListResponse, summary="List cleanup recommendations")
async def get_recommendations(
    ecological_risk: Optional[float] = Query(None, ge=0, le=100),
    human_exposure: Optional[float] = Query(None, ge=0, le=100),
    cleanup_feasibility: Optional[float] = Query(None, ge=0, le=100),
    limit: int = Query(100, ge=1, le=500),
):
    return await RecommendationService.get_recommendations(
        ecological_risk=ecological_risk,
        human_exposure=human_exposure,
        cleanup_feasibility=cleanup_feasibility,
        limit=limit,
    )


@router.get("/{cluster_id}", response_model=RecommendationResponse)
async def get_recommendation(
    cluster_id: int,
    ecological_risk: Optional[float] = Query(None, ge=0, le=100),
    human_exposure: Optional[float] = Query(None, ge=0, le=100),
    cleanup_feasibility: Optional[float] = Query(None, ge=0, le=100),
):
    try:
        result = await RecommendationService.get_recommendation(
            cluster_id,
            ecological_risk=ecological_risk,
            human_exposure=human_exposure,
            cleanup_feasibility=cleanup_feasibility,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Hotspot cluster {cluster_id} not found")
    return result