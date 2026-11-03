import pandas as pd
import pytest

from app.ml.forecast_model import (
    FORECAST_METRIC,
    FORECAST_FEATURE_VERSION,
    FORECAST_UNIT,
    ForecastConfig,
    aggregate_monthly,
    chronological_split,
    create_features,
    train_forecast_model,
)
from app.services.forecast_service import ForecastService, noaa_forecast_records


def _records():
    return [
        {"sample_date": f"2020-{month:02d}-15", "measurement": float(month), "latitude": 10.0, "longitude": 20.0, "region": "North"}
        for month in range(1, 13)
    ]


def test_forecasting_uses_monthly_aggregation_and_lags():
    monthly = aggregate_monthly(_records())
    features = create_features(monthly)
    assert len(monthly) == 12
    assert {"year", "month", "quarter", "lag_1", "lag_2", "lag_3", "rolling_mean_3", "rolling_mean_6"}.issubset(features.columns)


def test_forecasting_split_is_chronological_and_reports_metrics():
    features = create_features(aggregate_monthly(_records()))
    train, validation, test = chronological_split(features, ForecastConfig())
    assert train.target_period.max() <= validation.target_period.min() <= test.target_period.min()
    artifact = train_forecast_model(aggregate_monthly(_records()), ForecastConfig(min_periods=6))
    assert "xgboost" in artifact["metrics"]
    assert "previous_period_baseline" in artifact["metrics"]


def test_features_align_calendar_target_and_lags():
    monthly = aggregate_monthly(_records())

    features = create_features(monthly)
    latest = features.iloc[-1]

    assert latest["period"] == pd.Timestamp("2020-11-01")
    assert latest["target_period"] == pd.Timestamp("2020-12-01")
    assert latest["year"] == 2020
    assert latest["month"] == 12
    assert latest["lag_1"] == 11.0
    assert latest["lag_2"] == 10.0
    assert latest["lag_3"] == 9.0
    assert latest["rolling_mean_3"] == 10.0
    assert latest["rolling_mean_6"] == 8.5


def test_feature_creation_does_not_bridge_missing_calendar_months():
    records = [
        {"sample_date": date, "measurement": value, "latitude": 10.0, "longitude": 20.0, "region": "North"}
        for date, value in [
            ("2020-01-15", 1.0), ("2020-02-15", 2.0), ("2020-03-15", 3.0),
            ("2020-05-15", 5.0), ("2020-06-15", 6.0), ("2020-07-15", 7.0),
            ("2020-08-15", 8.0), ("2020-09-15", 9.0), ("2020-10-15", 10.0),
            ("2020-11-15", 11.0), ("2020-12-15", 12.0),
        ]
    ]

    features = create_features(aggregate_monthly(records))

    assert pd.Timestamp("2020-04-01") not in features["target_period"].tolist()
    assert features["target_period"].tolist() == [
        pd.Timestamp("2020-11-01"),
        pd.Timestamp("2020-12-01"),
    ]


def test_aggregation_normalizes_offsets_to_utc_calendar_month():
    monthly = aggregate_monthly([
        {"sample_date": "2020-02-01T00:30:00+02:00", "measurement": 4.0, "latitude": 10, "longitude": 20, "region": "North"},
        {"sample_date": "2020-01-31T22:30:00Z", "measurement": 8.0, "latitude": 10, "longitude": 20, "region": "North"},
    ])

    assert len(monthly) == 1
    assert monthly.iloc[0]["period"] == pd.Timestamp("2020-01-01")
    assert monthly.iloc[0]["value"] == 6.0


def test_noaa_adapter_keeps_only_forecast_metric_unit():
    records = [
        {
            "unique_id": "noaa-1",
            "sample_date": "2020-01-15",
            "latitude": 10.0,
            "longitude": 20.0,
            "measurement": 4.0,
            "unit": "pieces/m3",
            "region": "North",
        },
        {
            "unique_id": "satellite-1",
            "sample_date": "2020-01-15",
            "latitude": 10.0,
            "longitude": 20.0,
            "measurement": 3.0,
            "unit": "percent",
            "region": "North",
        },
    ]

    normalized = noaa_forecast_records(records)

    assert normalized == [{
        "sample_date": pd.Timestamp("2020-01-15", tz="UTC"),
        "measurement": 4.0,
        "latitude": 10.0,
        "longitude": 20.0,
        "region": "North",
    }]
    assert FORECAST_METRIC == "microplastic_concentration"
    assert FORECAST_UNIT == "pieces/m3"


class _IncrementingPipeline:
    def predict(self, frame):
        return frame["lag_1"].to_numpy() + 1


@pytest.mark.asyncio
async def test_forecast_output_is_phase6_consumable(monkeypatch, tmp_path):
    from app.services import forecast_service
    from app.ml.forecast_model import save_artifact

    artifact_path = tmp_path / "forecast.joblib"
    save_artifact({
        "pipeline": _IncrementingPipeline(),
        "zones": ["North"],
        "metrics": {"xgboost": {"mae": 1.0, "rmse": 1.0, "r2": 0.9}},
        "feature_version": FORECAST_FEATURE_VERSION,
        "region_evaluation": {"North": {"strategy": "xgboost"}},
        "deployment_training_regions": ["North"],
    }, str(artifact_path))
    monthly = aggregate_monthly(_records())

    async def load_monthly():
        return monthly

    monkeypatch.setattr(forecast_service, "MODEL_PATH", artifact_path)
    monkeypatch.setattr(ForecastService, "_load_monthly", staticmethod(load_monthly))

    result = await ForecastService.forecast("North", 2)

    assert result["zone"] == "North"
    assert result["metric"] == FORECAST_METRIC
    assert result["unit"] == FORECAST_UNIT
    assert result["forecast_dates"] == ["2021-01-01", "2021-02-01"]
    assert result["predicted_values"] == [
        {"date": "2021-01-01", "value": 13.0},
        {"date": "2021-02-01", "value": 14.0},
    ]
    assert set(result) == {
        "zone", "horizon", "metric", "unit", "historical_values",
        "predicted_values", "forecast_dates", "model_metrics", "message",
    }


