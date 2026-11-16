"""Recommendation queries and scoring orchestration."""

import hashlib
import json
from typing import Any, Dict, List, Optional

from app.db.mongodb import db_client
from app.ml.recommendation import score_hotspot
from app.services.forecast_service import ForecastService
from app.services.intelligence_service import IntelligenceService


HOTSPOT_COLLECTION = "hotspot_results"


class RecommendationService:
    @staticmethod
    def _location(hotspot: Dict[str, Any]) -> Optional[Dict[str, float]]:
        centroid = hotspot.get("centroid") or {}
        latitude = centroid.get("latitude", hotspot.get("centroid_latitude"))
        longitude = centroid.get("longitude", hotspot.get("centroid_longitude"))
        try:
            latitude, longitude = float(latitude), float(longitude)
        except (TypeError, ValueError):
            return None
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return None
        return {"latitude": latitude, "longitude": longitude}

    @staticmethod
    def _same_area(location: Dict[str, float], other: Dict[str, Any]) -> bool:
        try:
            other_lat = float(other["latitude"])
            other_lon = float(other["longitude"])
            tolerance = max(float(other.get("cell_size_degrees", 1.0)) / 2, 0.01)
        except (KeyError, TypeError, ValueError):
            return False
        return abs(location["latitude"] - other_lat) <= tolerance and abs(location["longitude"] - other_lon) <= tolerance

    @staticmethod
    def _build_response_recommendation(
        location: Dict[str, float],
        hotspot_recommendation: Optional[Dict[str, Any]],
        trend: Optional[Dict[str, Any]],
        alert: Optional[Dict[str, Any]],
        freshness: Dict[str, Any],
    ) -> Dict[str, Any]:
        risk = trend.get("risk_level") if trend else None
        alert_status = alert.get("status") if alert else None
        alert_is_active = alert_status in {"ACTIVE", "ACKNOWLEDGED", "UNDER_INVESTIGATION"}
        change_types = trend.get("change_types", []) if trend else []
        uncertainty = []
        if freshness.get("status") in {"stale", "unavailable"}:
            uncertainty.append(f"Observation freshness is {freshness.get('status')}; current conditions are not established.")
        if trend is None:
            uncertainty.append("No comparable measured trend is available for this location.")
        else:
            evidence = trend.get("evidence", {})
            if not evidence.get("baseline_available"):
                uncertainty.append("A comparable historical baseline is unavailable.")
            if evidence.get("data_quality") == "low":
                uncertainty.append("Sampling evidence is low quality or sparse.")
        if hotspot_recommendation and hotspot_recommendation.get("status") == "context_required":
            missing = hotspot_recommendation.get("missing_external_factors", [])
            if missing:
                uncertainty.append(f"Existing priority score is unavailable; missing contextual inputs: {', '.join(missing)}.")
        if alert and alert.get("risk_level"):
            alert_risk = alert["risk_level"]
        else:
            alert_risk = None

        if alert_is_active or risk in {"HIGH", "CRITICAL"}:
            action_type = "INSPECTION"
            action = "Inspect the location and verify current conditions before scheduling cleanup."
            priority = "CRITICAL" if (alert_risk == "CRITICAL" or risk == "CRITICAL") else "HIGH"
        elif risk == "MEDIUM" and "increasing_pollution" in change_types:
            action_type = "PREVENTIVE_CLEANUP"
            action = "Review preventive cleanup options and confirm site conditions before dispatch."
            priority = "MEDIUM"
        else:
            action_type = "INCREASED_MONITORING"
            action = "Increase observation frequency and collect comparable measurements."
            priority = "LOW" if risk == "LOW" else "MEDIUM"

        evidence = {
            "hotspot": None,
            "existing_priority_score": None,
            "existing_priority_level": None,
            "measured_trend": trend,
            "active_alert": None,
            "data_freshness": freshness,
        }
        if hotspot_recommendation:
            evidence["hotspot"] = hotspot_recommendation.get("hotspot")
            evidence["existing_priority_score"] = hotspot_recommendation.get("priority_score")
            evidence["existing_priority_level"] = hotspot_recommendation.get("priority_level")
        if alert:
            evidence["active_alert"] = {
                "alert_id": alert.get("alert_id"),
                "risk_level": alert.get("risk_level"),
                "status": alert.get("status"),
                "triggering_evidence": alert.get("triggering_evidence"),
            }
        identity = {
            "action_type": action_type,
            "location": {key: round(value, 4) for key, value in location.items()},
            "hotspot_id": (hotspot_recommendation or {}).get("hotspot", {}).get("hotspot_id"),
            "alert_id": (alert or {}).get("alert_id"),
        }
        recommendation_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "recommendation_id": recommendation_id,
            "action_type": action_type,
            "priority": priority,
            "location": location,
            "priority_score": evidence["existing_priority_score"],
            "priority_level": evidence["existing_priority_level"] or "UNAVAILABLE",
            "recommended_action": action,
            "evidence": evidence,
            "uncertainty": uncertainty,
        }

    @staticmethod
    async def get_cleanup_recommendations(
        ecological_risk: Optional[float] = None,
        human_exposure: Optional[float] = None,
        cleanup_feasibility: Optional[float] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        existing = await RecommendationService.get_recommendations(
            ecological_risk=ecological_risk,
            human_exposure=human_exposure,
            cleanup_feasibility=cleanup_feasibility,
            limit=limit,
        )
        assessment = await IntelligenceService.get_trends()
        alert_result = await IntelligenceService.list_alerts(status=None, limit=500)
        trends = assessment.get("trends", [])
        alerts = alert_result.get("data", [])
        freshness = assessment.get("data_freshness", {"status": "unavailable", "age_days": None})
        recommendations: List[Dict[str, Any]] = []
        represented_trends = set()
        represented_alerts = set()

        for existing_recommendation in existing["data"]:
            hotspot = existing_recommendation.get("hotspot") or {}
            location = RecommendationService._location(hotspot)
            if location is None:
                continue
            trend_match = next(
                (trend for trend in trends if RecommendationService._same_area(location, trend.get("location", {}))),
                None,
            )
            alert_match = next(
                (alert for alert in alerts if RecommendationService._same_area(location, alert.get("location", {}))),
                None,
            )
            if trend_match:
                represented_trends.add(id(trend_match))
            if alert_match:
                represented_alerts.add(id(alert_match))
            recommendations.append(RecommendationService._build_response_recommendation(
                location, existing_recommendation, trend_match, alert_match, freshness
            ))

        for trend in trends:
            if id(trend) in represented_trends:
                continue
            location = trend.get("location", {})
            if "latitude" not in location or "longitude" not in location:
                continue
            alert_match = next(
                (alert for alert in alerts if RecommendationService._same_area(location, alert.get("location", {}))),
                None,
            )
            if alert_match:
                represented_alerts.add(id(alert_match))
            recommendations.append(RecommendationService._build_response_recommendation(
                {"latitude": float(location["latitude"]), "longitude": float(location["longitude"])},
                None,
                trend,
                alert_match,
                freshness,
            ))

        for alert in alerts:
            if id(alert) in represented_alerts:
                continue
            location = alert.get("location", {})
            try:
                normalized_location = {
                    "latitude": float(location["latitude"]),
                    "longitude": float(location["longitude"]),
                }
            except (KeyError, TypeError, ValueError):
                continue
            recommendations.append(RecommendationService._build_response_recommendation(
                normalized_location, None, None, alert, freshness
            ))

        priority_order = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
        recommendations.sort(key=lambda item: (
            priority_order[item["priority"]],
            item["priority_score"] if item["priority_score"] is not None else -1,
        ), reverse=True)
        return {"data": recommendations[:limit], "total": len(recommendations)}

    @staticmethod
    async def _forecast_trend(hotspot: Dict[str, Any]) -> Dict[str, Any]:
        region = hotspot.get("dominant_region") or hotspot.get("region")
        if not region:
            return {}
        try:
            forecast = await ForecastService.forecast(region, horizon=3)
        except (FileNotFoundError, ValueError):
            return {}
        if (
            forecast.get("metric") != "microplastic_concentration"
            or forecast.get("unit") != "pieces/m3"
        ):
            return {}

        historical = forecast.get("historical_values") or []
        predicted = forecast.get("predicted_values") or []
        if not historical or not predicted:
            return {}
        latest_value = historical[-1].get("value")
        forecast_values = [item.get("value") for item in predicted]
        return {
            "historical_value": latest_value,
            "forecast_values": forecast_values,
        }

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
            trend = await RecommendationService._forecast_trend(hotspot)
            recommendations.append(score_hotspot(
                hotspot,
                ecological_risk,
                human_exposure,
                cleanup_feasibility,
                pollution_reference=RecommendationService._reference(run_hotspots),
                forecast_values=trend.get("forecast_values"),
                historical_value=trend.get("historical_value"),
            ))
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
        trend = await RecommendationService._forecast_trend(hotspots[0])
        return score_hotspot(
            hotspots[0],
            ecological_risk,
            human_exposure,
            cleanup_feasibility,
            pollution_reference=RecommendationService._reference(run_hotspots),
            forecast_values=trend.get("forecast_values"),
            historical_value=trend.get("historical_value"),
        )

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