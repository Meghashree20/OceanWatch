"""Monthly region-level pollution forecasting with XGBoost."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor


FORECAST_LABEL = "model-based pollution concentration forecast"
NUMERIC_FEATURES = ["year", "month", "quarter", "lag_1", "lag_2", "lag_3", "rolling_mean_3", "rolling_mean_6", "latitude", "longitude"]
CATEGORICAL_FEATURES = ["region"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
MODEL_CANDIDATES = [
    {"n_estimators": 300, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"n_estimators": 200, "max_depth": 2, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 1.0},
    {"n_estimators": 400, "max_depth": 3, "learning_rate": 0.03, "subsample": 0.8, "colsample_bytree": 1.0},
    {"n_estimators": 300, "max_depth": 3, "learning_rate": 0.03, "subsample": 0.8, "colsample_bytree": 1.0, "log_target": True},
]


@dataclass
class ForecastConfig:
    min_periods: int = 6
    validation_fraction: float = 0.15
    test_fraction: float = 0.15
    random_state: int = 42


def aggregate_monthly(records: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """Aggregate irregular observations into region and calendar-month rows."""
    frame = pd.DataFrame(list(records))
    required = {"sample_date", "measurement"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Forecast data missing required columns: {sorted(missing)}")
    if frame.empty:
        return pd.DataFrame(columns=["region", "period", "value", "latitude", "longitude", "observation_count"])
    frame["sample_date"] = pd.to_datetime(frame["sample_date"], errors="coerce")
    frame["measurement"] = pd.to_numeric(frame["measurement"], errors="coerce")
    frame = frame.dropna(subset=["sample_date", "measurement"])
    frame["region"] = frame.get("region", pd.Series(index=frame.index)).fillna("Unknown").astype(str)
    frame["period"] = frame["sample_date"].dt.to_period("M").dt.to_timestamp()
    frame["latitude"] = pd.to_numeric(frame.get("latitude"), errors="coerce")
    frame["longitude"] = pd.to_numeric(frame.get("longitude"), errors="coerce")
    return (
        frame.groupby(["region", "period"], as_index=False)
        .agg(value=("measurement", "mean"), latitude=("latitude", "mean"), longitude=("longitude", "mean"), observation_count=("measurement", "size"))
        .sort_values(["region", "period"])
        .reset_index(drop=True)
    )


def create_features(monthly: pd.DataFrame, config: ForecastConfig | None = None) -> pd.DataFrame:
    """Create lagged features and a one-observed-period-ahead target."""
    if monthly.empty:
        return monthly.copy()
    frame = monthly.sort_values(["region", "period"]).copy()
    grouped = frame.groupby("region", group_keys=False)
    frame["year"] = frame["period"].dt.year
    frame["month"] = frame["period"].dt.month
    frame["quarter"] = frame["period"].dt.quarter
    frame["lag_1"] = grouped["value"].shift(1)
    frame["lag_2"] = grouped["value"].shift(2)
    frame["lag_3"] = grouped["value"].shift(3)
    frame["rolling_mean_3"] = grouped["value"].transform(lambda values: values.shift(1).rolling(3).mean())
    frame["rolling_mean_6"] = grouped["value"].transform(lambda values: values.shift(1).rolling(6).mean())
    frame["target"] = grouped["value"].shift(-1)
    frame["target_period"] = grouped["period"].shift(-1)
    frame["baseline_prediction"] = frame["value"]
    return frame.dropna(subset=NUMERIC_FEATURES + ["target", "target_period"]).reset_index(drop=True)


def select_zones(monthly: pd.DataFrame, min_periods: int) -> List[str]:
    counts = monthly.groupby("region")["period"].nunique()
    return sorted(counts[counts >= min_periods].index.tolist())


def chronological_split(frame: pd.DataFrame, config: ForecastConfig) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ordered = frame.sort_values("target_period").reset_index(drop=True)
    periods = ordered["target_period"].drop_duplicates().sort_values().tolist()
    if len(periods) < 3:
        raise ValueError("At least three historical forecast periods are required.")
    test_periods = max(1, int(round(len(periods) * config.test_fraction)))
    validation_periods = max(1, int(round(len(periods) * config.validation_fraction)))
    if validation_periods + test_periods >= len(periods):
        validation_periods = 1
        test_periods = 1
    train_end = len(periods) - validation_periods - test_periods
    train_periods = set(periods[:train_end])
    validation_period_set = set(periods[train_end:train_end + validation_periods])
    test_period_set = set(periods[train_end + validation_periods:])
    return (
        ordered[ordered["target_period"].isin(train_periods)].reset_index(drop=True),
        ordered[ordered["target_period"].isin(validation_period_set)].reset_index(drop=True),
        ordered[ordered["target_period"].isin(test_period_set)].reset_index(drop=True),
    )


def _metrics(actual: pd.Series, predicted: np.ndarray) -> Dict[str, float | None]:
    return {"mae": float(mean_absolute_error(actual, predicted)), "rmse": float(np.sqrt(mean_squared_error(actual, predicted))), "r2": float(r2_score(actual, predicted)) if len(actual) > 1 else None}


def _build_pipeline(params: Dict[str, Any], random_state: int) -> Pipeline:
    model_params = {key: value for key, value in params.items() if key != "log_target"}
    preprocessor = ColumnTransformer([
        ("numeric", "passthrough", NUMERIC_FEATURES),
        ("region", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    model = XGBRegressor(
        **model_params,
        objective="reg:squarederror",
        random_state=random_state,
        n_jobs=1,
    )
    pipeline = Pipeline([("preprocessor", preprocessor), ("model", model)])
    if params.get("log_target"):
        return TransformedTargetRegressor(regressor=pipeline, func=np.log1p, inverse_func=np.expm1)
    return pipeline


def _period_summary(frame: pd.DataFrame) -> Dict[str, Any]:
    return {
        "start": str(frame["target_period"].min().date()),
        "end": str(frame["target_period"].max().date()),
        "rows": int(len(frame)),
    }


def _coverage_summary(monthly: pd.DataFrame, zones: List[str]) -> Dict[str, Any]:
    usable = monthly[monthly["region"].isin(zones)]
    return {
        "observations_per_region": {str(k): int(v) for k, v in monthly.groupby("region")["observation_count"].sum().sort_values(ascending=False).items()},
        "observations_per_month": {str(k): int(v) for k, v in monthly.groupby(monthly["period"].dt.month)["observation_count"].sum().sort_index().items()},
        "observations_per_year": {str(k): int(v) for k, v in monthly.groupby(monthly["period"].dt.year)["observation_count"].sum().sort_index().items()},
        "sufficient_history_regions": len(zones),
        "usable_time_periods": int(usable["period"].nunique()),
        "minimum_history_periods": int(min(monthly.groupby("region")["period"].nunique().loc[zones])) if zones else 0,
    }


def train_forecast_model(monthly: pd.DataFrame, config: ForecastConfig | None = None) -> Dict[str, Any]:
    config = config or ForecastConfig()
    zones = select_zones(monthly, config.min_periods)
    if not zones:
        raise ValueError("No regions have enough monthly observations for training.")
    features = create_features(monthly[monthly["region"].isin(zones)], config)
    if features.empty:
        raise ValueError("No rows remain after creating lag and rolling features.")
    train, validation, test = chronological_split(features, config)
    validation_results = []
    for params in MODEL_CANDIDATES:
        candidate = _build_pipeline(params, config.random_state)
        candidate.fit(train[FEATURE_COLUMNS], train["target"])
        validation_predictions = candidate.predict(validation[FEATURE_COLUMNS])
        validation_results.append({"params": params, "metrics": _metrics(validation["target"], validation_predictions)})
    selected = min(validation_results, key=lambda result: result["metrics"]["rmse"])
    train_validation = pd.concat([train, validation], ignore_index=True)
    pipeline = _build_pipeline(selected["params"], config.random_state)
    pipeline.fit(train_validation[FEATURE_COLUMNS], train_validation["target"])
    predictions = pipeline.predict(test[FEATURE_COLUMNS])
    metrics = {
        "xgboost": _metrics(test["target"], predictions),
        "previous_period_baseline": _metrics(test["target"], test["baseline_prediction"].to_numpy()),
    }
    return {
        "pipeline": pipeline,
        "zones": zones,
        "aggregation": "region + calendar month; one row per observed region-month",
        "config": config.__dict__,
        "selected_params": selected["params"],
        "validation_experiments": validation_results,
        "metrics": metrics,
        "validation_metrics": {"xgboost": selected["metrics"], "previous_period_baseline": _metrics(validation["target"], validation["baseline_prediction"].to_numpy())},
        "train_rows": len(train),
        "validation_rows": len(validation),
        "test_rows": len(test),
        "periods": {"training": _period_summary(train), "validation": _period_summary(validation), "testing": _period_summary(test)},
        "coverage": _coverage_summary(monthly, zones),
        "feature_columns": FEATURE_COLUMNS,
        "preprocessing": {"aggregation": "region + calendar month", "categorical_encoding": "OneHotEncoder(handle_unknown=ignore)", "numeric_features": NUMERIC_FEATURES, "categorical_features": CATEGORICAL_FEATURES, "target": "next observed region-month mean measurement"},
        "latest_period": monthly[monthly["region"].isin(zones)]["period"].max(),
        "label": FORECAST_LABEL,
    }


def save_artifact(artifact: Dict[str, Any], path: str) -> None:
    joblib.dump(artifact, path)


def load_artifact(path: str) -> Dict[str, Any]:
    return joblib.load(path)