"""Forecast orchestration for monthly region-level pollution data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from app.db.mongodb import db_client
from app.ml.forecast_model import (
    FORECAST_LABEL,
    FORECAST_FEATURE_VERSION,
    FORECAST_METRIC,
    FORECAST_UNIT,
    ForecastConfig,
    aggregate_monthly,
    load_artifact,
    save_artifact,
    train_forecast_model,
)
from app.services.observation_service import ObservationService


MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "pollution_forecast.joblib"
OBSERVATION_COLLECTION = "pollution_observations"


def noaa_forecast_records(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Adapt only NOAA concentration records in the trained model's unit."""
    normalized_records = []
    for record in records:
        if str(record.get("unit", "")).strip().lower() != FORECAST_UNIT:
            continue
        observation = ObservationService.from_noaa(record)
        if observation.metric != FORECAST_METRIC or observation.unit.strip().lower() != FORECAST_UNIT:
            continue
        normalized_records.append({
            "sample_date": observation.observed_at,
            "measurement": observation.value,
            "latitude": observation.latitude,
            "longitude": observation.longitude,
            "region": observation.region,
        })
    return normalized_records


class ForecastService:
    @staticmethod
    async def _load_monthly() -> pd.DataFrame:
        cursor = db_client.db[OBSERVATION_COLLECTION].find(
            {},
            {
                "_id": 0,
                "unique_id": 1,
                "sample_date": 1,
                "measurement": 1,
                "unit": 1,
                "latitude": 1,
                "longitude": 1,
                "region": 1,
                "ocean": 1,
                "country": 1,
            },
        )
        records = await cursor.to_list(length=None)
        return aggregate_monthly(noaa_forecast_records(records))

    @staticmethod
    async def train(min_periods: int = 6) -> Dict[str, Any]:
        artifact = train_forecast_model(await ForecastService._load_monthly(), ForecastConfig(min_periods=min_periods))
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = MODEL_PATH.with_suffix(".joblib.tmp")
        save_artifact(artifact, str(temporary_path))
        temporary_path.replace(MODEL_PATH)
        return {"status": "success", "message": f"{FORECAST_LABEL} model trained and saved.", "aggregation": artifact["aggregation"], "zones": artifact["zones"], "metrics": artifact["metrics"], "validation_metrics": artifact["validation_metrics"], "selected_params": artifact["selected_params"], "periods": artifact["periods"], "coverage": artifact["coverage"], "train_rows": artifact["train_rows"], "validation_rows": artifact["validation_rows"], "test_rows": artifact["test_rows"]}

    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        if not MODEL_PATH.exists():
            return {"status": "not_trained", "message": "Train the forecasting model first."}
        artifact = load_artifact(str(MODEL_PATH))
        if artifact.get("feature_version") != FORECAST_FEATURE_VERSION:
            return {
                "status": "not_trained",
                "message": "The saved forecast model uses incompatible features. Retrain the model.",
            }
        return {"status": "ready", "metrics": artifact["metrics"], "validation_metrics": artifact["validation_metrics"], "selected_params": artifact["selected_params"], "periods": artifact["periods"], "coverage": artifact["coverage"], "aggregation": artifact["aggregation"], "zones": artifact["zones"], "train_rows": artifact["train_rows"], "validation_rows": artifact["validation_rows"], "test_rows": artifact["test_rows"], "message": artifact["label"]}

    @staticmethod
    async def forecast(zone: str, horizon: int) -> Dict[str, Any]:
        if not MODEL_PATH.exists():
            raise FileNotFoundError("Train the forecasting model first.")
        artifact = load_artifact(str(MODEL_PATH))
        if artifact.get("feature_version") != FORECAST_FEATURE_VERSION:
            raise FileNotFoundError("The saved forecast model uses incompatible features. Retrain the model.")
        history = (await ForecastService._load_monthly()).query("region == @zone").sort_values("period")
        if history.empty:
            raise ValueError(f"No observations found for zone '{zone}'.")
        recent_periods = history["period"].tail(6).dt.to_period("M").astype("int64")
        if len(recent_periods) < 6 or not recent_periods.diff().dropna().eq(1).all():
            raise ValueError(f"Zone '{zone}' needs six consecutive monthly observations to forecast.")
        evaluation = artifact.get("region_evaluation", {}).get(zone, {})
        model_regions = artifact.get("deployment_training_regions", [])
        use_xgboost = evaluation.get("strategy") == "xgboost" and zone in model_regions
        latest = history.iloc[-1]
        values = history["value"].tolist()
        predictions = []
        for offset in range(1, horizon + 1):
            forecast_date = latest["period"] + pd.DateOffset(months=offset)
            if use_xgboost:
                recent = values[-6:]
                row = pd.DataFrame([{"year": forecast_date.year, "month": forecast_date.month, "quarter": forecast_date.quarter, "lag_1": recent[-1], "lag_2": recent[-2] if len(recent) >= 2 else recent[-1], "lag_3": recent[-3] if len(recent) >= 3 else recent[-1], "rolling_mean_3": sum(recent[-3:]) / min(3, len(recent)), "rolling_mean_6": sum(recent) / len(recent), "latitude": latest["latitude"], "longitude": latest["longitude"], "region": zone}])
                prediction = float(artifact["pipeline"].predict(row)[0])
            else:
                prediction = float(values[-1])
            prediction = max(0.0, prediction)
            values.append(prediction)
            predictions.append({"date": forecast_date.strftime("%Y-%m-%d"), "value": prediction})
        historical_values = [{"date": row.period.strftime("%Y-%m-%d"), "value": float(row.value)} for row in history.tail(12).itertuples()]
        return {
            "zone": zone,
            "horizon": horizon,
            "metric": FORECAST_METRIC,
            "unit": FORECAST_UNIT,
            "historical_values": historical_values,
            "predicted_values": predictions,
            "forecast_dates": [item["date"] for item in predictions],
            "model_metrics": artifact["metrics"],
            "message": FORECAST_LABEL if use_xgboost else "persistence baseline forecast; XGBoost reliability criteria were not met",
        }