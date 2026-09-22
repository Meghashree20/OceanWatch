"""Run reproducible real-data XGBoost forecast validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
INPUT_PATH = BACKEND_DIR / "data" / "processed" / "ocean_water_clean.csv"
RESULT_PATH = BACKEND_DIR / "data" / "processed" / "forecast_experiments.csv"
REPORT_PATH = REPO_DIR / "docs" / "FORECAST_VALIDATION_REPORT.md"
MODEL_PATH = BACKEND_DIR / "models" / "pollution_forecast.joblib"


def load_monthly():
    from app.ml.forecast_model import aggregate_monthly

    frame = pd.read_csv(INPUT_PATH, low_memory=False)
    records = frame.rename(columns={
        "Sample Date": "sample_date",
        "Microplastics Measurement": "measurement",
        "Latitude (degree)": "latitude",
        "Longitude (degree)": "longitude",
        "Region": "region",
    })[["sample_date", "measurement", "latitude", "longitude", "region"]].to_dict("records")
    return aggregate_monthly(records)


def markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "No experiments."
    headers = list(rows[0])
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[header]) for header in headers) + " |")
    return "\n".join(lines)


def main() -> None:
    from app.ml.forecast_model import ForecastConfig, load_artifact, save_artifact, train_forecast_model

    monthly = load_monthly()
    artifact = train_forecast_model(monthly, ForecastConfig(min_periods=6))
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = MODEL_PATH.with_suffix(".joblib.tmp")
    save_artifact(artifact, str(temporary_path))
    temporary_path.replace(MODEL_PATH)

    experiment_rows = []
    for index, experiment in enumerate(artifact["validation_experiments"], start=1):
        row = {"experiment": index, **experiment["params"]}
        row.update({f"validation_xgboost_{key}": value for key, value in experiment["metrics"].items()})
        experiment_rows.append(row)
    pd.DataFrame(experiment_rows).to_csv(RESULT_PATH, index=False)

    report = f"""# Model 2: XGBoost Forecast Validation

Generated from the real cleaned NOAA dataset by
`backend/scripts/run_forecast_validation.py`.

## Objective and data structure

The NOAA observations are irregularly sampled. The model does not treat them as a
daily time series. It forecasts the mean pollution concentration for the next
**observed region-month**. Observations are first aggregated by `region + calendar
month`; regions without the minimum history requirement are excluded.

- Input: `backend/data/processed/ocean_water_clean.csv`
- Monthly aggregated rows: **{len(monthly)}**
- Minimum history requirement: **{artifact['coverage']['minimum_history_periods']} observed monthly periods per region**
- Regions with sufficient history: **{artifact['coverage']['sufficient_history_regions']}**
- Usable time periods: **{artifact['coverage']['usable_time_periods']}**
- Target: next observed region-month mean measurement

## Temporal coverage diagnostics

Observations per region, year, and month are stored in the training artifact under
`coverage`. The artifact is saved at `backend/models/pollution_forecast.joblib`.

```json
{json.dumps(artifact['coverage'], indent=2)}
```

## Features and leakage controls

Features:

```text
{', '.join(artifact['feature_columns'])}
```

Lag and rolling features are shifted by one period before calculation, so only
past observed values are used. Region is one-hot encoded with unknown categories
ignored at inference. The saved Joblib artifact contains the fitted preprocessing
pipeline and feature metadata.

## Chronological split

No random shuffling was used. The split is based on target period:

| Split | Period | Samples |
| --- | --- | ---: |
| Training | {artifact['periods']['training']['start']} to {artifact['periods']['training']['end']} | {artifact['periods']['training']['rows']} |
| Validation | {artifact['periods']['validation']['start']} to {artifact['periods']['validation']['end']} | {artifact['periods']['validation']['rows']} |
| Testing | {artifact['periods']['testing']['start']} to {artifact['periods']['testing']['end']} | {artifact['periods']['testing']['rows']} |

## Controlled hyperparameter validation

Four small XGBoost configurations were evaluated on the validation split, including
one log-target candidate to test whether the strongly right-skewed concentration
target benefits from transformation. The
selected configuration minimized validation RMSE; the selected model was then
refit on training plus validation rows and evaluated once on the test split.

{markdown_table(experiment_rows)}

Selected parameters:

```json
{json.dumps(artifact['selected_params'], indent=2)}
```

## Final test metrics

| Model | MAE | RMSE | R² |
| --- | ---: | ---: | ---: |
| XGBoost | {artifact['metrics']['xgboost']['mae']} | {artifact['metrics']['xgboost']['rmse']} | {artifact['metrics']['xgboost']['r2']} |
| Previous-period baseline | {artifact['metrics']['previous_period_baseline']['mae']} | {artifact['metrics']['previous_period_baseline']['rmse']} | {artifact['metrics']['previous_period_baseline']['r2']} |

Validation metrics used for selection:

```json
{json.dumps(artifact['validation_metrics'], indent=2)}
```

## Baseline comparison and selection reasoning

The baseline predicts the previous observed region-month value. XGBoost was selected
from the controlled candidate set using validation RMSE, without inspecting test
metrics during selection. Final performance is reported against the same baseline
on the untouched chronological test period. If XGBoost is weaker on any metric, that
result is retained rather than hidden.

## Persistence and inference

The final Joblib artifact is saved at:

```text
backend/models/pollution_forecast.joblib
```

It contains the fitted `ColumnTransformer` and XGBoost pipeline, selected parameters,
feature list, aggregation strategy, coverage, split periods, and metrics. The API
loads this artifact for forecast requests; it does not retrain per request.

## Limitations

- Region coverage is uneven and many source observations have missing region metadata,
  which are represented as `Unknown`.
- The forecast target is an observed region-month aggregation, not a daily physical
  process and not a guarantee of future pollution.
- Missing calendar months are not imputed; lags refer to previous observed rows.
- The concentration distribution is highly skewed, which can make RMSE and R²
  sensitive to extreme measurements.
- This is an empirical validation on one NOAA dataset and does not establish
  scientific or operational forecasting validity.
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {RESULT_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {MODEL_PATH}")


if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND_DIR))
    main()
