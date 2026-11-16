import pytest

from app.services.intelligence_service import IntelligenceService
from app.services.recommendation_service import RecommendationService


def _trend(risk="HIGH", changes=None, baseline=True, quality="moderate"):
    return {
        "location": {"latitude": 10.5, "longitude": 20.5, "cell_size_degrees": 1.0},
        "risk_level": risk,
        "change_types": changes or [],
        "evidence": {"baseline_available": baseline, "data_quality": quality},
    }


def test_response_recommendation_explains_priority_and_missing_context():
    recommendation = {
        "status": "context_required",
        "hotspot": {"hotspot_id": "hotspot-1"},
        "priority_score": None,
        "priority_level": "UNAVAILABLE",
        "missing_external_factors": ["ecological_risk", "human_exposure"],
    }

    result = RecommendationService._build_response_recommendation(
        {"latitude": 10.5, "longitude": 20.5},
        recommendation,
        _trend("HIGH", ["newly_high_risk"]),
        {
            "alert_id": "alert-1",
            "status": "ACTIVE",
            "risk_level": "HIGH",
            "triggering_evidence": {"change_types": ["newly_high_risk"]},
        },
        {"status": "fresh", "age_days": 2},
    )

    assert result["action_type"] == "INSPECTION"
    assert result["priority"] == "HIGH"
    assert result["priority_score"] is None
    assert "ecological_risk" in result["uncertainty"][0]
    assert result["evidence"]["active_alert"]["alert_id"] == "alert-1"
    assert "Inspect" in result["recommended_action"]


def test_increasing_medium_measurement_recommends_preventive_cleanup():
    result = RecommendationService._build_response_recommendation(
        {"latitude": 10.5, "longitude": 20.5},
        None,
        _trend("MEDIUM", ["increasing_pollution"]),
        None,
        {"status": "fresh", "age_days": 1},
    )

    assert result["action_type"] == "PREVENTIVE_CLEANUP"
    assert result["priority"] == "MEDIUM"


def test_unavailable_or_stale_data_recommends_more_monitoring_and_explains_uncertainty():
    result = RecommendationService._build_response_recommendation(
        {"latitude": 10.5, "longitude": 20.5},
        None,
        None,
        None,
        {"status": "stale", "age_days": 120},
    )

    assert result["action_type"] == "INCREASED_MONITORING"
    assert any("stale" in item for item in result["uncertainty"])
    assert any("No comparable measured trend" in item for item in result["uncertainty"])


@pytest.mark.asyncio
async def test_cleanup_recommendations_merge_priority_trend_alert_and_freshness(monkeypatch):
    hotspot = {
        "centroid": {"latitude": 10.5, "longitude": 20.5},
        "hotspot_id": "hotspot-1",
    }
    base_recommendation = {
        "status": "calculated",
        "hotspot": hotspot,
        "priority_score": 78.0,
        "priority_level": "CRITICAL",
        "missing_external_factors": [],
    }
    trend = _trend("HIGH", ["persistent_hotspot"])
    alert = {
        "alert_id": "alert-1",
        "location": trend["location"],
        "status": "ACTIVE",
        "risk_level": "HIGH",
    }

    async def get_recommendations(**_kwargs):
        return {"data": [base_recommendation], "total": 1}

    async def get_trends():
        return {"trends": [trend], "data_freshness": {"status": "fresh", "age_days": 1}}

    async def list_alerts(**_kwargs):
        return {"data": [alert], "total": 1}

    monkeypatch.setattr(RecommendationService, "get_recommendations", get_recommendations)
    monkeypatch.setattr(IntelligenceService, "get_trends", get_trends)
    monkeypatch.setattr(IntelligenceService, "list_alerts", list_alerts)

    response = await RecommendationService.get_cleanup_recommendations()

    assert response["total"] == 1
    item = response["data"][0]
    assert item["priority_score"] == 78.0
    assert item["evidence"]["measured_trend"] == trend
    assert item["evidence"]["active_alert"]["alert_id"] == "alert-1"
    assert item["evidence"]["data_freshness"]["status"] == "fresh"
