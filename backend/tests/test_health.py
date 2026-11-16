import httpx
import pytest

from app.db.mongodb import db_client
from app.main import app, lifespan


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_endpoint_requires_successful_startup(monkeypatch):
    monkeypatch.setattr(db_client, "client", None)
    monkeypatch.setattr(app.state, "startup_ready", False, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/ready")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_staging_startup_fails_closed_when_mongodb_is_unavailable(monkeypatch):
    async def unavailable():
        raise RuntimeError("test-only connection failure")

    async def no_op_close():
        return None

    monkeypatch.setattr("app.main.settings.OCEANWATCH_ENV", "staging")
    monkeypatch.setattr("app.main.connect_to_mongo", unavailable)
    monkeypatch.setattr("app.main.close_mongo_connection", no_op_close)

    with pytest.raises(RuntimeError, match="requires MongoDB connectivity"):
        async with lifespan(app):
            pytest.fail("A staging app must not start without MongoDB.")