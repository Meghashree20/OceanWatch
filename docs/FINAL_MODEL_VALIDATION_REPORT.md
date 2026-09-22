# OceanWatch Final Model Validation Report

Validation date: 2026-09-08

## Scope

This report records the final validation status of the three backend models using the
real NOAA-derived dataset and persisted artifacts. It does not claim scientific
optimality or production safety beyond the checks listed here.

## Model 1: DBSCAN

- Input: `backend/data/processed/ocean_water_clean.csv`
- Distance: geographic Haversine distance after degree-to-radian conversion
- Selected configuration: `eps_km=150`, `min_samples=10`
- Selection basis: empirical Phase 11 parameter sensitivity analysis
- Parameter grid: 7 eps values x 4 min-samples values = 28 configurations
- Selected-run observations: 6,867
- Selected-run clusters: 61
- Selected-run noise observations: 1,703
- Selected-run noise percentage: 24.7998%
- Minimum cluster size: 10
- Maximum cluster size: 1,161
- Largest cluster percentage: 16.9069%

Each execution persists a UUID-based `detection_run_id`, UTC creation time, selected
parameters, dataset hash, filters, cluster statistics, and run-scoped hotspot IDs.
Previous runs are preserved.

## Model 2: XGBoost

- Aggregation: irregular observations aggregated by `region + calendar month`
- Minimum history: 6 observed monthly periods per region
- Eligible regions: 22
- Aggregated rows: 489
- Usable time periods: 165
- Features: year, month, quarter, lag 1-3, rolling means 3 and 6, latitude, longitude, region
- Split: chronological and disjoint by target period
  - Training: 2010-09-01 to 2020-01-01, 181 samples
  - Validation: 2020-02-01 to 2022-04-01, 48 samples
  - Testing: 2022-05-01 to 2024-10-01, 47 samples
- Candidate configurations: 4 controlled XGBoost candidates
- Selection metric: validation RMSE
- Selected candidate: 300 estimators, depth 3, learning rate 0.03, subsample 0.8, column subsample 1.0, log target enabled

Final test metrics:

| Model | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: |
| XGBoost | 372.0795 | 1739.9040 | -0.0319 |
| Previous-period baseline | 684.0509 | 2470.1608 | -1.0798 |

The selected XGBoost model improves all three test metrics relative to the baseline,
but the slightly negative R2 indicates limited explanatory power on this irregular,
heavy-tailed dataset.

The Joblib artifact contains the fitted preprocessing pipeline, model, features,
selected parameters, split metadata, coverage diagnostics, and metrics. The API
loads this artifact for inference instead of retraining each request.

## Model 3: Cleanup priority decision engine

- NOAA-derived factors: average pollution, normalized pollution score, observation density, and hotspot statistics
- External factors: ecological risk, human exposure, cleanup feasibility
- Required weights: 0.40, 0.25, 0.20, 0.15
- Weight sum validated as 1.0
- Pollution normalization: log-scaled min-max across actual average pollution values within the selected detection run
- Missing context: returns `status=context_required`, null priority score, and missing factor names
- Complete calculations return every weighted contribution and calculation explanation

No ecological, exposure, or feasibility values are generated from NOAA data.

## Limitations

- NOAA data is sampled and geographically uneven.
- Forecast R2 is slightly negative despite improvement over the naive baseline.
- Recommendation contextual factors require external provenance and are not independently verified by the backend.
- Authentication, authorization, rate limiting, and operational observability remain deployment responsibilities.
- The backend should be placed behind a secured production proxy before public exposure.
