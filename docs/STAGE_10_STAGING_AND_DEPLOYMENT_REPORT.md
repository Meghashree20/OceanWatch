# OceanWatch Stage 10 Staging and Deployment Preparation Report

## Executive summary

Stage 10 adds deployment-profile validation, database readiness reporting, a fail-closed staging startup path, and strict SMTP test-recipient routing. Frontend notification previews now disclose the delivery destination and prevent sending when test mode has no controlled recipient. Backend and frontend regression checks pass.

This work **did not deploy OceanWatch**, connect to a staging MongoDB cluster, send email, or run browser-backed end-to-end workflows. Stage 10 prepares safeguards and documents the required runbook; it does not establish operational or production readiness.

## Verification matrix

| Area | Status | Evidence and limits |
| --- | --- | --- |
| Development/test/staging profile selection | VERIFIED | `backend/app/core/config.py` selects a profile before app import; profile-specific names and configuration validation are covered by `backend/tests/test_config.py`. The checked-in files are examples, not runtime secrets. |
| Required backend environment inventory and safe templates | VERIFIED | `backend/.env.example`, `backend/.env.test.example`, and `backend/.env.staging.example` contain setting names and placeholders, not provider credentials. `backend/README.md` documents the variables and profile startup. |
| JWT secret generation and validation | VERIFIED | `AUTH_JWT_SECRET` is required, at least 32 characters, excluded from settings repr, and rejects staging placeholders. Validation tests pass. No runtime staging secret was provisioned. |
| Authentication APIs and permission checks | VERIFIED in automated tests | Backend tests exercise signup, login, HttpOnly cookie issuance, `/me`, missing/invalid/expired tokens, inactive users, logout cookie clearing, and protected routes. They use isolated test fixtures, not a deployed browser session. |
| Browser login and protected workflow E2E | NOT TESTED | No frontend/backend staging stack or deployment database was available. |
| Account-management completeness | PARTIALLY VERIFIED | Active/admin user roles exist. Organization directory records are not organization user accounts. Password reset, email verification, organization-role accounts, and server-side JWT revocation are not implemented. Logout clears the cookie; a copied, unexpired token remains valid until expiry or user invalidation. |
| MongoDB profile/database separation guards | VERIFIED in configuration tests | Database names must match the selected profile; staging requires a unique `oceanwatch_staging_<suffix>` name and remote TLS MongoDB. These checks cannot prove the URI points to a different cloud project/cluster from production. |
| Staging MongoDB connectivity, indexes, persistence, and recovery | BLOCKED | No staging URI, credentials, or cluster were provided. Startup pings MongoDB and creates indexes; the new readiness route checks startup state and pings MongoDB, but neither was exercised against staging. Stage 9's separate local integration evidence is historical and does not establish Stage 10 staging behavior. |
| Startup health/readiness separation | VERIFIED in automated tests | `GET /api/health` remains liveness; `GET /api/ready` returns 503 when startup/database readiness is missing and pings MongoDB when ready. Staging startup fails closed on MongoDB/index initialization failure. |
| SMTP test-mode policy and recipient routing | VERIFIED in code and automated tests | Test mode cannot be disabled in supported profiles. Notification previews disclose the controlled destination; alert and cleanup sends are routed only to `SMTP_TEST_RECIPIENT`, use a test subject/body, and direct sender calls to another address are rejected. The cleanup notifications API exposes the test-mode policy to authorized administrators. |
| Actual SMTP delivery, provider errors, retries, and acknowledgments | BLOCKED | No SMTP provider credentials or approved live test mailbox were available. Tests use a fake sender and verify simulated state/error behavior only. No email was sent. |
| Frontend notification safety UX | VERIFIED in component tests | Alert and cleanup interfaces show the controlled recipient and disable sending when test mode has no recipient. These are mocked component tests, not browser E2E against a running backend. |
| Frontend environment-variable boundary | VERIFIED in tracked templates/source | Frontend configuration is limited to `VITE_API_BASE_URL` and `VITE_API_TIMEOUT_MS`; templates warn that `VITE_*` values are public build-time values. No credentials belong there. No historical secret scan was performed. |
| Browser E2E workflows (alerts, organization notification, cleanup, evidence, citizen moderation) | NOT TESTED | No staging API/database was available. Component tests do not prove complete login-to-database workflows or media delivery in a browser. |
| Deployment architecture, backup/restore, private-media persistence, logging/monitoring, HTTPS | PARTIALLY VERIFIED | Requirements are documented below and in `backend/README.md`; no deployment manifest, staging host, durable media service, backup job, monitoring provider, or recovery drill was configured or tested. |
| Environmental/model safeguards | VERIFIED | The MARIDA checkpoint SHA-256 and four catalog names were rechecked. This work does not change model, preprocessing, taxonomy, inference, thresholds, provenance, or monitoring-location files. |
| Overall staging readiness | BLOCKED | Provision staging infrastructure and secrets, then run the blocked integration and browser workflows before considering a controlled staging release. No public deployment or production-readiness claim is made. |

