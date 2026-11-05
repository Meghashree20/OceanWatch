# OceanWatch Backend

OceanWatch is a FastAPI service for marine microplastic observations, geographic
hotspot detection, model-based concentration forecasting, and transparent cleanup
priority recommendations.

## Architecture

```text
React frontend
	|
	v
FastAPI REST API
	|
	+--> MongoDB observations and hotspot results
	+--> preprocessing and DBSCAN services
	+--> XGBoost forecasting service
	+--> rule-based recommendation service
```

The backend owns data access and all ML logic. The frontend communicates only over
HTTP and never connects directly to MongoDB.

## Installation

From `backend/`:

```bash
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

## Environment variables

Copy `.env.example` to `.env` and change values for the deployment environment:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string; may contain credentials outside source control |
| `MONGODB_DB_NAME` | `oceanwatch` | Database name |
| `MONGODB_SERVER_SELECTION_TIMEOUT_MS` | `5000` | Maximum time to find a MongoDB server |
| `MONGODB_CONNECT_TIMEOUT_MS` | `5000` | MongoDB connection timeout |
| `PROJECT_NAME` | `OceanWatch API` | API title |
| `API_V1_STR` | `/api/v1` | OpenAPI JSON path prefix |
| `BACKEND_CORS_ORIGINS` | localhost origins | Explicit JSON list of allowed browser origins |
| `SATELLITE_CONFIDENCE_THRESHOLD` | `0.5` | Per-pixel softmax cutoff in `[0, 1]`; lower-confidence pixels are reported as uncertain |

`.env` is ignored by Git. Never commit credentials or generated model artifacts.

## MongoDB setup

Install and start MongoDB locally, or provide a managed MongoDB URI through
`MONGODB_URL`. The application pings MongoDB during startup and fails fast when it
cannot connect. Startup also creates indexes for observation filters, coordinates,
hotspot lookup, severity, region, and ocean.

## Dataset setup

Place the source NOAA file at:

```text
data/raw/NOAA_raw.csv
```

The repository includes a processed dataset at
`data/processed/ocean_water_clean.csv`. The import endpoint only reads that known
repository path; there is no arbitrary file-upload endpoint.

## Data preprocessing

Run from `backend/`:

```bash
python scripts/run_preprocessing.py
```

Preprocessing keeps ocean-water `pieces/m3` observations, parses dates and numeric
fields, removes invalid coordinates and missing measurements, removes exact
duplicates, and writes the reproducible cleaned CSV.

Import it after the server is running:

```bash
curl -X POST http://127.0.0.1:8000/api/data/import
```

The importer validates required columns, numeric ranges, IDs, dates, and
coordinates before any bulk write occurs.

## ML pipeline

### Hotspots

DBSCAN uses latitude/longitude converted to radians with Haversine distance. Cluster
statistics include centroids, pollution summaries, dates, severity, and observation
counts. Results are persisted in MongoDB.

### Forecasting

Irregular observations are first aggregated by `region + calendar month`. The
XGBoost regressor uses calendar, lag, rolling, and geographic features. Training is
chronological, with no random shuffle, and is compared with a previous-period
baseline. Artifacts are persisted with Joblib using an atomic replacement.
Results are explicitly **model-based pollution concentration forecasts**, not
certainty about real-world future pollution.

### Recommendations

Cleanup priority is a transparent weighted rule, not another ML model:

```text
0.40 * pollution_severity
+ 0.25 * ecological_risk
+ 0.20 * human_exposure
+ 0.15 * cleanup_feasibility
```

Ecological risk, human exposure, and cleanup feasibility are not present in the
NOAA dataset. They must be supplied as external 0-100 contextual inputs. Missing
inputs return `UNAVAILABLE` rather than fabricated values.

### Satellite segmentation

Satellite inference uses the 11-band, 11-class U-Net in `app/ml/satellite/unet.py`
and runs on CPU by default. `models/model.pth` is the official MARIDA upstream
pretrained checkpoint (epoch 44), downloaded from the archive linked by the
[upstream project](https://github.com/marine-debris/marine-debris.github.io/blob/8de83a3394edfbe867d9fa825439666369ec6282/README.md).
Its SHA-256 is recorded in `models/model.pth.metadata.json`; the checkpoint
strictly loads into this U-Net implementation. The metadata records the official
11-band Sentinel-2 order, 11-class output mapping, and preprocessing taken from
the upstream data loader. MARIDA training class IDs 12–15 are aggregated to
Marine Water as in the upstream default.

Preprocessing is `(reflectance - band_mean) / band_std`; NaN/NoData values are
imputed with the upstream per-band means before standardization. The accepted
band order is B1, B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12. Uploads must be
authentic Sentinel-2 L2A reflectance in this order; the API cannot independently
prove the source or band identity from a TIFF containing no band descriptions.
GeoTIFF per-band scale and offset metadata is applied before the model's training
normalization.
Per-pixel softmax confidence is compared with `SATELLITE_CONFIDENCE_THRESHOLD`
(default `0.5`). Below-threshold valid pixels receive class ID 254 (Uncertain);
invalid pixels remain class ID 255 (NoData). Debris coverage uses only valid,
above-threshold pixels as its denominator. The response separately reports
uncertainty, excluded pixels, average confidence, the threshold, and compatibility
warnings. A missing band order or reflectance-unit declaration is surfaced as a
warning and prevents the result from being labeled reliable. The default cutoff
is configurable, not a threshold calibrated to a claimed accuracy.

The original [MARIDA dataset](https://doi.org/10.5281/zenodo.5151941) is publicly
available under CC BY 4.0 (1.16 GB archive; 4.38 GB uncompressed). The repository
includes one unmodified held-out MARIDA test patch and its class mask under
`tests/fixtures/marida/`, attributed to Kikaki et al. (2022), DOI
10.5281/zenodo.5151941, CC BY 4.0. This supports a real inference/API smoke test.
The example has only 13 labeled pixels, so it is not evidence of broad model
accuracy. Upstream evaluation code provides a full test-split evaluation
procedure, but no aggregate evaluation log is included with the released weights.

The older registered demo rasters remain available in the catalog but are
explicitly marked as unverified and cannot be analyzed. Upload a verified
11-band Sentinel-2 L2A GeoTIFF to run inference. Results include a class-index GeoTIFF preserving the input CRS and affine
transform; uncertain pixels are encoded as 254 and invalid input pixels as
NoData value 255.

If replacing the checkpoint, update its metadata manifest only from the actual
training artifacts. Version 1 requires `format_version`, `checkpoint_sha256`,
`task`, `architecture` (`name`, `input_bands`, `output_classes`, and
`hidden_channels`), `band_order`, `class_names`, `training` (`dataset`,
`provenance`, and `validation_evidence`), and `preprocessing` arrays (`scale`,
`offset`, `mean`, and `std`, each with 11 entries). The checksum detects mismatch
between metadata and weights; it does not independently prove a model's claims.

## API endpoints

Interactive Swagger documentation is available at `/docs`. OpenAPI JSON is at
`/api/v1/openapi.json`.

| Group | Method | Endpoint |
| --- | --- | --- |
| System | GET | `/api/health` |
| Data | POST | `/api/data/import` |
| Data | GET | `/api/data` |
| Data | GET | `/api/data/stats` |
| Data | GET | `/api/data/{unique_id}` |
| Hotspots | POST | `/api/hotspots/detect` |
| Hotspots | GET | `/api/hotspots` |
| Hotspots | GET | `/api/hotspots/{cluster_id}` |
| Hotspots | GET | `/api/hotspots/stats` |
| Hotspots | GET | `/api/hotspots/runs` |
| Hotspots | GET | `/api/hotspots/runs/{run_id}` |
| Hotspots | GET | `/api/hotspots/runs/{run_id}/{cluster_id}` |
| Forecasting | POST | `/api/forecast/train` |
| Forecasting | GET | `/api/forecast/{zone_id}` |
| Forecasting | GET | `/api/forecast/model-metrics` |
| Recommendations | GET | `/api/recommendations` |
| Recommendations | GET | `/api/recommendations/{cluster_id}` |
| Recommendations | POST | `/api/recommendations/calculate` |

List endpoints support bounded pagination. Data supports date, region, ocean, and
concentration filters. Hotspots support severity, region, and ocean filters.
Invalid parameters return a structured 422 response; missing resources return 404;
unexpected failures return a generic 500 response without stack traces.

### Date filtering

All `start_date` and `end_date` filters accept ISO dates or datetimes, for example:

```text
start_date=2024-01-01
end_date=2024-01-31
start_date=2024-01-01T00:00:00Z
end_date=2024-01-31T23:59:59-05:00
```

The API uses UTC consistently. Naive datetimes are interpreted as UTC, timezone
offsets are converted to UTC, and a date-only `end_date=2024-01-31` becomes
`2024-01-31T23:59:59.999999Z`, so the entire calendar day is included. A range with
`end_date` earlier than `start_date` returns HTTP 400. The same behavior is used by
observation queries and hotspot detection MongoDB filters.

## Running the backend

From `backend/`:

```bash
uvicorn app.main:app --reload
```

For production, run behind a process manager and reverse proxy, provide secrets
through the deployment environment, restrict CORS to the real frontend origin, and
use TLS at the proxy.

## Running tests

From `backend/`:

```bash
pytest
```

The default test suite is hermetic for unit and API contract tests. The legacy
MongoDB API tests in `tests/test_data_api.py` require a reachable MongoDB instance.

## Example API responses

Health:

```json
{"status": "healthy", "service": "OceanWatch API"}
```

Paginated observations:

```json
{"data": [{"unique_id": "...", "latitude": 16.88, "longitude": -159.15, "measurement": 0.0}], "total": 6867, "skip": 0, "limit": 100}
```

Structured error:

```json
{"error": {"code": "validation_error", "message": "Request validation failed"}}
```
