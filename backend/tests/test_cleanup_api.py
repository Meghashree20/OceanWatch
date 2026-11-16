import pytest


@pytest.mark.asyncio
async def test_cleanup_recommendations_endpoint_is_authenticated_and_returns_evidence(
    authenticated_app,
    monkeypatch,
):
    from httpx import ASGITransport, AsyncClient

    from app.services.recommendation_service import RecommendationService

    async def get_recommendations(**_kwargs):
        return {
            "data": [{
                "recommendation_id": "a" * 64,
                "action_type": "INCREASED_MONITORING",
                "priority": "LOW",
                "location": {"latitude": 10.5, "longitude": 20.5},
                "priority_score": None,
                "priority_level": "UNAVAILABLE",
                "recommended_action": "Increase observation frequency.",
                "evidence": {"data_freshness": {"status": "fresh"}},
                "uncertainty": ["Existing priority context is missing."],
            }],
            "total": 1,
        }

    monkeypatch.setattr(
        RecommendationService,
        "get_cleanup_recommendations",
        staticmethod(get_recommendations),
    )
    async with AsyncClient(
        transport=ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/cleanup/recommendations")

    assert response.status_code == 200
    result = response.json()["data"][0]
    assert result["priority_score"] is None
    assert result["evidence"]["data_freshness"]["status"] == "fresh"
    assert result["uncertainty"] == ["Existing priority context is missing."]


@pytest.mark.asyncio
async def test_operation_creation_requires_administrator(authenticated_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/cleanup/operations",
            json={"recommendation_id": "a" * 64},
        )

    assert response.status_code == 403