## Environment configuration and isolation

### Backend profile loading

Set `OCEANWATCH_ENV` in the process/container environment **before Python imports the application**. Supported values are `development`, `test`, and `staging`; the backend loads `backend/.env.<profile>`. The tracked templates end in `.example` and are not auto-loaded:

- Development: copy `backend/.env.example` to `backend/.env.development`.
- Test: copy `backend/.env.test.example` to `backend/.env.test`; pytest also forces a local `oceanwatch_test` database and an unusable SMTP test host.
- Staging: copy `backend/.env.staging.example` to `backend/.env.staging`, then provide values through an approved secret manager or untracked file.

Real `.env` files are ignored by Git. Never commit those files, credential values, private keys, or generated secrets. The examples intentionally contain no credentials.

Required and supported backend variables:

| Group | Variables | Notes |
| --- | --- | --- |
| Profile/API | `OCEANWATCH_ENV`, `PROJECT_NAME`, `API_V1_STR` | `OCEANWATCH_ENV` selects a supported profile before startup. |
| MongoDB | `MONGODB_URL`, `MONGODB_DB_NAME`, `MONGODB_SERVER_SELECTION_TIMEOUT_MS`, `MONGODB_CONNECT_TIMEOUT_MS` | Use a separate staging cluster/project, identity, network policy, and `oceanwatch_staging_<unique-suffix>` database. Staging requires TLS and disallows localhost. |
| Hotspots | `DBSCAN_EPS_KM`, `DBSCAN_MIN_SAMPLES` | Existing DBSCAN settings. |
| Measured pollution assessment | `POLLUTION_RISK_MEDIUM_THRESHOLD`, `POLLUTION_RISK_HIGH_THRESHOLD`, `POLLUTION_RISK_CRITICAL_THRESHOLD`, `POLLUTION_TREND_WINDOW_DAYS`, `POLLUTION_TREND_MIN_OBSERVATIONS`, `POLLUTION_TREND_MIN_RELATIVE_CHANGE`, `POLLUTION_TREND_CELL_SIZE_DEGREES`, `POLLUTION_DATA_FRESHNESS_MAX_DAYS` | Preserve documented measured-observation thresholds unless an independently reviewed change is made. |
| Authentication | `AUTH_JWT_SECRET`, `AUTH_JWT_ALGORITHM`, `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`, `AUTH_COOKIE_NAME`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_PATH` | Secret is required and at least 32 characters; staging rejects placeholder prefixes and requires secure cookies. Generate locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| Satellite | `SATELLITE_MODEL_PATH`, `SATELLITE_SAMPLES_DIR`, `SATELLITE_DEVICE`, `SATELLITE_CONFIDENCE_THRESHOLD`, `SATELLITE_PROVENANCE_PUBLIC_KEY` | Existing inference and provenance configuration. No Stage 10 model or threshold changes. Any private signing material must remain server-side; only the configured public key belongs in backend settings. |
| SMTP | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_SECURITY`, `SMTP_TIMEOUT_SECONDS`, `SMTP_TEST_MODE`, `SMTP_TEST_RECIPIENT` | Username/password must be paired. Test mode is enforced and all sends are routed only to `SMTP_TEST_RECIPIENT`; a missing recipient prevents delivery. Provider credentials are not configured in this workspace. |
| Private uploads | `PRIVATE_MEDIA_DIR`, `PRIVATE_MEDIA_MAX_BYTES`, `PRIVATE_MEDIA_MAX_PIXELS` | Use durable private storage outside web/static roots with restricted service identity and backups. |
| CORS | `BACKEND_CORS_ORIGINS` | JSON array of exact origins; staging requires HTTPS-only origins. |