class _NegativePipeline:
    def predict(self, frame):
        return [-10.0] * len(frame)


class _UnexpectedPipelineCall:
    def predict(self, frame):
        raise AssertionError("Unsupported regions must use persistence.")


def _forecast_artifact(pipeline, **overrides):
    artifact = {
        "pipeline": pipeline,
        "zones": ["North"],
        "metrics": {"xgboost": {"mae": 1.0, "rmse": 1.0, "r2": 0.9}},
        "feature_version": FORECAST_FEATURE_VERSION,
        "region_evaluation": {},
        "deployment_training_regions": ["North"],
    }
    artifact.update(overrides)
    return artifact


@pytest.mark.asyncio
async def test_unseen_region_uses_persistence_without_xgboost(monkeypatch, tmp_path):
    from app.services import forecast_service
    from app.ml.forecast_model import save_artifact

    artifact_path = tmp_path / "forecast.joblib"
    save_artifact(_forecast_artifact(_UnexpectedPipelineCall()), str(artifact_path))
    south_records = [
        {"sample_date": f"2020-{month:02d}-15", "measurement": float(month), "latitude": -10.0, "longitude": 20.0, "region": "South"}
        for month in range(1, 7)
    ]

    async def load_monthly():
        return aggregate_monthly(south_records)

    monkeypatch.setattr(forecast_service, "MODEL_PATH", artifact_path)
    monkeypatch.setattr(ForecastService, "_load_monthly", staticmethod(load_monthly))

    result = await ForecastService.forecast("South", 3)

    assert result["zone"] == "South"
    assert result["predicted_values"] == [
        {"date": "2020-07-01", "value": 6.0},
        {"date": "2020-08-01", "value": 6.0},
        {"date": "2020-09-01", "value": 6.0},
    ]
    assert result["metric"] == FORECAST_METRIC
    assert result["unit"] == FORECAST_UNIT
    assert result["message"].startswith("persistence baseline forecast")


@pytest.mark.asyncio
async def test_insufficient_model_history_uses_persistence(monkeypatch, tmp_path):
    from app.services import forecast_service
    from app.ml.forecast_model import save_artifact

    artifact_path = tmp_path / "forecast.joblib"
    save_artifact(
        _forecast_artifact(
            _UnexpectedPipelineCall(),
            region_evaluation={
                "North": {
                    "strategy": "persistence",
                    "reason": "insufficient_history_for_regional_evaluation",
                }
            },
        ),
        str(artifact_path),
    )
    monthly = aggregate_monthly(_records())

    async def load_monthly():
        return monthly

    monkeypatch.setattr(forecast_service, "MODEL_PATH", artifact_path)
    monkeypatch.setattr(ForecastService, "_load_monthly", staticmethod(load_monthly))

    result = await ForecastService.forecast("North", 2)

    assert result["predicted_values"] == [
        {"date": "2021-01-01", "value": 12.0},
        {"date": "2021-02-01", "value": 12.0},
    ]


@pytest.mark.asyncio
async def test_xgboost_predictions_are_clamped_non_negative(monkeypatch, tmp_path):
    from app.services import forecast_service
    from app.ml.forecast_model import save_artifact

    artifact_path = tmp_path / "forecast.joblib"
    save_artifact(
        _forecast_artifact(
            _NegativePipeline(),
            region_evaluation={"North": {"strategy": "xgboost"}},
        ),
        str(artifact_path),
    )
    monthly = aggregate_monthly(_records())

    async def load_monthly():
        return monthly

    monkeypatch.setattr(forecast_service, "MODEL_PATH", artifact_path)
    monkeypatch.setattr(ForecastService, "_load_monthly", staticmethod(load_monthly))

    result = await ForecastService.forecast("North", 3)

    assert [item["value"] for item in result["predicted_values"]] == [0.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_forecast_rejects_nonconsecutive_recent_history(monkeypatch, tmp_path):
    from app.services import forecast_service
    from app.ml.forecast_model import save_artifact

    artifact_path = tmp_path / "forecast.joblib"
    save_artifact({
        "pipeline": _IncrementingPipeline(),
        "zones": ["North"],
        "metrics": {},
        "feature_version": FORECAST_FEATURE_VERSION,
    }, str(artifact_path))
    records = _records()
    records.pop(8)
    monthly = aggregate_monthly(records)

    async def load_monthly():
        return monthly

    monkeypatch.setattr(forecast_service, "MODEL_PATH", artifact_path)
    monkeypatch.setattr(ForecastService, "_load_monthly", staticmethod(load_monthly))

    with pytest.raises(ValueError, match="consecutive monthly observations"):
        await ForecastService.forecast("North", 1)


@pytest.mark.asyncio
async def test_forecast_rejects_artifact_with_old_feature_contract(monkeypatch, tmp_path):
    from app.services import forecast_service
    from app.ml.forecast_model import save_artifact

    artifact_path = tmp_path / "old-forecast.joblib"
    save_artifact({"pipeline": _IncrementingPipeline(), "zones": ["North"]}, str(artifact_path))
    monkeypatch.setattr(forecast_service, "MODEL_PATH", artifact_path)

    with pytest.raises(FileNotFoundError, match="incompatible features"):
        await ForecastService.forecast("North", 1)