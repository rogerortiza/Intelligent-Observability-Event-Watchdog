# Task List — Intelligent Observability & Event Watchdog

> Status markers: `[ ]` pending · `[~]` in progress · `[x]` done  
> Format: `Task XX — [file] — description — AC: acceptance criteria`  
> Ordered by dependency. Nothing depends on something not yet built.

---

## Branch: `feature/project-scaffolding`
> Covers: repo structure, env template, package markers, README

- [x] Task 01 — `git` — Create and checkout `feature/project-scaffolding` from main — AC: `git branch --show-current` prints `feature/project-scaffolding`
- [x] Task 02 — `.env.example` — Document all 12 env vars (SUPABASE_DB_URL, DEBUG, all thresholds, API_BASE_URL) with types, defaults, and inline comments — AC: File exists at project root; `diff .env.example` against spec §9 shows no missing variables
- [x] Task 03 — `app/__init__.py`, `app/routers/__init__.py`, `app/services/__init__.py` — Empty package markers so Python treats all three dirs as importable packages — AC: `python -c "import app; import app.routers; import app.services"` exits 0 with no errors
- [x] Task 04 — `requirements.txt` — Confirm all 18 pinned packages match spec §2; run `pip install -r requirements.txt` inside `.venv` — AC: `.venv/bin/pip list --format=freeze` shows every package at the pinned version; no install errors
- [x] Task 05 — `README.md` — Step-by-step setup (clone → venv → install → copy .env → configure Supabase URL → run API → run dashboard → run tests) with exact shell commands for each step — AC: A developer following the README from scratch reaches a running FastAPI server and Streamlit dashboard

---

## Branch: `feature/database-models`
> Covers: config, sync SQLAlchemy engine, all ORM models and enums  
> Depends on: Task 03 (package markers), Task 04 (requirements installed)

- [x] Task 06 — `git` — Create and checkout `feature/database-models` from main — AC: `git branch --show-current` prints `feature/database-models`
- [x] Task 07 — `app/config.py` — Pydantic `BaseSettings` class loading all 12 env vars from `.env` with typed defaults; exports `settings` singleton; all threshold values defined as named constants (no magic numbers) — AC: `from app.config import settings; assert settings.error_count_threshold == 10` passes without a `.env` file present
- [x] Task 08 — `app/database.py` — Sync SQLAlchemy engine using `settings.database_url`, `SessionLocal` factory via `sessionmaker`, `Base` declarative base, `init_db()` that runs `create_all`, `get_db()` context-manager generator for FastAPI `Depends()` — AC: Running `python -c "from app.database import init_db; import asyncio"` imports cleanly; `init_db()` called with a valid SUPABASE_DB_URL creates tables without error
- [x] Task 09 — `app/models.py` — All 5 ORM models (LogEntry, MetricSnapshot, Alert, WebhookConfig, WebhookDelivery) and all 5 enum types (LogLevel, AlertType, AlertSeverity, AlertStatus, WebhookStatus) with every field, type, constraint, default, and FK relationship exactly as specified in spec §5 — AC: `init_db()` runs without error; all 5 tables and all enum columns are visible in the Supabase table editor

---

## Branch: `feature/log-ingestion-api`
> Covers: all Pydantic schemas, logs router, core FastAPI app  
> Depends on: Task 07 (config), Task 08 (database), Task 09 (models)

