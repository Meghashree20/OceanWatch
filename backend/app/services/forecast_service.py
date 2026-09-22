"""Forecast orchestration for monthly region-level pollution data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from app.db.mongodb import db_client
from app.ml.forecast_model import FORECAST_LABEL, ForecastConfig, aggregate_monthly, create_features, load_artifact, save_artifact, train_forecast_model


MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "pollution_forecast.joblib"
OBSERVATION_COLLECTION = "pollution_observations"


class ForecastService:
    @staticmethod
    async def _load_monthly() -> pd.DataFrame:
        cursor = db_client.db[OBSERVATION_COLLECTION].find({}, {"_id": 0, "sample_date": 1, "measurement": 1, "latitude": 1, "longitude": 1, "region": 1})
        return aggregate_monthly(await cursor.to_list(length=None))

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
        return {"status": "ready", "metrics": artifact["metrics"], "validation_metrics": artifact["validation_metrics"], "selected_params": artifact["selected_params"], "periods": artifact["periods"], "coverage": artifact["coverage"], "aggregation": artifact["aggregation"], "zones": artifact["zones"], "train_rows": artifact["train_rows"], "validation_rows": artifact["validation_rows"], "test_rows": artifact["test_rows"], "message": artifact["label"]}

    @staticmethod
    async def forecast(zone: str, horizon: int) -> Dict[str, Any]:
        if not MODEL_PATH.exists():
            raise FileNotFoundError("Train the forecasting model first.")
        artifact = load_artifact(str(MODEL_PATH))
        if zone not in artifact["zones"]:
            raise ValueError(f"Zone '{zone}' is not available in the trained model.")
        history = (await ForecastService._load_monthly()).query("region == @zone").sort_values("period")
        if history.empty:
            raise ValueError(f"No observations found for zone '{zone}'.")
        if create_features(history).empty:
            raise ValueError(f"Zone '{zone}' does not have enough history for lag features.")
        latest = history.iloc[-1]
        values = history["value"].tolist()
        predictions = []
        for offset in range(1, horizon + 1):
            forecast_date = latest["period"] + pd.DateOffset(months=offset)
            recent = values[-6:]
            row = pd.DataFrame([{"year": forecast_date.year, "month": forecast_date.month, "quarter": forecast_date.quarter, "lag_1": recent[-1], "lag_2": recent[-2] if len(recent) >= 2 else recent[-1], "lag_3": recent[-3] if len(recent) >= 3 else recent[-1], "rolling_mean_3": sum(recent[-3:]) / min(3, len(recent)), "rolling_mean_6": sum(recent) / len(recent), "latitude": latest["latitude"], "longitude": latest["longitude"], "region": zone}])
            prediction = max(0.0, float(artifact["pipeline"].predict(row)[0]))
            values.append(prediction)
            predictions.append({"date": forecast_date.strftime("%Y-%m-%d"), "value": prediction})
        historical_values = [{"date": row.period.strftime("%Y-%m-%d"), "value": float(row.value)} for row in history.tail(12).itertuples()]
        return {"zone": zone, "horizon": horizon, "historical_values": historical_values, "predicted_values": predictions, "forecast_dates": [item["date"] for item in predictions], "model_metrics": artifact["metrics"], "message": FORECAST_LABEL}