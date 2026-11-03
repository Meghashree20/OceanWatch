import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import require_active_user
from app.main import app
from app.models.user import User


PROTECTED_REQUESTS = [
    ("GET", "/api/data/stats"),
    ("GET", "/api/hotspots/stats"),
    ("GET", "/api/forecast/model-metrics"),
    ("GET", "/api/recommendations"),
    ("GET", "/api/satellite/catalog"),
]


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), PROTECTED_REQUESTS)
async def test_protected_api_routes_reject_missing_authentication(client, method, path):
    response = await client.request(method, path)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_remains_public(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_authenticated_session_reaches_protected_endpoint(client):
    async def override_active_user():
        return User(
            user_id="authenticated-user",
            full_name="Authenticated User",
            email="user@example.com",
            password_hash="not-used",
        )

    app.dependency_overrides[require_active_user] = override_active_user
    try:
        response = await client.get("/api/forecast/model-metrics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code != 401