- [x] Task 10 — `git` — Create and checkout `feature/log-ingestion-api` from main — AC: `git branch --show-current` prints `feature/log-ingestion-api`
- [x] Task 11 — `app/schemas.py` — All 17 Pydantic schemas: `LogEntryCreate`, `LogEntryOut`, `LogEntryBatch`, `MetricSnapshotOut`, `MetricsSummary`, `TimeSeriesPoint`, `TimeSeriesResponse`, `AlertOut`, `AlertAcknowledge`, `WebhookCreate`, `WebhookOut`, `WebhookDeliveryOut`, `SimulateNormalRequest`, `SimulateSpikeRequest`, `SimulateResponse`, `HealthCheck`, `PaginatedResponse` — AC: `from app.schemas import LogEntryCreate, PaginatedResponse` imports cleanly; `LogEntryCreate(level="ERROR", service="s", message="m")` validates without error
- [x] Task 12 — `app/routers/logs.py` — `POST /api/v1/logs/ingest` (201, returns full `LogEntryOut`), `POST /api/v1/logs/ingest/batch` (201, accepts 1–1000 entries), `GET /api/v1/logs` with query filters (service, level, start_time, end_time, limit 1–1000, offset) returning `PaginatedResponse` ordered by `timestamp DESC` — AC: POST /logs/ingest returns 201 with `id` and `ingested_at` fields; GET /logs?level=ERROR returns only ERROR/CRITICAL entries; batch ingest of 100 entries returns `{"count": 100}`
- [x] Task 13 — `app/main.py` — FastAPI app factory with `lifespan` context (calls `init_db()`, `start_watchdog()`, `stop_watchdog()`), `CORSMiddleware` allowing all origins, mounts all 5 routers at `/api/v1` prefix (logs, metrics, alerts, webhooks, simulate), `GET /api/v1/health` returning `HealthCheck` schema with uptime — AC: `uvicorn app.main:app --reload` starts without import errors; `GET /api/v1/health` returns `{"status":"ok","watchdog":"running","database":"postgresql"}`; Swagger UI at `/docs` lists all endpoints

---

## Branch: `feature/anomaly-engine`
> Covers: three-tier anomaly detector service, metrics read router  
> Depends on: Task 09 (models), Task 11 (schemas), Task 13 (main.py for router mount)

- [ ] Task 14 — `git` — Create and checkout `feature/anomaly-engine` from main — AC: `git branch --show-current` prints `feature/anomaly-engine`
- [ ] Task 15 — `app/services/anomaly_detector.py` — `_zscore(value, baseline)` helper; `get_baseline(db, service, field, lookback)` DB query; `AnomalyResult` dataclass; Tier 1 hard threshold checks (error_count ≥ 10, error_rate ≥ 0.25, latency ≥ 2000ms, dual-breach → CRITICAL); Tier 2 Z-score detection on error_count/total_logs/avg_latency_ms with `|z| ≥ 2.5` trigger and severity mapping (≥5→CRITICAL, ≥4→HIGH, ≥3→MEDIUM); Tier 3 IsolationForest on feature vector `[error_count, total_logs, avg_latency_ms or 0.0]` with `contamination=0.05`, fires only when ≥ 20 baseline windows exist; `detect_anomalies(db, snapshot)` orchestrator returning list of `AnomalyResult`; `create_alert_from_result(db, result, snapshot)` persisting `Alert` row — AC: Calling `detect_anomalies` on a snapshot with `error_count=15` returns at least one `AnomalyResult` with `alert_type=ERROR_RATE_SPIKE`; `_zscore(10, [2,2,2,2,2])` returns a float > 2.5; IsolationForest does not fire with fewer than 20 baseline rows
- [ ] Task 16 — `app/routers/metrics.py` — `GET /api/v1/metrics/summary` querying last 24h for total_logs, error_count, active_alerts, services_monitored, avg_latency, health_score using formula `max(0, min(100, 100 - error_rate*50 - active_alerts*5))`; `GET /api/v1/metrics/timeseries` returning `TimeSeriesResponse` for any of 4 metrics over 1–168h with optional service filter; `GET /api/v1/metrics/snapshots` returning paginated `MetricSnapshotOut` — AC: GET /metrics/summary returns all 8 fields; `health_score` is always 0–100; GET /metrics/timeseries?metric=error_count returns `{"metric":"error_count","points":[...]}`

---

## Branch: `feature/alert-manager`
> Covers: alert read/lifecycle router (list, detail, ACK, resolve)  
> Depends on: Task 09 (Alert model), Task 11 (AlertOut schema)