The staging template has blank secret/SMTP fields and a placeholder MongoDB URI, so it is intentionally not deployable until explicitly configured. The name/TLS checks reduce accidental profile mixing but do not prove the remote cluster is not production. Require a second-person review of the cloud project/cluster, account, URI, and database before startup.

The frontend accepts only `VITE_API_BASE_URL` and `VITE_API_TIMEOUT_MS`. Set them in `frontend/.env.development`, `frontend/.env.test`, or `frontend/.env.staging` using the matching Vite mode. For example, build staging assets with `npm run build -- --mode staging`. Vite embeds these values in downloadable browser code; never place JWT secrets, MongoDB credentials, SMTP credentials, or signing keys in `VITE_*`.

## Authentication and authorization

The automated API tests cover registration, duplicate signup, login, cookie attributes, current-user lookup, invalid and expired tokens, inactive users, protected routes, and logout cookie clearing. Existing active-user and admin dependencies guard protected operations.

Remaining gaps:

- Public self-registration is present; email ownership is not verified.
- Password reset/change and MFA are not implemented.
- Organization directory entries are not organization login accounts; there is no organization role or authenticated external acknowledgment.
- Logout removes the browser cookie but does not revoke a copied bearer-equivalent JWT before its expiry.
- `backend/create_admin.py` is an operational bootstrap script, not a self-service workflow. Before using it, review the selected profile, exact MongoDB cluster/database, and chosen admin email; do not use the example identity as a staging account without approval.

No live browser session or deployed role workflow was tested.

## MongoDB, indexes, persistence, and recovery

The application pings the configured database and initializes indexes at startup. In staging, inability to connect or initialize indexes aborts startup; `/api/ready` reports 503 until startup has succeeded and a subsequent MongoDB ping passes. `/api/health` is intentionally only a liveness endpoint.

There is no versioned database migration framework. Existing collections/indexes are initialized by `backend/app/db/indexes.py`. Stage 10 adds no data migration or collection change; the cleanup notification GET response adds server delivery-policy fields, while notification documents already store recipient/test-mode metadata. Stage 9's live database test used a disposable local database; Stage 10 did not connect to MongoDB.

Before staging:

1. Provision a separate managed cluster/project and least-privilege application identity. Restrict network access to the staging service and require TLS.
2. Verify the configured cloud project/cluster and database name independently; do not rely on the DB-name validator alone.
3. Configure automated encrypted backups and point-in-time recovery according to the provider's controls. Restore to a new isolated database and validate indexes and representative records before relying on recovery.
4. Do not run integration tests against production. The Stage 9 integration fixture is opt-in and drops the explicitly selected test database on teardown; it was not run in Stage 10.

Connectivity, index creation, persistence, backup, restore, and disaster recovery remain unverified against staging.

## Email notification safety

