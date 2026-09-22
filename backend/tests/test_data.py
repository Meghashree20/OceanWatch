import httpx
import pytest

from app.main import app
from app.services.data_service import DataService


OBSERVATION = {
    "unique_id": "TEST-1",
    "sample_date": "2024-01-01T00:00:00",
    "latitude": 10.0,
    "longitude": 20.0,
    "measurement": 1.5,
    "unit": "pieces/m3",
}


@pytest.mark.asyncio
async def test_data_endpoints(monkeypatch):
    async def import_data(_path):
        return {"status": "success", "total_documents": 1}

    async def get_observations(**_kwargs):
        return {"data": [OBSERVATION], "total": 1, "skip": 0, "limit": 100}

    async def get_stats():
        return {"total_observations": 1}

    async def get_observation_by_id(_unique_id):
        return OBSERVATION

    monkeypatch.setattr(DataService, "import_data", import_data)
    monkeypatch.setattr(DataService, "get_observations", get_observations)
    monkeypatch.setattr(DataService, "get_stats", get_stats)
    monkeypatch.setattr(DataService, "get_observation_by_id", get_observation_by_id)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/data/import")).status_code == 200
        assert (await client.get("/api/data")).status_code == 200
        assert (await client.get("/api/data/stats")).json() == {"total_observations": 1}
        assert (await client.get("/api/data/TEST-1")).status_code == 200


@pytest.mark.asyncio
async def test_data_query_validation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/data?start_date=2024-02-01&end_date=2024-01-01")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "http_400"


@pytest.mark.asyncio
async def test_date_query_accepts_datetime_and_date_only_end(monkeypatch):
    captured = {}

    async def get_observations(**kwargs):
        captured.update(kwargs)
        return {"data": [], "total": 0, "skip": 0, "limit": 100}

    monkeypatch.setattr(DataService, "get_observations", get_observations)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/data?start_date=2024-01-01T00:00:00Z&end_date=2024-01-01")
    assert response.status_code == 200
    assert captured["end_date"].hour == 23
    assert captured["end_date"].tzinfo is not None


@pytest.mark.asyncio
async def test_invalid_date_format_returns_bad_request():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/data?start_date=not-a-date")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "http_400"