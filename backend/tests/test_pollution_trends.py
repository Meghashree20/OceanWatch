from datetime import datetime, timezone

import pytest

from app.ml.pollution_trends import PollutionTrendConfig, analyze_pollution_trends


def _record(day, measurement, latitude=10.2, longitude=20.2, unit="pieces/m3"):
    return {
        "sample_date": f"2024-06-{day:02d}T12:00:00Z",
        "latitude": latitude,
        "longitude": longitude,
        "measurement": measurement,
        "unit": unit,
    }


def test_trend_compares_equal_windows_and_marks_new_high_risk():
    rows = [
        _record(2, 1), _record(3, 1), _record(4, 9),
        _record(20, 1), _record(21, 20), _record(22, 20),
    ]
    result = analyze_pollution_trends(
        rows,
        PollutionTrendConfig(window_days=15, min_observations=3),
    )

    trend = result["trends"][0]
    assert result["status"] == "ready"
    assert trend["risk_level"] == "HIGH"
    assert trend["change_types"] == ["newly_high_risk", "increasing_pollution"]
    assert trend["comparison"]["previous_risk_level"] == "MEDIUM"
    assert trend["evidence"]["recent_observation_count"] == 3
    assert trend["source"] == "observed NOAA microplastic measurements"
    assert result["windows"]["days_per_window"] == 15


def test_repeated_samples_at_one_site_do_not_overweight_site_mean():
    rows = [
        _record(2, 0, 10.2, 20.2), _record(3, 0, 10.2, 20.2),
        _record(4, 10, 10.3, 20.3),
        _record(20, 0, 10.2, 20.2),
        _record(21, 10, 10.3, 20.3), _record(22, 10, 10.3, 20.3),
        _record(23, 10, 10.3, 20.3), _record(24, 10, 10.3, 20.3),
    ]
    result = analyze_pollution_trends(
        rows,
        PollutionTrendConfig(window_days=15, min_observations=3),
    )

    trend = result["trends"][0]
    assert trend["comparison"]["previous_mean_pieces_m3"] == 5.0
    assert trend["comparison"]["recent_mean_pieces_m3"] == 5.0
    assert trend["trend_direction"] == "stable"


def test_missing_baseline_is_not_reported_as_zero_or_emerging():
    result = analyze_pollution_trends(
        [_record(20, 50), _record(21, 50), _record(22, 50)],
        PollutionTrendConfig(window_days=15, min_observations=3),
    )

    trend = result["trends"][0]
    assert trend["comparison"]["previous_mean_pieces_m3"] is None
    assert trend["comparison"]["absolute_change_pieces_m3"] is None
    assert trend["change_types"] == ["no_comparable_baseline"]
    assert trend["trend_direction"] == "unknown"
    assert trend["evidence"]["baseline_available"] is False


def test_missing_period_observations_are_not_imputed_as_zero():
    result = analyze_pollution_trends(
        [_record(1, 50), _record(2, 50), _record(3, 50)],
        PollutionTrendConfig(window_days=15, min_observations=3),
    )

    assert result["status"] == "ready"
    assert result["trends"][0]["comparison"]["previous_mean_pieces_m3"] is None
    assert result["trends"][0]["change_types"] == ["no_comparable_baseline"]


def test_invalid_and_incompatible_observations_are_excluded():
    result = analyze_pollution_trends(
        [
            _record(20, 50, unit="percent"),
            {**_record(21, 50), "latitude": 91},
            {**_record(22, -1)},
        ],
        PollutionTrendConfig(window_days=15, min_observations=1),
    )

    assert result["status"] == "insufficient_data"
    assert result["coverage"]["valid_observations"] == 0
    assert result["coverage"]["excluded_observations"] == 3


def test_invalid_risk_threshold_order_is_rejected():
    config = PollutionTrendConfig(
        risk_thresholds={"MEDIUM": 10, "HIGH": 1, "CRITICAL": 100},
    )
    with pytest.raises(ValueError, match="MEDIUM < HIGH < CRITICAL"):
        analyze_pollution_trends([], config)


def test_future_records_are_not_included_in_requested_reference_time():
    result = analyze_pollution_trends(
        [_record(20, 50), _record(21, 50), _record(22, 50)],
        PollutionTrendConfig(window_days=15, min_observations=1),
        reference_time=datetime(2024, 6, 21, 12, tzinfo=timezone.utc),
    )
    assert result["latest_observation"] == "2024-06-21T12:00:00+00:00"


def test_empty_observation_store_returns_insufficient_data():
    result = analyze_pollution_trends([])
    assert result["status"] == "insufficient_data"
    assert result["trends"] == []
    assert result["data_freshness"]["status"] == "unavailable"


def test_zero_baseline_uses_absolute_risk_threshold_without_fake_percent_change():
    result = analyze_pollution_trends(
        [
            _record(2, 0), _record(3, 0), _record(4, 0),
            _record(20, 1), _record(21, 1), _record(22, 1),
        ],
        PollutionTrendConfig(window_days=15, min_observations=3),
    )
    trend = result["trends"][0]

    assert trend["comparison"]["relative_change"] is None
    assert trend["comparison"]["previous_risk_level"] == "LOW"
    assert trend["risk_level"] == "MEDIUM"
    assert trend["change_types"] == ["increasing_pollution"]


def test_adjacent_low_cell_crossing_high_threshold_is_marked_as_expansion():
    rows = [
        _record(2, 1, 10.2, 20.2), _record(3, 1, 10.2, 20.2), _record(4, 1, 10.2, 20.2),
        _record(2, 20, 10.2, 21.2), _record(3, 20, 10.2, 21.2), _record(4, 20, 10.2, 21.2),
        _record(20, 15, 10.2, 20.2), _record(21, 15, 10.2, 20.2), _record(22, 15, 10.2, 20.2),
    ]
    result = analyze_pollution_trends(
        rows,
        PollutionTrendConfig(window_days=15, min_observations=3),
    )
    expanding_cell = next(
        trend for trend in result["trends"]
        if trend["location"]["longitude"] == 20.5
    )

    assert "expanding_hotspot" in expanding_cell["change_types"]
    assert expanding_cell["evidence"]["adjacent_previous_high_risk_cell"] is True
