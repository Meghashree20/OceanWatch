# Model 2: XGBoost Forecast Validation

Generated from the real cleaned NOAA dataset by
`backend/scripts/run_forecast_validation.py`.

## Objective and data structure

The NOAA observations are irregularly sampled. The model does not treat them as a
daily time series. It forecasts the mean pollution concentration for the next
**observed region-month**. Observations are first aggregated by `region + calendar
month`; regions without the minimum history requirement are excluded.

- Input: `backend/data/processed/ocean_water_clean.csv`
- Monthly aggregated rows: **489**
- Minimum history requirement: **6 observed monthly periods per region**
- Regions with sufficient history: **22**
- Usable time periods: **165**
- Target: next observed region-month mean measurement

## Temporal coverage diagnostics

Observations per region, year, and month are stored in the training artifact under
`coverage`. The artifact is saved at `backend/models/pollution_forecast.joblib`.

```json
{
  "observations_per_region": {
    "Unknown": 3559,
    "Mediterranean Sea": 1183,
    "Inner Seas off the West Coast of Scotland": 261,
    "North Sea": 255,
    "Gulf of America (formerly Gulf of Mexico)": 215,
    "Celtic Sea": 147,
    "Philippine Sea": 129,
    "Coral Sea": 105,
    "South China Sea": 100,
    "Bay of Bengal": 96,
    "Tasman Sea": 90,
    "Laccadive Sea": 72,
    "Great Australian Bight": 48,
    "Caribbean Sea": 44,
    "Greenland Sea": 43,
    "Arabian Sea": 43,
    "Kara Sea": 42,
    "Laptev Sea": 39,
    "Bay of Biscay": 36,
    "Norwegian Sea": 35,
    "Black Sea": 34,
    "East China Sea": 30,
    "East Siberian Sea": 25,
    "Irish Sea and St. George's Channel": 22,
    "Mozambique Channel": 20,
    "Davis Strait": 19,
    "Arafura Sea": 18,
    "English Channel": 17,
    "Andaman Sea": 15,
    "Barentsz Sea": 15,
    "Baltic Sea": 14,
    "Northwestern Passages": 14,
    "Timor Sea": 11,
    "Gulf of St. Lawrence": 11,
    "Baffin Bay": 9,
    "Solomon Sea": 6,
    "Bering Sea": 6,
    "Beaufort Sea": 5,
    "White Sea": 5,
    "Kattegat": 4,
    "Barents Sea": 4,
    "Labrador Sea": 3,
    "Molukka Sea": 3,
    "Halmahera Sea": 3,
    "Skagerrak Strait": 3,
    "Chukchi Sea": 2,
    "Bismarck Sea": 2,
    "Rio de La Plata": 2,
    "Sulu Sea": 2,
    "Celebes Sea": 1
  },
  "observations_per_month": {
    "1": 579,
    "2": 421,
    "3": 338,
    "4": 481,
    "5": 400,
    "6": 661,
    "7": 739,
    "8": 962,
    "9": 574,
    "10": 833,
    "11": 551,
    "12": 328
  },
  "observations_per_year": {
    "2010": 315,
    "2011": 591,
    "2012": 644,
    "2013": 973,
    "2014": 534,
    "2015": 790,
    "2016": 368,
    "2017": 454,
    "2018": 616,
    "2019": 589,
    "2020": 261,
    "2021": 264,
    "2022": 234,
    "2023": 141,
    "2024": 93
  },
  "sufficient_history_regions": 22,
  "usable_time_periods": 165,
  "minimum_history_periods": 6
}
```

## Features and leakage controls

Features:

```text
year, month, quarter, lag_1, lag_2, lag_3, rolling_mean_3, rolling_mean_6, latitude, longitude, region
```

Lag and rolling features are shifted by one period before calculation, so only
past observed values are used. Region is one-hot encoded with unknown categories
ignored at inference. The saved Joblib artifact contains the fitted preprocessing
pipeline and feature metadata.

## Chronological split

No random shuffling was used. The split is based on target period:

| Split | Period | Samples |
| --- | --- | ---: |
| Training | 2010-09-01 to 2020-01-01 | 181 |
| Validation | 2020-02-01 to 2022-04-01 | 48 |
| Testing | 2022-05-01 to 2024-10-01 | 47 |

## Controlled hyperparameter validation

Four small XGBoost configurations were evaluated on the validation split, including
one log-target candidate to test whether the strongly right-skewed concentration
target benefits from transformation. The
selected configuration minimized validation RMSE; the selected model was then
refit on training plus validation rows and evaluated once on the test split.

| experiment | n_estimators | max_depth | learning_rate | subsample | colsample_bytree | validation_xgboost_mae | validation_xgboost_rmse | validation_xgboost_r2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 300 | 4 | 0.05 | 0.8 | 0.8 | 5.256787101497616 | 17.128267797320856 | -5236.741992446946 |
| 2 | 200 | 2 | 0.05 | 0.9 | 1.0 | 2.6928343468653835 | 10.94099632615156 | -2136.1300801895145 |
| 3 | 400 | 3 | 0.03 | 0.8 | 1.0 | 1.564326263343064 | 3.864530776530101 | -265.6310686178388 |
| 4 | 300 | 3 | 0.03 | 0.8 | 1.0 | 0.37622800458782346 | 0.5789076726022844 | -4.983231736032837 |

Selected parameters:

```json
{
  "n_estimators": 300,
  "max_depth": 3,
  "learning_rate": 0.03,
  "subsample": 0.8,
  "colsample_bytree": 1.0,
  "log_target": true
}
```

## Final test metrics

| Model | MAE | RMSE | R² |
| --- | ---: | ---: | ---: |
| XGBoost | 372.15769118883964 | 1739.5250975465153 | -0.03140589282185591 |
| Previous-period baseline | 684.0508500507685 | 2470.1608140990174 | -1.0797860750017914 |

Validation metrics used for selection:

```json
{
  "xgboost": {
    "mae": 0.37622800458782346,
    "rmse": 0.5789076726022844,
    "r2": -4.983231736032837
  },
  "previous_period_baseline": {
    "mae": 0.19539565881264118,
    "rmse": 0.28417164689570873,
    "r2": -0.4417126233743691
  }
}
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
