import pytest

from app.ml.recommendation import score_hotspot


def test_recommendation_score_and_action_are_transparent():
    result = score_hotspot(
        {"cluster_id": 1, "severity": "CRITICAL", "observation_count": 100},
        ecological_risk=90,
        human_exposure=80,
        cleanup_feasibility=70,
    )
    assert result["priority_score"] == 49.0
    assert result["priority_level"] == "MEDIUM"
    assert result["recommended_action"] == "Schedule further assessment"
    assert result["weighted_components"]["pollution_severity"] == 0.0


def test_recommendation_does_not_invent_external_factors():
    result = score_hotspot({"cluster_id": 1, "severity": "LOW", "observation_count": 5})
    assert result["priority_score"] is None
    assert result["priority_level"] == "UNAVAILABLE"
    assert len(result["missing_external_factors"]) == 3


@pytest.mark.asyncio
async def test_recommendations_endpoint_requires_context_and_returns_calculated_scores(
    authenticated_app,
    monkeypatch,
):
    from httpx import ASGITransport, AsyncClient

    from app.services.recommendation_service import RecommendationService

    hotspot = {
        "cluster_id": 7,
        "observation_count": 50,
        "average_pollution": 10.0,
        "region": None,
        "detection_run_id": "run-1",
    }

    async def get_hotspots(**_kwargs):
        return [hotspot]

    monkeypatch.setattr(RecommendationService, "_get_hotspots", get_hotspots)

    async with AsyncClient(
        transport=ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        missing_context = await client.get("/api/recommendations")
        calculated = await client.get(
            "/api/recommendations",
            params={
                "ecological_risk": 80,
                "human_exposure": 60,
                "cleanup_feasibility": 40,
            },
        )

    assert missing_context.status_code == 200
    unavailable = missing_context.json()["data"][0]
    assert unavailable["status"] == "context_required"
    assert unavailable["priority_score"] is None
    assert unavailable["priority_level"] == "UNAVAILABLE"
    assert unavailable["missing_external_factors"] == [
        "ecological_risk",
        "human_exposure",
        "cleanup_feasibility",
    ]

    assert calculated.status_code == 200
    recommendation = calculated.json()["data"][0]
    assert recommendation["status"] == "calculated"
    assert recommendation["priority_score"] == 78.0
    assert recommendation["priority_level"] == "CRITICAL"
    assert recommendation["recommended_action"] == "Immediate cleanup assessment"