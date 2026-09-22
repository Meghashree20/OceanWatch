from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RecommendationResponse(BaseModel):
    status: str
    hotspot: Dict[str, Any]
    cluster: Dict[str, Any]
    priority_score: Optional[float]
    priority_level: str
    factor_scores: Dict[str, Dict[str, Any]]
    weighted_components: Optional[Dict[str, float]] = None
    weights: Dict[str, float]
    recommended_action: str
    recommendation: str
    contributions: Optional[Dict[str, float]] = None
    calculation_explanation: str
    missing_external_factors: List[str] = Field(default_factory=list)


class RecommendationListResponse(BaseModel):
    data: List[RecommendationResponse]
    total: int


class ContextualFactors(BaseModel):
    ecological_risk: Optional[float] = Field(None, ge=0, le=100)
    human_exposure: Optional[float] = Field(None, ge=0, le=100)
    cleanup_feasibility: Optional[float] = Field(None, ge=0, le=100)


class RecommendationCalculateRequest(ContextualFactors):
    cluster_id: int = Field(..., ge=0)
    detection_run_id: str = Field(..., min_length=1, max_length=128)