- [ ] Task 17 — `git` — Create and checkout `feature/alert-manager` from main — AC: `git branch --show-current` prints `feature/alert-manager`
- [ ] Task 18 — `app/routers/alerts.py` — `GET /api/v1/alerts` with filters (status, severity, alert_type, service, limit, offset) returning `PaginatedResponse` ordered by `triggered_at DESC`; `GET /api/v1/alerts/{id}` returning `AlertOut` or 404; `PUT /api/v1/alerts/{id}/acknowledge` setting `status=ACKNOWLEDGED` and `acknowledged_at=utcnow`, returns 400 if already non-OPEN; `PUT /api/v1/alerts/{id}/resolve` setting `status=RESOLVED` and `resolved_at=utcnow`, returns 400 if already resolved — AC: GET /alerts returns paginated list; PUT /alerts/1/acknowledge on an OPEN alert returns 200 with `status="ACKNOWLEDGED"`; second ACK on same alert returns 400; PUT /alerts/1/resolve sets `resolved_at` timestamp

---

## Branch: `feature/webhook-dispatcher`
> Covers: webhook delivery service, webhook CRUD router  
> Depends on: Task 09 (WebhookConfig, WebhookDelivery models), Task 11 (webhook schemas)

- [ ] Task 19 — `git` — Create and checkout `feature/webhook-dispatcher` from main — AC: `git branch --show-current` prints `feature/webhook-dispatcher`
- [ ] Task 20 — `app/services/webhook_dispatcher.py` — `_build_payload(alert)` serializing alert to JSON dict; `_sign_payload(secret, body)` generating `sha256=<hmac>` header; `dispatch_alert(db, alert)` querying active `WebhookConfig` rows, filtering by severity and alert_type, POSTing signed payload via `httpx.AsyncClient`, persisting `WebhookDelivery` row with status/status_code/response_body for each attempt — AC: Dispatching to `https://httpbin.org/post` returns a `WebhookDelivery` with `status=SUCCESS` and `status_code=200`; dispatching to an unreachable URL creates a `WebhookDelivery` with `status=FAILED` and a non-null `error_message`; a webhook with `min_severity=CRITICAL` is skipped for a MEDIUM alert
- [ ] Task 21 — `app/routers/webhooks.py` — `POST /api/v1/webhooks` (201 `WebhookOut`); `GET /api/v1/webhooks` (list all); `GET /api/v1/webhooks/{id}` (single or 404); `DELETE /api/v1/webhooks/{id}` (204); `PUT /api/v1/webhooks/{id}/toggle` (flips `active` boolean); `GET /api/v1/webhooks/{id}/deliveries` (paginated `WebhookDeliveryOut`) — AC: POST /webhooks creates a record; DELETE removes it and subsequent GET returns 404; PUT /toggle flips active from true to false; GET /deliveries returns delivery history after a dispatch

---

## Branch: `feature/watchdog-scheduler`
> Covers: APScheduler background watchdog loop and cycle logic  
> Depends on: Task 15 (anomaly_detector), Task 20 (webhook_dispatcher), Task 09 (models)

- [ ] Task 22 — `git` — Create and checkout `feature/watchdog-scheduler` from main — AC: `git branch --show-current` prints `feature/watchdog-scheduler`
- [ ] Task 23 — `app/services/watchdog.py` — `_aggregate_window(db, service, start, end)` building a `MetricSnapshot` (total_logs, error_count, warning_count, error_rate, avg/p95/max latency using numpy); `run_watchdog_cycle()` discovering active services in the current window, skipping existing snapshots (idempotent), calling `detect_anomalies`, creating `Alert` rows, committing, then dispatching webhooks; `watchdog_loop()` async infinite loop sleeping `WATCHDOG_INTERVAL_SECONDS`; `start_watchdog()` / `stop_watchdog()` managing the asyncio Task; `is_running()` returning bool — AC: After seeding 20 ERROR logs for `auth-service` and calling `run_watchdog_cycle()` directly, a `MetricSnapshot` and at least one `Alert` row appear in the DB; calling `run_watchdog_cycle()` twice for the same window creates only one snapshot (idempotent); `is_running()` returns True after `start_watchdog()`

