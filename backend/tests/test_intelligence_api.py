import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.auth import require_admin_user
from app.models.user import User
from app.services.intelligence_service import IntelligenceService


@pytest_asyncio.fixture
async def client(authenticated_app):
    async with AsyncClient(transport=ASGITransport(app=authenticated_app), base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_trend_endpoint_exposes_observed_evidence(monkeypatch, client):
    async def get_trends(window_days):
        return {
            "status": "ready",
            "source": "observed NOAA microplastic measurements",
            "unit": "pieces/m3",
            "windows": {
                "previous": {"start": "2024-01-01T00:00:00+00:00", "end": "2024-03-31T00:00:00+00:00"},
                "recent": {"start": "2024-03-31T00:00:00+00:00", "end": "2024-06-29T00:00:00+00:00"},
                "days_per_window": window_days,
            },
            "latest_observation": "2024-06-29T00:00:00+00:00",
            "coverage": {"recent_observations": 3, "previous_observations": 3},
            "trends": [],
        }

    monkeypatch.setattr(IntelligenceService, "get_trends", staticmethod(get_trends))
    response = await client.get("/api/intelligence/trends?window_days=90")

    assert response.status_code == 200
    assert response.json()["source"] == "observed NOAA microplastic measurements"
    assert response.json()["windows"]["days_per_window"] == 90


@pytest.mark.asyncio
async def test_trend_endpoint_validates_comparison_window(client):
    response = await client.get("/api/intelligence/trends?window_days=3")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_organization_management_requires_admin(client):
    response = await client.post("/api/intelligence/organizations", json={
        "name": "Coastal Response Group",
        "contact_email": "ops@example.org",
        "service_area": {
            "type": "Polygon",
            "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 1]]],
        },
        "areas_served": ["Bay A"],
        "email_notifications_enabled": True,
        "acknowledgment_required": True,
    })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_assessment_endpoint_refreshes_trends_and_alerts(monkeypatch, client):
    async def assess():
        return {
            "status": "ready",
            "source": "observed NOAA microplastic measurements",
            "trends": [],
            "alerts": {"data": [], "total": 0},
        }

    monkeypatch.setattr(IntelligenceService, "assess", staticmethod(assess))
    response = await client.post("/api/intelligence/assess")

    assert response.status_code == 200
    assert response.json()["alerts"]["total"] == 0


@pytest.mark.asyncio
async def test_notification_send_requires_explicit_approval(client):
    async def admin_user():
        return User(
            user_id="admin-1",
            full_name="Test Admin",
            email="admin@example.org",
            password_hash="test-only",
            is_admin=True,
        )

    app.dependency_overrides[require_admin_user] = admin_user
    try:
        response = await client.post(
            "/api/intelligence/alerts/alert-1/notifications",
            json={"organization_id": "org-1", "approved": False},
        )
    finally:
        app.dependency_overrides.pop(require_admin_user, None)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_can_create_organization_and_send_only_after_approval(monkeypatch, client):
    async def admin_user():
        return User(
            user_id="admin-1",
            full_name="Test Admin",
            email="admin@example.org",
            password_hash="test-only",
            is_admin=True,
        )

    async def create_organization(payload, actor_id):
        return {"organization_id": "org-1", **payload, "verified": False, "created_by": actor_id}

    async def send_notification(alert_id, organization_id, actor_id):
        return {
            "notification_id": "notification-1",
            "alert_id": alert_id,
            "organization_id": organization_id,
            "delivery_status": "SENT",
            "approved_by": actor_id,
        }

    app.dependency_overrides[require_admin_user] = admin_user
    monkeypatch.setattr(IntelligenceService, "create_organization", staticmethod(create_organization))
    monkeypatch.setattr(IntelligenceService, "send_notification", staticmethod(send_notification))
    try:
        org_response = await client.post("/api/intelligence/organizations", json={
            "name": "Coastal Response Group",
            "contact_email": "ops@example.org",
            "service_area": {
                "type": "Polygon",
                "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 1]]],
            },
            "areas_served": ["Bay A"],
            "email_notifications_enabled": True,
            "acknowledgment_required": True,
        })
        sent_response = await client.post(
            "/api/intelligence/alerts/alert-1/notifications",
            json={"organization_id": "org-1", "approved": True},
        )
    finally:
        app.dependency_overrides.pop(require_admin_user, None)

    assert org_response.status_code == 201
    assert org_response.json()["verified"] is False
    assert sent_response.status_code == 200
    assert sent_response.json()["delivery_status"] == "SENT"
