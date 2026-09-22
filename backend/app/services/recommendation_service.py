"""Recommendation queries and scoring orchestration."""

from typing import Any, Dict, List, Optional

from app.db.mongodb import db_client
from app.ml.recommendation import score_hotspot


HOTSPOT_COLLECTION = "hotspot_results"


class RecommendationService:
    @staticmethod
    async def _get_hotspots(cluster_id: Optional[int] = None, detection_run_id: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        collection = db_client.db[HOTSPOT_COLLECTION]
        query: Dict[str, Any] = {}
        if cluster_id is not None:
            query["cluster_id"] = cluster_id
        if detection_run_id:
            query["detection_run_id"] = detection_run_id
        cursor = collection.find(query, {"_id": 0}).limit(limit)
        return await cursor.to_list(length=limit)

    @staticmethod
    def _reference(hotspots: List[Dict[str, Any]]) -> Dict[str, float]:
        values = [float(hotspot.get("average_pollution", 0.0)) for hotspot in hotspots]
        return {"min": min(values), "max": max(values)} if values else {"min": 0.0, "max": 0.0}

    @staticmethod
    async def get_recommendations(
        ecological_risk: Optional[float] = None,
        human_exposure: Optional[float] = None,
        cleanup_feasibility: Optional[float] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        hotspots = await RecommendationService._get_hotspots(limit=limit)
        recommendations = []
        for hotspot in hotspots:
            run_hotspots = await RecommendationService._get_hotspots(detection_run_id=hotspot.get("detection_run_id"), limit=500)
            recommendations.append(score_hotspot(hotspot, ecological_risk, human_exposure, cleanup_feasibility, pollution_reference=RecommendationService._reference(run_hotspots)))
        recommendations.sort(key=lambda item: item["priority_score"] if item["priority_score"] is not None else -1, reverse=True)
        return {"data": recommendations, "total": len(recommendations)}

    @staticmethod
    async def get_recommendation(
        cluster_id: int,
        detection_run_id: Optional[str] = None,
        ecological_risk: Optional[float] = None,
        human_exposure: Optional[float] = None,
        cleanup_feasibility: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        hotspots = await RecommendationService._get_hotspots(cluster_id=cluster_id, detection_run_id=detection_run_id, limit=1)
        if not hotspots:
            return None
        run_hotspots = await RecommendationService._get_hotspots(detection_run_id=hotspots[0].get("detection_run_id"), limit=500)
        return score_hotspot(hotspots[0], ecological_risk, human_exposure, cleanup_feasibility, pollution_reference=RecommendationService._reference(run_hotspots))

    @staticmethod
    async def calculate(
        cluster_id: int,
        detection_run_id: str,
        ecological_risk: float,
        human_exposure: float,
        cleanup_feasibility: float,
    ) -> Optional[Dict[str, Any]]:
        return await RecommendationService.get_recommendation(
            cluster_id=cluster_id,
            detection_run_id=detection_run_id,
            ecological_risk=ecological_risk,
            human_exposure=human_exposure,
            cleanup_feasibility=cleanup_feasibility,
        )