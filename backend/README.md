# OceanWatch Backend

OceanWatch is a FastAPI service for marine microplastic observations, geographic
hotspot detection, measured-trend early warnings, model-based concentration
forecasting, and transparent cleanup priority recommendations.

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
	+--> observed-trend and alert intelligence service
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

## Environment profiles

The backend selects a profile before importing the application. Set
`OCEANWATCH_ENV` to `development`, `test`, or `staging` **before the Python
process starts**; it loads `backend/.env.<profile>`. The tracked
`.env.example`, `.env.test.example`, and `.env.staging.example` files are safe
templates, not files that the application loads directly. Copy the appropriate
template to `.env.development`, `.env.test`, or `.env.staging`, then provide
values through an untracked file or the deployment secret manager. Do not copy
production credentials into development or test.

Generate a signing secret locally with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the generated value as `AUTH_JWT_SECRET` in the backend environment only.
It must be at least 32 characters. Staging additionally requires a non-placeholder
secret, `AUTH_COOKIE_SECURE=true`, HTTPS-only CORS origins, a remote TLS-enabled
MongoDB endpoint, and a database named `oceanwatch_staging_<unique-suffix>`.
Staging startup fails if MongoDB or index initialization is unavailable. The
development and test profiles use separate database names; the test suite
overrides its MongoDB URL and will not select a staging or production profile.

`AUTH_JWT_SECRET`, MongoDB credentials, SMTP credentials, and satellite signing
keys are server-only. Never put them in a frontend `.env` file. `VITE_*` values
are embedded in public browser assets.

### Backend setting reference

All settings are case-sensitive. Bracketed values are validation constraints;
the profile templates show the main values required for each deployment.

