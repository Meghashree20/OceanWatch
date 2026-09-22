import pytest

from app.ml.recommendation import score_hotspot


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