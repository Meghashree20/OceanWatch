import pandas as pd

from app.ml.forecast_model import ForecastConfig, aggregate_monthly, chronological_split, create_features, train_forecast_model


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