| Variable(s) | Purpose |
| --- | --- |
| `OCEANWATCH_ENV` | Selects `development`, `test`, or `staging` and the matching profile file. |
| `PROJECT_NAME`, `API_V1_STR` | API title and OpenAPI path prefix. |
| `MONGODB_URL`, `MONGODB_DB_NAME` | MongoDB endpoint and isolated database name; staging requires a remote TLS endpoint and staging-prefixed DB name. |
| `MONGODB_SERVER_SELECTION_TIMEOUT_MS`, `MONGODB_CONNECT_TIMEOUT_MS` | MongoDB selection and connection timeouts. |
| `DBSCAN_EPS_KM`, `DBSCAN_MIN_SAMPLES` | Existing hotspot-clustering parameters. |
| `POLLUTION_RISK_MEDIUM_THRESHOLD`, `POLLUTION_RISK_HIGH_THRESHOLD`, `POLLUTION_RISK_CRITICAL_THRESHOLD` | Measured-pollution risk thresholds in pieces/m³. |
| `POLLUTION_TREND_WINDOW_DAYS`, `POLLUTION_TREND_MIN_OBSERVATIONS`, `POLLUTION_TREND_MIN_RELATIVE_CHANGE`, `POLLUTION_TREND_CELL_SIZE_DEGREES`, `POLLUTION_DATA_FRESHNESS_MAX_DAYS` | Observation trend comparison windows, evidence minimums, cell size, and freshness. |
| `AUTH_JWT_SECRET`, `AUTH_JWT_ALGORITHM`, `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | Signing secret (required, at least 32 characters), token algorithm, and token lifetime. |
| `AUTH_COOKIE_NAME`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_PATH` | HttpOnly authentication cookie settings; staging requires `AUTH_COOKIE_SECURE=true`. |
| `SATELLITE_MODEL_PATH`, `SATELLITE_SAMPLES_DIR`, `SATELLITE_DEVICE`, `SATELLITE_CONFIDENCE_THRESHOLD`, `SATELLITE_PROVENANCE_PUBLIC_KEY` | Model/runtime paths, device, existing confidence cutoff, and optional trusted Ed25519 public key. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_SECURITY`, `SMTP_TIMEOUT_SECONDS` | Optional SMTP transport settings; username and password must be supplied together. |
| `SMTP_TEST_MODE`, `SMTP_TEST_RECIPIENT` | Test mode must remain enabled in every supported profile. Approved messages are sent only to this explicitly configured recipient and labeled as test messages; organization delivery is disabled. A missing test recipient prevents sending. |
| `PRIVATE_MEDIA_DIR`, `PRIVATE_MEDIA_MAX_BYTES`, `PRIVATE_MEDIA_MAX_PIXELS` | Private image storage path and upload limits. The path must be a durable, non-public mount in a deployment. |
| `BACKEND_CORS_ORIGINS` | Explicit JSON list of browser origins; staging requires HTTPS origins. |

### Frontend settings

The frontend accepts only `VITE_API_BASE_URL` (backend origin) and
`VITE_API_TIMEOUT_MS` (request timeout). See the `.env.*.example` files in
`frontend/`. Build with Vite's matching mode, for example
`npm run build -- --mode staging`, after creating `frontend/.env.staging`.
These public values must not contain credentials or server-side secrets.

See `docs/STAGE_10_STAGING_AND_DEPLOYMENT_REPORT.md` for the verification
matrix, authentication limitations, database/email safety rules, and deployment
blockers.

## MongoDB setup

For local development, use a dedicated local database. For staging, provision a
separate MongoDB project/cluster, credentials, network policy, and
`oceanwatch_staging_<unique-suffix>` database; never reuse production credentials
or point a staging URI at a production cluster. The application pings MongoDB and
initializes indexes at startup. Staging fails closed if either step fails; the
development/test profiles remain alive but report not-ready when MongoDB is
unavailable. `GET /api/health` is a liveness check; `GET /api/ready` also checks
startup state and MongoDB connectivity.

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

### Satellite input validation

`POST /api/satellite/validate` inspects a GeoTIFF before analysis and returns a
compatibility status, band and pixel statistics, calibrated reflectance status,
CRS, resolution, geographic bounds, provenance status, and whether inference is
permitted. `POST /api/satellite/analyze` reruns the same validation and rejects
every input except `VERIFIED_COMPATIBLE`; a preflight result is not an inference
authorization token.

Production verification requires a deployment-managed Ed25519 PEM public key
in `SATELLITE_PROVENANCE_PUBLIC_KEY`. The caller may submit a JSON envelope in
the `provenance_manifest_json` form field, with a signed `payload` containing
the raster SHA-256, Sentinel-2 product identifier, acquisition date and
processing baseline, L2A processing level, ordered band identities, stored-value representation,
reflectance units, raster scales and offsets, calibration method, source
metadata references, pixel size, and a product-specific maximum invalid-pixel
fraction. The signature is checked against the server key and the hash binds
the manifest to the exact uploaded bytes. A caller-supplied key, TIFF tags, or
unsigned sidecar cannot authorize inference. For already calibrated
surface-reflectance values, scales must be identity and offsets zero; signed
UInt16 digital-number products use the per-band calibration recorded in the
trusted manifest from the cited source product metadata, applied once. If TIFF
scale/offset tags are present they must agree with that calibration. Missing or
contradictory calibration is rejected.

For UInt16 L2A digital numbers, the manifest must include per-band
`quantification_values` and `boa_add_offsets`. The verifier checks that the
effective affine calibration is exactly `scale = 1 / quantification_value` and
`offset = boa_add_offset / quantification_value`, as specified in the
[Sentinel-2 Products Specification](https://sentinels.copernicus.eu/documents/d/sentinel/s2-pdgs-cs-di-psd-v15-0).
DN 0 is masked as product NoData. These values must come from the source
product metadata; they are not defaults or application constants.

The signature is base64 Ed25519 over the UTF-8 encoding of the payload serialized
as canonical JSON (`sort_keys=true`, compact separators `(',', ':')`,
`ensure_ascii=false`). The envelope has this shape; values must come from the
trusted Sentinel-2 product record:

```json
{
  "payload": {
    "raster_sha256": "<sha256 of uploaded TIFF bytes>",
    "source_product_id": "<Sentinel-2 product identifier>",
    "acquisition_date": "2024-05-02",
    "processing_level": "L2A",
    "processing_baseline": "<baseline from source metadata>",
    "band_order": ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"],
    "stored_values": "surface_reflectance",
    "reflectance_units": "1",
    "calibration_method": "identity_reflectance",
    "raster_scales": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    "raster_offsets": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "source_metadata_refs": ["<immutable reference to original product metadata>"],
    "pixel_size_m": 10,
    "max_invalid_pixel_fraction": 0.05
  },
  "signature": "<base64 Ed25519 signature>"
}
```

The key must be managed outside source control and distributed only after the
imagery verification process is established. This repository does not contain
a production trust key or a production-signed imagery manifest, so the current
four sample sites and ordinary uploads remain unavailable for inference.

#### Trusted imagery issuance workflow

The signature is an authorization statement from the organization that controls
the private key. It does not independently prove that an uploaded image is
genuine Sentinel-2 data. The current application verifies signatures and raster
hashes, but does not implement product retrieval, source-metadata parsing, or a
manifest signing service. A production trust signer must perform these checks
before issuing an envelope:

1. Obtain the original Sentinel-2 L2A SAFE product from an authorized Copernicus
   source. Preserve the original product identifier, acquisition date, baseline,
   `manifest.safe`, product metadata XML, source files, and their checksums.
2. Verify the product identity and processing level from the preserved source
   metadata. Verify each image file's band identity, tile, CRS, affine grid,
   and native resolution. Record the original file references and the chosen
   common model grid and resampling operation.
3. Stack exactly B1, B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12 into the model's
   channel order, excluding B10. Produce a co-registered 10 m grid consistent
   with the MARIDA training patches and preserve its CRS and transform.
4. Either export unitless calibrated surface reflectance as float data with
   identity scale/zero offset, or retain UInt16 DN and copy the exact per-band
   quantification and BOA offset fields from the source metadata. Do not apply
   the calibration twice. Keep DN 0 as NoData.
5. Independently validate the output pixels and invalid-pixel policy against
   the source product. Compute the exact output TIFF SHA-256 and prepare the
   complete manifest from the preserved product record.
6. Sign only the canonical manifest payload with an isolated organizational
   signing service. Keep the private key out of OceanWatch, its uploads, and the
   frontend. Configure only the corresponding Ed25519 public key in
   `SATELLITE_PROVENANCE_PUBLIC_KEY`.

Steps 1–6 are an operational trust procedure, not a tool implemented in this
repository. Until an accountable signer and product-verification process exist,
do not issue production signatures. The unit tests use ephemeral test keys only.

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
| Intelligence | GET | `/api/intelligence/trends` |
| Intelligence | POST | `/api/intelligence/assess` |
| Intelligence | GET | `/api/intelligence/alerts` |
| Intelligence | PATCH | `/api/intelligence/alerts/{alert_id}/status` |
| Intelligence | GET | `/api/intelligence/organizations` |
| Intelligence | POST | `/api/intelligence/organizations` |
| Intelligence | PATCH | `/api/intelligence/organizations/{organization_id}/verification` |
| Intelligence | GET | `/api/intelligence/alerts/{alert_id}/organizations` |
| Intelligence | POST | `/api/intelligence/alerts/{alert_id}/notifications` |
| Intelligence | GET | `/api/intelligence/alerts/{alert_id}/notifications` |
| Intelligence | PATCH | `/api/intelligence/notifications/{notification_id}/acknowledge` |

Intelligence trend and alert assessments use observed NOAA microplastic
measurements, not forecast values. Risk bands, equal-window length, minimum
observation count, cell size, and freshness are configurable through the
`POLLUTION_*` environment variables in `.env.example`. Organization registration,
verification, notification sending, and acknowledgment require administrator
authorization. Email is never sent automatically; SMTP configuration is optional.

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