The server requires `SMTP_TEST_MODE=true` in all supported profiles. Previewed alert and cleanup emails are clearly marked as test messages and delivered only to the explicitly configured `SMTP_TEST_RECIPIENT`, never to the organization's stored contact address. The administrator sees the destination before approving; sending is disabled in the frontend when the test recipient is absent, and the backend independently rejects unsafe destinations.

To run a future actual SMTP test, an operator must provision valid SMTP settings (`SMTP_HOST`, port, paired credentials if needed, sender, and security mode) plus a specifically approved controlled mailbox as `SMTP_TEST_RECIPIENT`. The actual message must still be a test-labeled message to that mailbox. This repository configuration deliberately does not enable sending to arbitrary organization contacts during staging preparation. No credentials were available; no SMTP connection, delivery, retry through a provider, or mailbox acknowledgment occurred.

## Deployment architecture and operations

The intended controlled staging shape is a TLS-served static React frontend, a FastAPI service behind a TLS-terminating reverse proxy/load balancer, a dedicated managed MongoDB staging cluster, and durable private media storage mounted only to the API service. This is a recommended architecture, not a deployed or tested topology; the repository contains no Docker/Compose or deployment manifest.

Required operational controls before staging:

- **HTTPS and cookies:** terminate TLS; route only configured HTTPS frontend origins through CORS; set secure HttpOnly cookies; do not expose the API or private media over plain HTTP.
- **Media:** mount encrypted durable private storage outside public/static directories; retain authenticated download routes; restrict filesystem/object-storage permissions; define retention and deletion; back up media consistently with metadata. The current service uses configured local private storage, not a managed object-storage integration.
- **Backups and recovery:** enable managed MongoDB backups/PITR; keep protected media backups; document key/secret rotation; conduct a restore drill into an isolated environment and verify the service's `/api/ready` after recovery.
- **Logging and monitoring:** centralize structured application and reverse-proxy logs with access control and retention; avoid logging credentials, tokens, private image content, or unnecessary personal data. Add metrics/alerts for readiness failures, MongoDB errors, SMTP failures, upload rejection, storage capacity, and 5xx rates. No central log, metric, tracing, or error-reporting provider is configured.
- **Health checks:** use `GET /api/health` for process liveness and `GET /api/ready` for service/database readiness. Alert on repeated readiness failure; do not route traffic to an unready instance.
- **Recovery:** redeploy from a reviewed build, restore MongoDB and private media from coordinated backups to an isolated target, verify configured secrets and indexes, then validate `/api/ready` and authenticated workflows before switching staging traffic. This procedure has not been exercised.
- **Release controls:** review environment values and CORS origins, scan built assets for accidental secrets, verify change approval and rollback artifact, and keep production deployment separate from this Stage 10 scope.

## API changes

- Added `GET /api/ready` for startup/database readiness; existing `GET /api/health` remains liveness.
- `GET /api/intelligence/alerts/{alert_id}/organizations` previews now include each matched organization's intended address, test-mode flag, and actual controlled test delivery address.
- Admin-only `GET /api/cleanup/operations/{operation_id}/notifications` now includes test-mode state and the configured controlled delivery address alongside notification history.
- Existing send endpoints and administrator approval requirements remain in place. In test mode their service path sends only to the configured test recipient.

## Files changed

- Backend configuration and lifecycle: `backend/app/core/config.py`, `backend/app/main.py`, `backend/app/routes/health.py`.
- Notification safety and API data: `backend/app/services/intelligence_service.py`, `backend/app/services/cleanup_service.py`.
- Test isolation/templates: `backend/tests/conftest.py`, `backend/tests/test_config.py`, `backend/tests/test_health.py`, `backend/tests/test_auth_api.py`, `backend/tests/test_intelligence_service.py`, `backend/tests/test_cleanup_service.py`, `backend/.env.example`, `backend/.env.test.example`, `backend/.env.staging.example`, `backend/.gitignore`.
- Frontend templates and safe destination UX: `frontend/.env.example`, `frontend/.env.development.example`, `frontend/.env.test.example`, `frontend/.env.staging.example`, `frontend/.gitignore`, `frontend/src/lib/api/client.ts`, `frontend/src/components/AlertManagementPanel.tsx`, `frontend/src/components/AlertManagementPanel.test.tsx`, `frontend/src/pages/CleanupOperationsPage.tsx`, `frontend/src/pages/CleanupOperationsPage.test.tsx`.
- Documentation: `backend/README.md`, `docs/PROJECT_PHASE_AUDIT.md`, `docs/STAGE_10_STAGING_AND_DEPLOYMENT_REPORT.md`.

