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