---

## Branch: `feature/log-simulator`
> Covers: Faker-powered simulation endpoints  
> Depends on: Task 09 (LogEntry model), Task 22/Task 23 (watchdog for manual trigger endpoint)

- [ ] Task 24 — `git` — Create and checkout `feature/log-simulator` from main — AC: `git branch --show-current` prints `feature/log-simulator`
- [ ] Task 25 — `app/routers/simulate.py` — `POST /api/v1/simulate/normal-traffic` generating `count` logs with `error_rate` fraction using Faker for messages (service names, error messages, latency values); `POST /api/v1/simulate/error-spike` injecting `error_count` ERROR/CRITICAL logs spread over `spike_duration_minutes`; `POST /api/v1/simulate/run-watchdog` triggering `run_watchdog_cycle()` as a background task; `POST /api/v1/simulate/seed-all-services` seeding all 5 built-in services with mixed-level traffic — AC: POST /simulate/normal-traffic with `count=50` inserts 50 `LogEntry` rows; POST /simulate/error-spike with `error_count=30` inserts ≥30 ERROR/CRITICAL rows; POST /simulate/run-watchdog returns immediately with a 200; POST /simulate/seed-all-services returns service list with 5 entries

---

## Branch: `feature/streamlit-dashboard`
> Covers: Streamlit single-process dashboard with 5s auto-refresh  
> Depends on: Task 13 (FastAPI running), Task 16 (metrics endpoints), Task 18 (alerts endpoint)

- [ ] Task 26 — `git` — Create and checkout `feature/streamlit-dashboard` from main — AC: `git branch --show-current` prints `feature/streamlit-dashboard`
- [ ] Task 27 — `dashboard/app.py` (Panel 1 — Metric Cards) — `streamlit-autorefresh` at 5000ms; call `GET /api/v1/metrics/summary`; render 4 `st.metric` cards: Health Score (color green ≥ 80 / yellow ≥ 60 / red < 60), Total Logs 24h, Error Rate 24h (inverse delta), Active Alerts (inverse delta) — AC: Cards appear at top of page; values update every 5 seconds; Health Score delta color matches threshold rules
- [ ] Task 28 — `dashboard/app.py` (Panel 2 + 3 — Service Table + Trend Chart) — Call `GET /api/v1/metrics/snapshots?hours=1`; group by service, show latest snapshot per service with error_rate progress bar in `st.dataframe`; call `GET /api/v1/metrics/timeseries?metric=error_count`; render Plotly dual-axis line chart (error_count left axis, total_logs right axis); sidebar service multiselect filters the chart — AC: Service table lists each active service with its latest error_rate; chart renders with two Y-axes; selecting a service in the sidebar filters the chart data
- [ ] Task 29 — `dashboard/app.py` (Panel 4 — Alert Feed + Sidebar Actions) — Call `GET /api/v1/alerts?limit=50`; render `st.dataframe` with severity-based row background colors (CRITICAL `#7f1d1d`, HIGH `#7c2d12`, MEDIUM `#713f12`, LOW `#14532d`); sidebar buttons "Seed Normal Traffic", "Inject Error Spike", "Run Watchdog Now" calling respective `/api/v1/simulate/*` endpoints via `requests`; show `st.success/error` feedback toast — AC: Alert feed shows color-coded rows matching severity; clicking "Inject Error Spike" button calls the API and shows success toast; after "Run Watchdog Now" and a refresh, new alerts appear in the feed

---

## Branch: `feature/smoke-tests`
> Covers: unit tests, integration tests, end-to-end smoke test script  
> Depends on: all prior branches merged to main (full running system required)

