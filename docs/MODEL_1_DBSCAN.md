# Model 1: Potential Pollution Hotspot Detection

## Objective

Identify geographic groups of sampled ocean-water microplastic observations that may
warrant further investigation. Results are labelled **Potential Pollution Hotspot**
or **Detected Pollution Hotspot**. They are not claims that the sampled clusters are
scientifically proven pollution hotspots.

## Dataset

The model runs on the cleaned NOAA dataset:

```text
backend/data/processed/ocean_water_clean.csv
```

The validated dataset contains 6,867 ocean-water observations in `pieces/m3`, with
valid dates, numeric measurements, and valid latitude/longitude coordinates.

## Preprocessing

The existing preprocessing pipeline:

- keeps `Marine Setting = Ocean water`
- keeps `Unit = pieces/m3`
- parses sample dates
- converts latitude, longitude, and measurements to numeric values
- removes missing measurements
- removes invalid coordinates outside latitude `[-90, 90]` or longitude `[-180, 180]`
- removes exact duplicate rows

The result is stored as the cleaned CSV and imported into MongoDB as
`pollution_observations`.

## Geographic distance

Latitude and longitude are converted from degrees to radians. DBSCAN uses sklearn's
`haversine` metric with `algorithm="ball_tree"`. The kilometer radius is converted
to radians using an Earth radius of 6,371 km:

```text
eps_radians = eps_km / 6371
```

Ordinary Euclidean distance on raw latitude/longitude is not used.

## DBSCAN

For each observation, DBSCAN determines whether enough observations exist within the
configured geographic radius to form a dense group. Noise observations receive:

```text
cluster_id = -1
```

Cluster statistics include:

- cluster ID and deterministic run-scoped hotspot ID
- observation count
- centroid latitude and longitude
- average, median, maximum, and minimum pollution
- population standard deviation of pollution
- date start and date end
- dominant region
- severity based on average pollution

## Parameter experiment

The full Phase 11 grid tested 28 configurations:

- `eps_km`: 50, 100, 150, 200, 250, 300, 400
- `min_samples`: 5, 10, 15, 20

Results are available in:

- [dbscan_parameter_results.csv](../backend/data/processed/dbscan_parameter_results.csv)
- [DBSCAN_PARAMETER_EXPERIMENTS.md](DBSCAN_PARAMETER_EXPERIMENTS.md)

The experiment used mean and median great-circle distance from cluster members to
cluster centroids as spatial compactness indicators. These are descriptive quality
measures, not scientific validation metrics.

## Selected parameters

The selected configuration is:

```text
eps_km = 150
min_samples = 10
```

These values are **selected based on empirical parameter sensitivity analysis**.
They are stored in the environment-backed configuration fields:

```text
DBSCAN_EPS_KM=150
DBSCAN_MIN_SAMPLES=10
```

Observed Phase 11 results for this configuration:

- clusters: 61
- noise observations: 1,703
- noise percentage: 24.7998%
- minimum cluster size: 10
- maximum cluster size: 1,161
- mean cluster size: 84.6557
- median cluster size: 25.0
- largest cluster percentage: 16.9069%
- mean centroid distance: 337.188 km
- median centroid distance: 258.2483 km

## Selection justification

`eps_km=150` was chosen because it produced a moderate noise proportion while
retaining geographically meaningful groups. Compared with the 50 km settings, it
avoids producing hundreds of small, fragmented clusters. Compared with the larger
radii, it limits geographic merging and keeps the largest cluster below 25% of the
observations for the selected `min_samples` value.

`min_samples=10` was chosen because every selected cluster has at least 10
observations, while the result still retains 61 groups for investigation. Higher
values reduce the number of clusters and increase the minimum density requirement;
lower values produce more small groups. This is an operational project choice, not
a scientifically optimal parameter claim.

## Run identity and persistence

Every successful DBSCAN execution creates a run record in
`hotspot_detection_runs` with:

- `run_id`
- UTC `created_at`
- `eps_km`
- `min_samples`
- SHA-256 `dataset_hash`
- filters used
- cluster and noise totals

Each stored cluster includes the same run metadata and a deterministic run-scoped
`hotspot_id` in the form `{run_id}:{cluster_id}`. Previous runs are preserved; a
new execution does not delete or overwrite earlier results.

Run-aware endpoints are:

- `GET /api/hotspots/runs`
- `GET /api/hotspots/runs/{run_id}`
- `GET /api/hotspots/runs/{run_id}/{cluster_id}`

The existing `GET /api/hotspots/{cluster_id}` endpoint remains available for
backward compatibility and resolves the cluster from the latest recorded run.

## Limitations

- NOAA observations are sampled and irregular, not continuous spatial coverage.
- DBSCAN results depend on sampling density and the selected radius/density threshold.
- Centroids are arithmetic summaries of sampled coordinates, not physical source
  locations.
- A cluster's severity is based on average sampled concentration and does not prove
  ecological harm or causality.
- Region metadata is incomplete in the source data.
- The parameter experiment is empirical sensitivity analysis, not ground-truth model
  validation.
- Results should guide inspection and prioritization, not replace scientific or
  operational assessment.