No database migration was created. No MARIDA model, checkpoint, production inference, monitoring location, or environmental measurement was added or changed.

## Regression tests and exact results

Backend tests used the project environment `backend/.venv-stage25` and writable `backend/test-tmp`; the opt-in live Mongo integration URL was removed for this run:

```powershell
cd backend
$env:TEMP='D:\MINORPROJ\OceanWatch\backend\test-tmp'
$env:TMP=$env:TEMP
Remove-Item Env:OCEANWATCH_TEST_MONGODB_URL -ErrorAction SilentlyContinue
.\.venv-stage25\Scripts\python.exe -m pytest --basetemp='D:\MINORPROJ\OceanWatch\backend\test-tmp' -p no:cacheprovider -q
```

| Check | Exact result |
| --- | --- |
| Full backend suite | **222 passed, 1 skipped, 42 warnings in 76.57s**. The skipped case is the opt-in live MongoDB integration. Warnings are Matplotlib/PyParsing, Starlette/HTTPX, and Rasterio deprecations. |
| Frontend suite (`npm test -- --run`) | **14 passed across 5 files**. |
| TypeScript (`npm run typecheck`) | Passed. |
| ESLint (`npm run lint`) | Passed. |
| Production build (`npm run build`) | Passed; Vite transformed 2,262 modules. |
| Focused backend Stage 10 tests | **55 passed** for config, authentication, health/readiness, notifications, and cleanup services after the final backend safety changes. |
| Focused notification UI tests | **7 passed across 2 files** before the full frontend suite. |

The Stage 10 full-suite run did not contact MongoDB or SMTP. No browser-based E2E test was run.

## Environmental safeguards

- MARIDA checkpoint `backend/models/model.pth` SHA-256: `7a690027cf279b31cae45a3188f2d4faa011b222f42b5e92c9ec6b1fd46d1b37` (required hash; rechecked).
- The four existing catalog entries remain Accra Coast, Ghana; Gulf of Honduras; Durban Harbor, South Africa; and Coastal Demo Site.
- No pollution observations, organizations, cleanup outcomes, or external validation results were fabricated.
- No checkpoint, preprocessing, class taxonomy, satellite validation/provenance, inference threshold, production inference, or monitoring-location changes were made.

## Remaining blockers and recommended next actions

1. Provision a dedicated staging cloud project/cluster, least-privilege MongoDB credentials, TLS/network restrictions, staging database suffix, and secret-manager values; have an operator independently verify the target is not production.
2. Configure a controlled test mailbox and provider credentials only after approval, then test actual SMTP send/failure handling without directing mail to organization addresses.
3. Deploy to a restricted staging URL and run browser E2E for login, permissions, alerts, recommendations, cleanup assignment/status, private evidence, citizen submission, and moderation.
4. Configure durable private media storage, retention, backups, logs/metrics/error reporting, and HTTPS; execute an isolated restore/recovery drill.
5. Address account-management gaps (verified email, password recovery, organization accounts/roles, and token revocation) before relying on the application for external organization workflows.
6. Re-run the Stage 9 guarded MongoDB integration suite only against a separately verified disposable database, then repeat all regression checks before a controlled staging release.

Until these actions are completed and evidenced, OceanWatch remains **not verified for staging deployment** and is **not certified production-ready**.