- [ ] Task 30 — `git` — Create and checkout `feature/smoke-tests` from main — AC: `git branch --show-current` prints `feature/smoke-tests`
- [ ] Task 31 — `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py` — Empty package markers for test directories — AC: `python -m pytest --collect-only` discovers test directories without import errors
- [ ] Task 32 — `tests/conftest.py` — `TEST_DATABASE_URL` pointing to `sqlite:///./test_watchdog.db`; override `get_db` dependency with test SQLite session; `TestClient` fixture wrapping the FastAPI app; session-scoped setup that calls `init_db()` before tests and drops all tables after; `sample_log_entry` fixture; `sample_alert` fixture — AC: Running `pytest tests/` with no test files yet exits 0; adding a trivial test that uses the `client` fixture passes; the test DB is created and dropped around the session
- [ ] Task 33 — `tests/unit/test_anomaly_detector.py` — `test_zscore_returns_none_with_fewer_than_5_samples`; `test_zscore_returns_high_value_for_outlier`; `test_tier1_fires_on_error_count_threshold`; `test_tier1_fires_critical_on_dual_breach`; `test_tier2_fires_on_high_zscore`; `test_isolation_forest_skipped_below_20_samples`; `test_severity_from_zscore_mapping` — AC: `pytest tests/unit/` passes all 7 tests; all tests run against in-memory/mock data with no DB required
- [ ] Task 34 — `tests/integration/test_logs_api.py` — `test_ingest_single_log_returns_201`; `test_ingest_sets_ingested_at`; `test_batch_ingest_100_logs`; `test_batch_rejects_more_than_1000`; `test_get_logs_filter_by_level`; `test_get_logs_filter_by_service`; `test_get_logs_pagination` — AC: `pytest tests/integration/test_logs_api.py` passes all 7 tests against the SQLite test DB
- [ ] Task 35 — `tests/integration/test_metrics_api.py` — `test_summary_returns_all_fields`; `test_health_score_is_between_0_and_100`; `test_health_score_formula` (inject known error_rate, assert computed score); `test_timeseries_returns_points_after_seeding`; `test_timeseries_rejects_invalid_metric` — AC: `pytest tests/integration/test_metrics_api.py` passes all 5 tests
- [ ] Task 36 — `tests/integration/test_alerts_api.py` — `test_get_alerts_returns_empty_initially`; `test_get_alert_by_id_returns_404_for_missing`; `test_acknowledge_open_alert`; `test_acknowledge_already_acked_returns_400`; `test_resolve_alert`; `test_resolve_already_resolved_returns_400` — AC: `pytest tests/integration/test_alerts_api.py` passes all 6 tests
- [ ] Task 37 — `tests/smoke_test.py` — Standalone Python script (no pytest) executing 8 steps sequentially: (1) GET /health assert 200; (2) POST /simulate/seed-all-services assert 201; (3) POST /simulate/error-spike assert 201; (4) sleep 20s for watchdog cycle; (5) GET /alerts assert `total ≥ 1`; (6) GET /metrics/summary assert `active_alerts ≥ 1`; (7) GET /webhooks/{id}/deliveries assert at least 1 delivery record; (8) print PASS/FAIL per step with elapsed ms — AC: `python tests/smoke_test.py` against a running server with a pre-registered webhook prints all 8 steps as PASS and exits 0

---

## Progress Tracker

| Branch | Tasks | Done | Remaining |
|---|---|---|---|
| feature/project-scaffolding | 5 | 5 | 0 |
| feature/database-models | 4 | 4 | 0 |
| feature/log-ingestion-api | 4 | 4 | 0 |
| feature/anomaly-engine | 3 | 0 | 3 |
| feature/alert-manager | 2 | 0 | 2 |
| feature/webhook-dispatcher | 3 | 0 | 3 |
| feature/watchdog-scheduler | 2 | 0 | 2 |
| feature/log-simulator | 2 | 0 | 2 |
| feature/streamlit-dashboard | 4 | 0 | 4 |
| feature/smoke-tests | 8 | 0 | 8 |
| **TOTAL** | **37** | **13** | **24** |
