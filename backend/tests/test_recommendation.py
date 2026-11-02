import pytest

from app.ml.recommendation import (
    DEFAULT_WEIGHTS,
    TREND_ADJUSTMENT_WEIGHT,
    _priority_level,
    calculate_trend_score,
    score_hotspot,
)


def _hotspot():
    return {"cluster_id": 7, "severity": "HIGH", "observation_count": 50, "average_pollution": 10.0}


def test_priority_score_is_transparent_and_uses_configured_weights():
    result = score_hotspot(_hotspot(), ecological_risk=80, human_exposure=60, cleanup_feasibility=40)
    assert result["priority_score"] == 78.0
    assert result["priority_level"] == "CRITICAL"
    assert result["factor_scores"]["observation_density"]["score"] == 50.0
    assert result["weighted_components"] == {
        "pollution_severity": 40.0,
        "ecological_risk": 20.0,
        "human_exposure": 12.0,
        "cleanup_feasibility": 6.0,
    }
    assert result["recommended_action"] == "Immediate cleanup assessment"
    assert result["status"] == "calculated"
    assert result["contributions"] == result["weighted_components"]
    assert result["trend_adjustment"] == 0.0
    assert result["weights"] == DEFAULT_WEIGHTS


def test_missing_context_is_not_fabricated():
    result = score_hotspot(_hotspot())
    assert result["priority_score"] is None
    assert result["priority_level"] == "UNAVAILABLE"
    assert result["status"] == "context_required"
    assert result["missing_external_factors"] == ["ecological_risk", "human_exposure", "cleanup_feasibility"]
    assert result["factor_scores"]["ecological_risk"]["source"] == "External/contextual input"


def test_context_scores_must_be_between_zero_and_one_hundred():
    with pytest.raises(ValueError, match="human_exposure"):
        score_hotspot(_hotspot(), ecological_risk=50, human_exposure=101, cleanup_feasibility=50)


def _fully_contextual_score(forecast_values=None, historical_value=None):
    return score_hotspot(
        _hotspot(),
        ecological_risk=80,
        human_exposure=60,
        cleanup_feasibility=40,
        forecast_values=forecast_values,
        historical_value=historical_value,
    )


def test_forecast_trend_changes_trend_score_and_priority():
    increasing = _fully_contextual_score([12.0, 14.0, 16.0], historical_value=10.0)
    decreasing = _fully_contextual_score([8.0, 6.0, 4.0], historical_value=10.0)

    assert increasing["factor_scores"]["trend_increase"]["score"] == 70.0
    assert decreasing["factor_scores"]["trend_increase"]["score"] == 30.0
    assert increasing["trend_adjustment"] == 5.0
    assert decreasing["trend_adjustment"] == -5.0
    assert increasing["priority_score"] > decreasing["priority_score"]


def test_missing_forecast_uses_neutral_fallback_and_preserves_existing_score():
    result = _fully_contextual_score()

    assert result["factor_scores"]["trend_increase"]["score"] == 50.0
    assert "neutral fallback" in result["factor_scores"]["trend_increase"]["source"]
    assert result["trend_adjustment"] == 0.0
    assert result["priority_score"] == 78.0


def test_negative_forecast_trend_is_clamped_and_final_score_stays_bounded():
    trend = calculate_trend_score([-10.0, -5.0], historical_value=10.0)
    low = score_hotspot(
        {**_hotspot(), "average_pollution": 0.0},
        ecological_risk=0,
        human_exposure=0,
        cleanup_feasibility=0,
        forecast_values=[-10.0],
        historical_value=10.0,
    )
    high = score_hotspot(
        {**_hotspot(), "average_pollution": 10.0},
        ecological_risk=100,
        human_exposure=100,
        cleanup_feasibility=100,
        forecast_values=[1000.0],
        historical_value=1.0,
        pollution_reference={"min": 0.0, "max": 10.0},
    )

    assert trend["score"] == 0.0
    assert low["priority_score"] == 0.0
    assert high["priority_score"] == 100.0
    assert 0.0 <= low["priority_score"] <= 100.0
    assert 0.0 <= high["priority_score"] <= 100.0


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "LOW"), (25, "LOW"), (25.01, "MEDIUM"), (50, "MEDIUM"),
     (50.01, "HIGH"), (75, "HIGH"), (75.01, "CRITICAL"), (100, "CRITICAL")],
)
def test_priority_category_boundaries_remain_unchanged(score, expected):
    assert _priority_level(score) == expected


def test_trend_adjustment_uses_reference_weight_without_changing_existing_weights():
    assert TREND_ADJUSTMENT_WEIGHT == 0.25
    assert DEFAULT_WEIGHTS == {
        "pollution_severity": 0.40,
        "ecological_risk": 0.25,
        "human_exposure": 0.20,
        "cleanup_feasibility": 0.15,
    }


@pytest.mark.asyncio
async def test_recommendation_service_uses_phase5_forecast_contract(monkeypatch):
    from app.services.forecast_service import ForecastService
    from app.services.recommendation_service import RecommendationService

    async def get_hotspots(**_kwargs):
        return [{**_hotspot(), "region": "North", "detection_run_id": "run-1"}]

    async def forecast(zone, horizon):
        assert zone == "North"
        assert horizon == 3
        return {
            "zone": zone,
            "horizon": horizon,
            "metric": "microplastic_concentration",
            "unit": "pieces/m3",
            "historical_values": [{"date": "2024-01-01", "value": 10.0}],
            "predicted_values": [
                {"date": "2024-02-01", "value": 12.0},
                {"date": "2024-03-01", "value": 14.0},
            ],
        }

    monkeypatch.setattr(RecommendationService, "_get_hotspots", get_hotspots)
    monkeypatch.setattr(ForecastService, "forecast", forecast)

    result = await RecommendationService.get_recommendation(
        7,
        ecological_risk=80,
        human_exposure=60,
        cleanup_feasibility=40,
    )

    assert result["factor_scores"]["trend_increase"]["score"] == 65.0
    assert result["trend_adjustment"] == 3.75
    assert result["priority_score"] == 81.75


@pytest.mark.asyncio
async def test_missing_model_uses_fallback_in_recommendation_service(monkeypatch):
    from app.services.forecast_service import ForecastService
    from app.services.recommendation_service import RecommendationService

    async def get_hotspots(**_kwargs):
        return [{**_hotspot(), "region": "North"}]

    async def forecast(_zone, horizon):
        assert horizon == 3
        raise FileNotFoundError("forecast not trained")

    monkeypatch.setattr(RecommendationService, "_get_hotspots", get_hotspots)
    monkeypatch.setattr(ForecastService, "forecast", forecast)

    result = await RecommendationService.get_recommendation(
        7,
        ecological_risk=80,
        human_exposure=60,
        cleanup_feasibility=40,
    )

    assert result["priority_score"] == 78.0
    assert result["factor_scores"]["trend_increase"]["score"] == 50.0