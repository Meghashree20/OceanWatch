import pandas as pd

import app.ml.forecast_model as forecast_model
from app.ml.forecast_model import (
    FORECAST_FEATURE_VERSION,
    ForecastConfig,
    MODEL_CANDIDATES,
    aggregate_monthly,
    chronological_split,
    create_features,
    evaluate_regions,
    train_forecast_model,
)


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
    features = create_features(aggregate_monthly(_records()))
    assert artifact["zones"] == ["North", "South"]
    assert "xgboost" in artifact["metrics"]
    assert "previous_period_baseline" in artifact["metrics"]
    assert len(artifact["validation_experiments"]) == 4
    assert artifact["periods"]["training"]["end"] <= artifact["periods"]["validation"]["start"]
    assert artifact["periods"]["validation"]["end"] <= artifact["periods"]["testing"]["start"]
    assert artifact["feature_columns"]
    assert artifact["feature_version"] == FORECAST_FEATURE_VERSION
    assert artifact["preprocessing"]["aggregation"] == "region + calendar month"
    assert artifact["deployment_training_rows"] == len(features)
    assert artifact["deployment_training_regions"] == ["North", "South"]
    assert artifact["region_evaluation"]["North"]["evaluation_points"] >= 3
    assert artifact["metrics"]["evaluation_strategy"] == "regional expanding windows"
    assert "global_chronological_holdout" in artifact["metrics"]


def test_region_evaluation_uses_expanding_history_and_compares_persistence(monkeypatch):
    fitted_regions = []

    class NextMonthPipeline:
        def fit(self, features, target):
            fitted_regions.append(set(features["region"]))
            return self

        def predict(self, features):
            return features["lag_1"].to_numpy() + 1

    monkeypatch.setattr(forecast_model, "_build_pipeline", lambda params, random_state: NextMonthPipeline())
    features = create_features(aggregate_monthly(_records()))

    regional, predictions = evaluate_regions(
        features,
        ["North", "South"],
        MODEL_CANDIDATES[0],
        ForecastConfig(),
    )

    assert regional["North"]["strategy"] == "xgboost"
    assert regional["South"]["strategy"] == "xgboost"
    assert regional["North"]["evaluation_points"] == 3
    assert regional["North"]["xgboost_mae"] < regional["North"]["persistence_mae"]
    assert set(predictions["region"]) == {"North", "South"}
    assert len(fitted_regions) == len(predictions)
    assert all(region_set == {"North", "South"} for region_set in fitted_regions)
    assert predictions.groupby("region")["target_period"].min().to_dict() == {
        "North": pd.Timestamp("2020-10-01"),
        "South": pd.Timestamp("2020-10-01"),
    }


def test_region_without_enough_evaluation_rows_uses_persistence():
    monthly = aggregate_monthly(_records())
    sparse = monthly[monthly["region"] == "North"].head(8)
    features = create_features(sparse)

    evaluations, predictions = evaluate_regions(
        features,
        ["North"],
        MODEL_CANDIDATES[0],
        ForecastConfig(),
    )

    assert evaluations["North"]["strategy"] == "persistence"
    assert evaluations["North"]["reason"] == "insufficient_history_for_regional_evaluation"
    assert predictions.empty