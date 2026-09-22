import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_service import DataService
from app.services.forecast_service import ForecastService
from app.services.hotspot_service import HotspotService
from app.services.recommendation_service import RecommendationService


OBSERVATION = {
    "unique_id": "OBS-1",
    "sample_date": "2024-01-01T00:00:00",
    "latitude": 10.0,
    "longitude": 20.0,
    "measurement": 12.5,
    "unit": "pieces/m3",
    "region": "Test Region",
}
HOTSPOT = {
    "cluster_id": 1,
    "observation_count": 10,
    "centroid": {"latitude": 10.0, "longitude": 20.0},
    "average_pollution": 12.5,
    "maximum_pollution": 20.0,
    "minimum_pollution": 5.0,
    "pollution_std": 2.0,
    "date_range": {"min": "2024-01-01", "max": "2024-01-31"},
    "region": "Test Region",
    "ocean": "Test Ocean",
    "severity": "HIGH",
    "label": "Potential Pollution Hotspot",
}
RECOMMENDATION = {
    "status": "calculated",
    "hotspot": HOTSPOT,
    "cluster": HOTSPOT,
    "priority_score": 78.0,
    "priority_level": "HIGH",
    "factor_scores": {
        "pollution_severity": {"score": 100.0, "source": "NOAA-derived average_pollution", "normalization": "log1p min-max across selected detection run hotspot averages"},
        "observation_density": {"score": 10.0, "source": "Hotspot observation_count / 100, capped at 100"},
        "ecological_risk": {"score": 80.0, "source": "External/contextual input"},
        "human_exposure": {"score": 60.0, "source": "External/contextual input"},
        "cleanup_feasibility": {"score": 40.0, "source": "External/contextual input"},
    },
    "weighted_components": {"pollution_severity": 40.0, "ecological_risk": 20.0, "human_exposure": 12.0, "cleanup_feasibility": 6.0},
    "contributions": {"pollution_severity": 40.0, "ecological_risk": 20.0, "human_exposure": 12.0, "cleanup_feasibility": 6.0},
    "weights": {"pollution_severity": 0.4, "ecological_risk": 0.25, "human_exposure": 0.2, "cleanup_feasibility": 0.15},
    "recommended_action": "Prioritize cleanup assessment",
    "recommendation": "Prioritize cleanup assessment",
    "calculation_explanation": "Pollution uses log-scaled min-max normalization of actual average pollution values within the selected detection run. External factors are supplied by the caller and are not present in NOAA data.",
    "missing_external_factors": [],
}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_every_required_endpoint(monkeypatch, client):
    async def import_data(_path):
        return {"status": "success", "total_documents": 1}

    async def get_observations(**_kwargs):
        return {"data": [OBSERVATION], "total": 1, "skip": 0, "limit": 100}

    async def get_observation(_unique_id):
        return OBSERVATION

    async def get_data_stats():
        return {"total_observations": 1}

    async def detect_hotspots(**_kwargs):
        return {"status": "success", "total_clusters": 1, "noise_points": 0, "total_observations_used": 10, "eps_km": 200.0, "min_samples": 10, "severity_distribution": {"HIGH": 1}}

    async def get_hotspots(**_kwargs):
        return {"data": [HOTSPOT], "total": 1, "skip": 0, "limit": 100}

    async def get_hotspot_by_id(_cluster_id):
        return HOTSPOT

    async def get_hotspot_stats():
        return {"total_clusters": 1, "total_observations_in_clusters": 10, "severity_distribution": {"HIGH": 1}, "last_run_eps_km": 200.0, "last_run_min_samples": 10}

    async def get_runs(**_kwargs):
        return {"data": [{"run_id": "run-1", "created_at": "2024-01-01T00:00:00Z", "eps_km": 150.0, "min_samples": 10, "dataset_hash": "hash", "total_clusters": 1, "noise_points": 0, "total_observations_used": 10, "severity_distribution": {"HIGH": 1}, "filters": {}, "status": "success"}], "total": 1, "skip": 0, "limit": 100}

    async def get_run(_run_id):
        return {"run_id": "run-1", "created_at": "2024-01-01T00:00:00Z", "eps_km": 150.0, "min_samples": 10, "dataset_hash": "hash", "total_clusters": 1, "noise_points": 0, "total_observations_used": 10, "severity_distribution": {"HIGH": 1}, "filters": {}, "status": "success"}

    async def get_hotspot_by_run_and_id(_run_id, _cluster_id):
        return {**HOTSPOT, "hotspot_id": "run-1:1", "detection_run_id": "run-1", "eps_km": 150.0, "min_samples": 10, "dataset_hash": "hash", "centroid_latitude": 10.0, "centroid_longitude": 20.0, "median_pollution": 12.0, "date_start": "2024-01-01", "date_end": "2024-01-31", "dominant_region": "Test Region", "created_at": "2024-01-01T00:00:00Z"}

    async def train(min_periods=6):
        return {"status": "success", "message": "model-based pollution concentration forecast model trained and saved.", "aggregation": "region + calendar month", "zones": ["Test Region"], "metrics": {}, "train_rows": 1, "validation_rows": 1, "test_rows": 1}

    async def forecast(_zone, _horizon):
        return {"zone": "Test Region", "horizon": 1, "historical_values": [], "predicted_values": [{"date": "2024-02-01", "value": 13.0}], "forecast_dates": ["2024-02-01"], "model_metrics": {}, "message": "model-based pollution concentration forecast"}

    async def get_recommendations(**_kwargs):
        return {"data": [RECOMMENDATION], "total": 1}

    async def get_recommendation(_cluster_id, **_kwargs):
        return RECOMMENDATION

    async def calculate(**_kwargs):
        return RECOMMENDATION

    monkeypatch.setattr(DataService, "import_data", import_data)
    monkeypatch.setattr(DataService, "get_observations", get_observations)
    monkeypatch.setattr(DataService, "get_observation_by_id", get_observation)
    monkeypatch.setattr(DataService, "get_stats", get_data_stats)
    monkeypatch.setattr(HotspotService, "detect_hotspots", detect_hotspots)
    monkeypatch.setattr(HotspotService, "get_hotspots", get_hotspots)
    monkeypatch.setattr(HotspotService, "get_hotspot_by_id", get_hotspot_by_id)
    monkeypatch.setattr(HotspotService, "get_stats", get_hotspot_stats)
    monkeypatch.setattr(HotspotService, "get_runs", get_runs)
    monkeypatch.setattr(HotspotService, "get_run", get_run)
    monkeypatch.setattr(HotspotService, "get_hotspot_by_run_and_id", get_hotspot_by_run_and_id)
    monkeypatch.setattr(ForecastService, "train", train)
    monkeypatch.setattr(ForecastService, "forecast", forecast)
    monkeypatch.setattr(ForecastService, "get_metrics", lambda: {"status": "ready", "metrics": {"xgboost": {"mae": 1.0}}, "message": "model-based pollution concentration forecast"})
    monkeypatch.setattr(RecommendationService, "get_recommendations", get_recommendations)
    monkeypatch.setattr(RecommendationService, "get_recommendation", get_recommendation)
    monkeypatch.setattr(RecommendationService, "calculate", calculate)

    responses = [
        await client.get("/api/health"),
        await client.post("/api/data/import"),
        await client.get("/api/data"),
        await client.get("/api/data/stats"),
        await client.get("/api/data/OBS-1"),
        await client.post("/api/hotspots/detect", json={}),
        await client.get("/api/hotspots"),
        await client.get("/api/hotspots/1"),
        await client.get("/api/hotspots/stats"),
        await client.get("/api/hotspots/runs"),
        await client.get("/api/hotspots/runs/run-1"),
        await client.get("/api/hotspots/runs/run-1/1"),
        await client.post("/api/forecast/train"),
        await client.get("/api/forecast/Test%20Region?horizon=1"),
        await client.get("/api/forecast/model-metrics"),
        await client.get("/api/recommendations?ecological_risk=80&human_exposure=60&cleanup_feasibility=40"),
        await client.get("/api/recommendations/1?ecological_risk=80&human_exposure=60&cleanup_feasibility=40"),
        await client.post("/api/recommendations/calculate", json={"cluster_id": 1, "detection_run_id": "run-1", "ecological_risk": 80, "human_exposure": 60, "cleanup_feasibility": 40}),
    ]
    assert [response.status_code for response in responses] == [200] * 18


@pytest.mark.asyncio
async def test_validation_errors_use_consistent_error_structure(client):
    response = await client.get("/api/data?limit=0")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"