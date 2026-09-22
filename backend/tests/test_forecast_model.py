import pandas as pd

from app.ml.forecast_model import ForecastConfig, aggregate_monthly, chronological_split, create_features, train_forecast_model


def _records():
    records = []
    for region, base in [("North", 10.0), ("South", 20.0)]:
        for month in range(1, 13):
            records.append({"sample_date": f"2020-{month:02d}-15", "measurement": base + month, "latitude": 10.0 if region == "North" else -10.0, "longitude": 20.0, "region": region})
    return records


def test_aggregate_monthly_does_not_treat_observations_as_daily():
    records = _records()
    records.append({**records[0], "sample_date": "2020-01-20", "measurement": 30.0})
    monthly = aggregate_monthly(records)
    january_north = monthly[(monthly.region == "North") & (monthly.period == pd.Timestamp("2020-01-01"))]
    assert len(january_north) == 1
    assert january_north.iloc[0].value == 20.5
    assert january_north.iloc[0].observation_count == 2


def test_features_have_lags_and_chronological_split():
    features = create_features(aggregate_monthly(_records()))
    assert {"year", "month", "quarter", "lag_1", "lag_2", "lag_3", "rolling_mean_3", "rolling_mean_6"}.issubset(features.columns)
    train, validation, test = chronological_split(features, ForecastConfig())
    assert train.target_period.max() <= validation.target_period.min()
    assert validation.target_period.max() <= test.target_period.min()


def test_train_forecast_model_reports_baseline_metrics():
    artifact = train_forecast_model(aggregate_monthly(_records()), ForecastConfig(min_periods=6))
    assert artifact["zones"] == ["North", "South"]
    assert "xgboost" in artifact["metrics"]
    assert "previous_period_baseline" in artifact["metrics"]
    assert len(artifact["validation_experiments"]) == 4
    assert artifact["periods"]["training"]["end"] <= artifact["periods"]["validation"]["start"]
    assert artifact["periods"]["validation"]["end"] <= artifact["periods"]["testing"]["start"]
    assert artifact["feature_columns"]
    assert artifact["preprocessing"]["aggregation"] == "region + calendar month"