import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.mongodb import connect_to_mongo, close_mongo_connection

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await connect_to_mongo()
    yield
    await close_mongo_connection()

@pytest.mark.asyncio
async def test_import_data():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/data/import")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_documents"] > 0

@pytest.mark.asyncio
async def test_get_stats():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_observations" in data
    assert data["total_observations"] > 0

@pytest.mark.asyncio
async def test_get_observations():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert len(data["data"]) <= 10
    
    # Save an ID for the next test
    if len(data["data"]) > 0:
        return data["data"][0]["unique_id"]

@pytest.mark.asyncio
async def test_get_observation_by_id():
    # First get an ID
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        list_response = await ac.get("/api/data?limit=1")
        if list_response.status_code == 200 and list_response.json()["data"]:
            unique_id = list_response.json()["data"][0]["unique_id"]
            
            response = await ac.get(f"/api/data/{unique_id}")
            assert response.status_code == 200
            assert response.json()["unique_id"] == unique_id
