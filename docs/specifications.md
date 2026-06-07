# Specifications — Intelligent Observability & Event Watchdog

**Project:** Graduate Vibe Coding Challenge — Project 3  
**Focus:** Site Reliability Engineering (SRE)  
**Session start:** 2026-06-07 09:48 CST  

---

## 1. Project Overview and Goals

### What It Is
A Python-based, API-first observability platform that ingests application and platform logs, detects anomalies and error spikes using AI/statistical logic, triggers simulated webhook alerts when thresholds are breached, and visualizes service health trends on a live dashboard.

### Goals
| Goal | Success Criteria |
|---|---|
| Log Ingestion | Accept structured log events via REST API (single + batch) |
| Anomaly Detection | Three-tier detection: hard threshold → Z-score → IsolationForest |
| Alert Generation | Persist Alert rows, assign severity, fire webhook on trigger |
| Webhook Simulation | POST to registered URLs with signed payload; log delivery result |
| Health Dashboard | Streamlit app with real-time metric cards, line chart, alert feed |
| MVP Timeline | Functional end-to-end in 4–6 hours (hard cap 16h) |

### Scope (MVP)
- Structured JSON log ingestion only (no raw syslog parsing)
- Simulated log traffic via `/simulate/*` endpoints (Faker-powered)
- Webhook delivery is HTTP POST to any URL (simulated via webhook.site or local echo server)
- Single PostgreSQL database (Supabase free tier)
- Two processes: FastAPI server + Streamlit dashboard (run separately)

---

## 2. Full Tech Stack with Versions

```
fastapi==0.115.0           # API framework
uvicorn[standard]==0.30.6  # ASGI server
sqlalchemy==2.0.35         # ORM (sync engine)
psycopg2-binary==2.9.9     # PostgreSQL driver
apscheduler==3.10.4        # Background watchdog scheduler
httpx==0.27.2              # Async HTTP client for webhook dispatch
numpy==2.1.1               # Z-score calculations
scikit-learn==1.5.2        # IsolationForest anomaly detection
faker==30.3.0              # Realistic log message generation
pydantic-settings==2.5.2   # Settings from .env
python-multipart==0.0.12   # FastAPI form support
python-dotenv==1.0.1       # .env file loading
streamlit==1.39.0          # Dashboard UI
streamlit-autorefresh==1.0.1  # 5-second auto-refresh component
plotly==5.24.1             # Interactive time-series charts
pandas==2.2.3              # DataFrame manipulation for Streamlit
```

**Runtime:** Python 3.11+  
**Database:** Supabase PostgreSQL (free tier, hosted)  
**OS:** macOS / Linux compatible

---

## 3. Development Standards

### Python Best Practices
- Type hints on all function signatures and class attributes
- Docstrings on all public functions, classes, and modules (Google style)
- No magic numbers — use named constants in `config.py`
- All exceptions caught explicitly — no bare `except:`
- Use `pathlib` over `os.path`
- Max line length: 88 characters (Black formatter standard)
- Imports ordered: stdlib → third-party → local (isort compatible)

### Design Patterns

| Pattern | Where Applied |
|---|---|
| Repository | All database access — no raw queries inside routers |
| Dependency Injection | FastAPI `Depends()` for DB sessions and services |
| Factory | Service instantiation in FastAPI lifespan |
| Strategy | Anomaly detection tiers — each tier is an interchangeable strategy |

### SOLID Principles

| Principle | Application |
|---|---|
| Single Responsibility | Each file/class has one purpose only |
| Open/Closed | New anomaly tiers can be added without modifying existing ones |
| Liskov Substitution | All anomaly strategies are interchangeable via a common interface |
| Interface Segregation | Schemas are lean — no god-objects |
| Dependency Inversion | Routers depend on service abstractions, not concrete implementations |

---

## 4. Complete File Structure

```
VibeCodingChallenge/
│
├── app/                              # FastAPI application package
│   ├── __init__.py
│   ├── config.py                     # Pydantic BaseSettings; reads all config from .env
│   ├── database.py                   # Sync SQLAlchemy engine, SessionLocal, Base, init_db()
│   ├── models.py                     # ORM table definitions (all five models)
│   ├── schemas.py                    # Pydantic request/response schemas
│   ├── main.py                       # FastAPI app factory, lifespan, router mounts, /health
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── logs.py                   # Log ingestion and query endpoints
│   │   ├── metrics.py                # Metric summary and time-series endpoints
│   │   ├── alerts.py                 # Alert list, detail, acknowledge, resolve
│   │   ├── webhooks.py               # Webhook CRUD and delivery history
│   │   └── simulate.py               # Demo traffic generators using Faker
│   │
│   └── services/
│       ├── __init__.py
│       ├── anomaly_detector.py       # Three-tier detection logic
│       ├── watchdog.py               # APScheduler job: aggregate → detect → alert → dispatch
│       └── webhook_dispatcher.py     # httpx POST sender; persists WebhookDelivery records
│
├── dashboard/
│   └── app.py                        # Streamlit dashboard (auto-refresh, cards, chart, feed)
│
├── .env.example                      # Template for required environment variables
├── requirements.txt                  # Pinned dependencies
├── specifications.md                 # This file
├── prompts.md                        # Audit log of all session prompts
└── README.md                         # Setup and run instructions
```

---

## 5. Database Models

All tables use PostgreSQL via SQLAlchemy ORM (sync). Primary keys are auto-increment integers. Timestamps are naive UTC datetimes (no timezone column — stored as UTC, handled in Python).

---

### 4.1 `LogEntry` — Table: `log_entries`

Represents a single ingested log event from any service.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, auto-increment, indexed | Row identifier |
| `timestamp` | DateTime | NOT NULL, indexed, default=utcnow | Event timestamp (UTC) |
| `level` | Enum(LogLevel) | NOT NULL, indexed | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `service` | String(100) | NOT NULL, indexed | Originating service name |
| `message` | Text | NOT NULL | Log message body |
| `latency_ms` | Float | nullable | Request/operation latency in milliseconds |
| `host` | String(100) | nullable | Originating hostname or pod name |
| `trace_id` | String(64) | nullable | Distributed trace identifier |
| `extra` | JSON | nullable | Arbitrary additional metadata |
| `ingested_at` | DateTime | NOT NULL, default=utcnow | When the API received this entry |

**Enum `LogLevel`:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

---

### 4.2 `MetricSnapshot` — Table: `metric_snapshots`

Aggregated statistics for one service over one time window. Created by the watchdog each cycle.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, auto-increment, indexed | Row identifier |
| `window_start` | DateTime | NOT NULL, indexed | Start of aggregation window (UTC) |
| `window_end` | DateTime | NOT NULL | End of aggregation window (UTC) |
| `service` | String(100) | NOT NULL, indexed | Service name |
| `total_logs` | Integer | NOT NULL, default=0 | Total log entries in window |
| `error_count` | Integer | NOT NULL, default=0 | ERROR + CRITICAL count |
| `warning_count` | Integer | NOT NULL, default=0 | WARNING count |
| `error_rate` | Float | NOT NULL, default=0.0 | error_count / total_logs |
| `avg_latency_ms` | Float | nullable | Mean latency (null if no latency data) |
| `p95_latency_ms` | Float | nullable | 95th-percentile latency |
| `max_latency_ms` | Float | nullable | Maximum observed latency |
| `error_zscore` | Float | nullable | Z-score of error_count vs. baseline |
| `volume_zscore` | Float | nullable | Z-score of total_logs vs. baseline |
| `latency_zscore` | Float | nullable | Z-score of avg_latency_ms vs. baseline |
| `created_at` | DateTime | NOT NULL, default=utcnow | Row insert time |

---

### 4.3 `Alert` — Table: `alerts`

A triggered anomaly event. One snapshot can produce multiple alerts (one per anomaly type).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, auto-increment, indexed | Row identifier |
| `alert_type` | Enum(AlertType) | NOT NULL, indexed | ERROR_RATE_SPIKE / LOG_VOLUME_SPIKE / LATENCY_SPIKE / THRESHOLD_BREACH / ISOLATION_FOREST |
| `severity` | Enum(AlertSeverity) | NOT NULL | LOW / MEDIUM / HIGH / CRITICAL |
| `status` | Enum(AlertStatus) | NOT NULL, default=OPEN, indexed | OPEN / ACKNOWLEDGED / RESOLVED |
| `service` | String(100) | NOT NULL, indexed | Affected service |
| `title` | String(255) | NOT NULL | Short human-readable alert title |
| `description` | Text | NOT NULL | Full description with values and thresholds |
| `metric_value` | Float | nullable | The anomalous observed value |
| `threshold_value` | Float | nullable | The threshold that was breached (if applicable) |
| `zscore` | Float | nullable | Z-score at time of detection |
| `snapshot_id` | Integer | FK → metric_snapshots.id, nullable | Source snapshot |
| `triggered_at` | DateTime | NOT NULL, default=utcnow, indexed | When the alert was created |
| `acknowledged_at` | DateTime | nullable | When ACKed |
| `resolved_at` | DateTime | nullable | When resolved |

**Enum `AlertType`:** `ERROR_RATE_SPIKE`, `LOG_VOLUME_SPIKE`, `LATENCY_SPIKE`, `THRESHOLD_BREACH`, `ISOLATION_FOREST`  
**Enum `AlertSeverity`:** `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`  
**Enum `AlertStatus`:** `OPEN`, `ACKNOWLEDGED`, `RESOLVED`

---

### 4.4 `WebhookConfig` — Table: `webhook_configs`

A registered external URL to receive alert payloads via HTTP POST.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, auto-increment, indexed | Row identifier |
| `name` | String(100) | NOT NULL | Human label for this webhook |
| `url` | String(512) | NOT NULL | Destination URL |
| `secret` | String(256) | nullable | HMAC-SHA256 signing secret |
| `active` | Boolean | NOT NULL, default=True | Whether deliveries are enabled |
| `min_severity` | Enum(AlertSeverity) | NOT NULL, default=MEDIUM | Minimum severity to trigger this webhook |
| `alert_types` | JSON (list) | nullable | Filter to specific alert types; null = all types |
| `created_at` | DateTime | NOT NULL, default=utcnow | Registration time |

---

### 4.5 `WebhookDelivery` — Table: `webhook_deliveries`

Audit record of every webhook POST attempt (success or failure).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, auto-increment, indexed | Row identifier |
| `webhook_id` | Integer | FK → webhook_configs.id, NOT NULL | Which webhook config |
| `alert_id` | Integer | FK → alerts.id, NOT NULL | Which alert triggered this |
| `status` | Enum(WebhookStatus) | NOT NULL, default=PENDING | PENDING / SUCCESS / FAILED |
| `status_code` | Integer | nullable | HTTP response code received |
| `response_body` | Text | nullable | First 2000 chars of response body |
| `error_message` | Text | nullable | Exception message on network failure |
| `payload` | JSON | nullable | Exact JSON body sent |
| `delivered_at` | DateTime | NOT NULL, default=utcnow | Attempt timestamp |

**Enum `WebhookStatus`:** `PENDING`, `SUCCESS`, `FAILED`

---

## 6. API Endpoints

Base path: `/api/v1`  
All request/response bodies are JSON. All list endpoints return a `PaginatedResponse` wrapper.

```json
// PaginatedResponse
{ "items": [...], "total": 0, "limit": 100, "offset": 0 }
```

---

### 5.1 Logs

#### `POST /api/v1/logs/ingest`
Ingest a single log entry.

**Request body:**
```json
{
  "timestamp": "2026-06-07T10:00:00Z",   // optional, defaults to now
  "level": "ERROR",                        // required: DEBUG|INFO|WARNING|ERROR|CRITICAL
  "service": "auth-service",              // required
  "message": "Connection timeout",        // required
  "latency_ms": 1540.0,                   // optional
  "host": "pod-1.auth-service",           // optional
  "trace_id": "ab12cd34",                 // optional
  "extra": {"user_id": 42}               // optional
}
```
**Response:** `201 LogEntryOut` (full row with `id` and `ingested_at`)

---

#### `POST /api/v1/logs/ingest/batch`
Ingest 1–1000 log entries in one request.

**Request body:** `{ "logs": [LogEntryCreate, ...] }`  
**Response:** `201 { "message": "...", "count": N }`

---

#### `GET /api/v1/logs`
Query log entries with optional filters.

**Query params:** `service`, `level`, `start_time`, `end_time`, `limit` (1–1000, default 100), `offset`  
**Response:** `200 PaginatedResponse<LogEntryOut>` ordered by `timestamp DESC`

---

### 5.2 Metrics

#### `GET /api/v1/metrics/summary`
24-hour aggregate KPIs across all services.

**Response:**
```json
{
  "total_logs_24h": 4820,
  "error_rate_24h": 0.0312,
  "error_count_24h": 150,
  "active_alerts": 3,
  "services_monitored": 5,
  "avg_latency_ms": 243.7,
  "health_score": 84.4,
  "last_updated": "2026-06-07T15:30:00"
}
```
**Health score formula:** `max(0, min(100, 100 - error_rate*50 - active_alerts*5))`

---

#### `GET /api/v1/metrics/timeseries`
Time-series data from MetricSnapshot for charting.

**Query params:** `metric` (error_count|total_logs|avg_latency_ms|error_rate), `service` (optional filter), `hours` (1–168, default 24)  
**Response:**
```json
{
  "metric": "error_count",
  "service": "auth-service",
  "points": [
    { "timestamp": "2026-06-07T10:00:00", "value": 3.0, "service": "auth-service" }
  ]
}
```

---

#### `GET /api/v1/metrics/snapshots`
Paginated MetricSnapshot history.

**Query params:** `service`, `hours`, `limit`, `offset`  
**Response:** `200 PaginatedResponse<MetricSnapshotOut>`

---

### 5.3 Alerts

#### `GET /api/v1/alerts`
**Query params:** `status`, `severity`, `alert_type`, `service`, `limit`, `offset`  
**Response:** `200 PaginatedResponse<AlertOut>` ordered by `triggered_at DESC`

#### `GET /api/v1/alerts/{alert_id}`
**Response:** `200 AlertOut` or `404`

#### `PUT /api/v1/alerts/{alert_id}/acknowledge`
**Request body:** `{ "note": "optional string" }`  
**Response:** `200 AlertOut` with `status=ACKNOWLEDGED`, `acknowledged_at` set. Returns `400` if already non-OPEN.

#### `PUT /api/v1/alerts/{alert_id}/resolve`
**Response:** `200 AlertOut` with `status=RESOLVED`, `resolved_at` set. Returns `400` if already resolved.

---

### 5.4 Webhooks

#### `POST /api/v1/webhooks`
**Request body:**
```json
{
  "name": "Slack Alerts",
  "url": "https://hooks.slack.com/...",
  "secret": "optional-hmac-secret",
  "min_severity": "HIGH",
  "alert_types": ["ERROR_RATE_SPIKE", "LATENCY_SPIKE"]
}
```
**Response:** `201 WebhookOut`

#### `GET /api/v1/webhooks` → `200 [WebhookOut]`
#### `GET /api/v1/webhooks/{id}` → `200 WebhookOut` or `404`
#### `DELETE /api/v1/webhooks/{id}` → `204`
#### `PUT /api/v1/webhooks/{id}/toggle` → `200 WebhookOut` (flips `active`)
#### `GET /api/v1/webhooks/{id}/deliveries` → `200 PaginatedResponse<WebhookDeliveryOut>`

---

### 5.5 Simulate

#### `POST /api/v1/simulate/normal-traffic`
**Request body:** `{ "service": "api-gateway", "count": 50, "error_rate": 0.05 }`  
Generates `count` realistic log entries using Faker. `error_rate` controls the fraction of ERROR/CRITICAL.  
**Response:** `201 { "message": "...", "logs_created": 50, "service": "api-gateway" }`

#### `POST /api/v1/simulate/error-spike`
**Request body:** `{ "service": "api-gateway", "error_count": 50, "spike_duration_minutes": 5 }`  
Injects an error burst (intended to trigger anomaly detection on the next watchdog cycle).  
**Response:** `201 SimulateResponse`

#### `POST /api/v1/simulate/run-watchdog`
Manually triggers one watchdog cycle in the background (no waiting for the scheduler interval).  
**Response:** `200 { "message": "Watchdog cycle triggered in background" }`

#### `POST /api/v1/simulate/seed-all-services`
Seeds realistic mixed-level logs across all five built-in services.  
**Response:** `201 { "message": "...", "services": [...] }`

---

### 5.6 Health

#### `GET /api/v1/health`
**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "postgresql",
  "watchdog": "running",
  "uptime_seconds": 142.3
}
```

---

## 7. Anomaly Detection Logic

The detector runs once per watchdog cycle on every new `MetricSnapshot`. Three tiers are evaluated in sequence; any firing tier creates an `Alert`.

---

### Tier 1 — Hard Threshold (always evaluated, no history required)

| Metric | Condition | Severity |
|---|---|---|
| `error_count` | `≥ ERROR_COUNT_THRESHOLD` (default: 10) | HIGH |
| `error_rate` | `≥ ERROR_RATE_THRESHOLD` (default: 0.25) | HIGH |
| `avg_latency_ms` | `≥ LATENCY_THRESHOLD_MS` (default: 2000) | HIGH |

Both error_count and error_rate breaching simultaneously → CRITICAL.

---

### Tier 2 — Z-score Statistical Detection (requires ≥ 5 prior windows)

**Baseline:** Last `BASELINE_LOOKBACK_WINDOWS` (default: 60) MetricSnapshot rows for the same service, ordered by `window_start DESC`.

**Formula:**
```
z = (current_value - mean(baseline)) / std(baseline)
```
If `std < 1e-9` (flat baseline), skip (returns None — no false positives on stable services).

**Trigger:** `|z| ≥ ZSCORE_THRESHOLD` (default: 2.5)

**Severity mapping:**
| |z| range | Severity |
|---|---|---|
| ≥ 5.0 | CRITICAL |
| ≥ 4.0 | HIGH |
| ≥ 3.0 | MEDIUM |
| < 3.0 | LOW |

**Applied to:** `error_count`, `total_logs` (volume), `avg_latency_ms`

---

### Tier 3 — IsolationForest (requires ≥ 20 prior windows for model fit)

**Feature vector per snapshot:**
```python
X = [error_count, total_logs, avg_latency_ms or 0.0]
```

**Training data:** Last `BASELINE_LOOKBACK_WINDOWS` snapshots for the service.  

**Model:** `sklearn.ensemble.IsolationForest(contamination=0.05, random_state=42)`  
Fitted fresh each watchdog cycle on the baseline windows (lightweight — max 60 rows).

**Trigger condition:**
- `model.decision_function([current_vector])[0] < -0.1` (negative = anomalous)
- AND `model.predict([current_vector])[0] == -1` (IsolationForest label: -1 = outlier)

**Alert type:** `ISOLATION_FOREST`  
**Severity:** Derived from the raw anomaly score:
- score < -0.3 → CRITICAL
- score < -0.2 → HIGH  
- score < -0.1 → MEDIUM

**Note:** Tiers 1 and 2 may already have fired for the same snapshot. Tier 3 fires independently. Deduplication is intentionally absent at MVP — operators see all signals.

---

### Watchdog Cycle Flow

```
Every WATCHDOG_INTERVAL_SECONDS (default: 60):
  1. window_end   = utcnow()
     window_start = window_end - METRIC_WINDOW_MINUTES (default: 5)
  2. SELECT DISTINCT service FROM log_entries WHERE timestamp IN [window_start, window_end)
  3. For each service:
     a. Skip if MetricSnapshot already exists for this (service, window_start)
     b. Aggregate LogEntry rows → MetricSnapshot (compute all fields)
     c. INSERT MetricSnapshot; flush to get ID
     d. Run Tier 1 → Tier 2 → Tier 3 detection
     e. INSERT Alert for each AnomalyResult
  4. COMMIT transaction
  5. For each new Alert: call webhook_dispatcher.dispatch_alert()
```

---

## 8. Streamlit Dashboard

**File:** `dashboard/app.py`  
**Run:** `streamlit run dashboard/app.py`  
**Auto-refresh:** `streamlit-autorefresh` component, interval = 5000 ms (5 seconds)

### Panels

#### Panel 1 — Metric Cards (top row, 4 columns)
Fetches `GET /api/v1/metrics/summary`

| Card | Value | Delta color |
|---|---|---|
| Health Score | `health_score` % | green ≥ 80, yellow ≥ 60, red < 60 |
| Total Logs (24h) | `total_logs_24h` | neutral |
| Error Rate (24h) | `error_rate_24h` % | inverse (lower = better) |
| Active Alerts | `active_alerts` | inverse |

#### Panel 2 — Service Health Table (second row)
Fetches `GET /api/v1/metrics/snapshots?hours=1&limit=500`  
Groups by service; shows latest snapshot per service with error_rate bar.

#### Panel 3 — Health Trend Line Chart (third row)
Fetches `GET /api/v1/metrics/timeseries?metric=error_count&hours=24`  
Renders Plotly line chart. Service selector dropdown in sidebar.  
X-axis: `window_start`, Y-axis: `error_count`. Second trace: `total_logs` on secondary Y-axis.

#### Panel 4 — Alert Feed Table (fourth row)
Fetches `GET /api/v1/alerts?limit=50`  
`st.dataframe` with conditional row styling:
- CRITICAL → red background (`#7f1d1d`)
- HIGH → orange background (`#7c2d12`)
- MEDIUM → yellow background (`#713f12`)
- LOW → green background (`#14532d`)
- ACKNOWLEDGED → muted
- RESOLVED → strikethrough (via HTML in `st.markdown`)

Columns shown: `triggered_at`, `severity`, `alert_type`, `service`, `title`, `status`, `zscore`

#### Sidebar
- Service selector (multiselect, feeds chart)
- Simulate buttons: "Seed Normal Traffic", "Inject Error Spike", "Run Watchdog Now"
- Calls respective `/api/v1/simulate/*` endpoints via `requests` (sync)

---

## 9. Environment Variables

File: `.env` (copy from `.env.example`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `SUPABASE_DB_URL` | **YES** | — | Full PostgreSQL connection string: `postgresql://user:password@host:port/dbname` |
| `DEBUG` | no | `false` | Enable SQLAlchemy query logging |
| `ERROR_COUNT_THRESHOLD` | no | `10` | Hard threshold: error count per window |
| `ERROR_RATE_THRESHOLD` | no | `0.25` | Hard threshold: error rate (0.0–1.0) |
| `LATENCY_THRESHOLD_MS` | no | `2000` | Hard threshold: avg latency in ms |
| `ZSCORE_THRESHOLD` | no | `2.5` | Standard deviations for Z-score alert |
| `VOLUME_ZSCORE_THRESHOLD` | no | `3.0` | Z-score threshold for volume spike |
| `WATCHDOG_INTERVAL_SECONDS` | no | `60` | How often the watchdog runs |
| `METRIC_WINDOW_MINUTES` | no | `5` | Aggregation window size |
| `BASELINE_LOOKBACK_WINDOWS` | no | `60` | Prior windows used for baseline |
| `ISOLATION_FOREST_MIN_SAMPLES` | no | `20` | Min windows before IsolationForest runs |
| `API_BASE_URL` | no | `http://localhost:8000` | Used by Streamlit to call FastAPI |

**`.env.example` content:**
```
SUPABASE_DB_URL=postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres
DEBUG=false
ERROR_COUNT_THRESHOLD=10
ERROR_RATE_THRESHOLD=0.25
LATENCY_THRESHOLD_MS=2000
ZSCORE_THRESHOLD=2.5
VOLUME_ZSCORE_THRESHOLD=3.0
WATCHDOG_INTERVAL_SECONDS=60
METRIC_WINDOW_MINUTES=5
BASELINE_LOOKBACK_WINDOWS=60
ISOLATION_FOREST_MIN_SAMPLES=20
API_BASE_URL=http://localhost:8000
```

---

## 10. Testing Strategy

**Philosophy:** Lean but functional — enough to prove the end-to-end pipeline works, not full coverage.

### Test Types

| Type | Tool | Scope |
|---|---|---|
| Unit | pytest | `anomaly_detector.py` functions in isolation |
| Integration | pytest + httpx | FastAPI endpoints against a real test DB |
| Smoke | Python script | Full pipeline: ingest → detect → alert → webhook |

### File Structure

```
tests/
├── __init__.py
├── conftest.py                        # DB setup/teardown, FastAPI test client, fixtures
├── unit/
│   └── test_anomaly_detector.py       # Z-score, IsolationForest, severity classification
├── integration/
│   ├── test_logs_api.py               # POST /logs, POST /logs/ingest/batch, GET /logs
│   ├── test_metrics_api.py            # GET /metrics/summary, GET /metrics/timeseries
│   └── test_alerts_api.py             # GET /alerts, PUT acknowledge/resolve
└── smoke_test.py                      # Full end-to-end pipeline validation
```

### Smoke Test Flow

1. `GET /health` — confirm API is up
2. `POST /simulate/seed-all-services` — generate baseline logs
3. `POST /simulate/error-spike` — inject anomaly trigger
4. Wait 20 seconds for watchdog cycle
5. `GET /api/v1/alerts` — assert at least 1 alert created
6. `GET /api/v1/metrics/summary` — assert `active_alerts ≥ 1`
7. `GET /api/v1/webhooks/{id}/deliveries` — assert webhook was fired
8. Print `PASS` / `FAIL` per step with elapsed time

### Test Database

Use a separate `TEST_DATABASE_URL` in `.env.example` pointing to a **local SQLite instance** (`sqlite:///./test_watchdog.db`). The `conftest.py` creates all tables before each test session and drops them after. Never run tests against the production Supabase database.

### Test Dependencies

Added to `requirements.txt` under a `# [test]` comment:

```
# [test]
pytest==8.3.3
pytest-asyncio==0.24.0
# httpx==0.27.2 already included above
```

---

## 11. V2 Roadmap (Out of Scope for MVP)

| Feature | Description | Rationale |
|---|---|---|
| **Real Webhook Delivery via AWS SNS** | Replace simulated HTTP webhook with an SNS topic. FastAPI publishes to SNS; subscribers (Slack, PagerDuty, email) receive notifications natively. | Production-grade fan-out with retry, dead-letter queue, subscription management |
| **CloudWatch as Log Source** | Add a log poller service that reads from AWS CloudWatch Logs via `boto3`. Map CW log events to `LogEntry` schema and ingest. | Real SRE use case — no more simulated logs |
| **EC2/ECS Deployment** | Dockerize FastAPI + Streamlit. Deploy to ECS Fargate (free tier eligible). Use RDS PostgreSQL instead of Supabase. Add ALB for HTTPS. | Move from dev laptop to always-on cloud deployment |
| **Grafana Integration** | Expose `/metrics` in Prometheus format via `prometheus-fastapi-instrumentator`. Connect to Grafana Cloud (free tier). | Industry-standard observability stack |
| **Log Parsing from Files** | Accept raw log file uploads (multipart) and parse common formats: JSON lines, Apache Combined, syslog. | Widens ingestion surface beyond structured API |
| **Alert Deduplication** | Suppress duplicate alerts for the same (service, alert_type) within a cooldown window (default: 15 min). | Reduce alert fatigue in sustained incident scenarios |
| **Multi-Tenant Services** | Add an `Organization` model and API key authentication. Partition all data by org. | Enterprise SaaS readiness |
| **Runbook Automation** | When an alert is created, auto-lookup a remediation runbook (stored as markdown in DB) and attach it to the alert payload. | Reduces MTTR for known failure patterns |

---

## 12. Branching Strategy

**Model:** GitHub Flow (simplified)

| Branch | Purpose |
|---|---|
| `main` | Stable, always deployable |
| `feature/*` | One branch per feature, merged to `main` via PR |

### Branch Naming Convention

| Branch | Covers |
|---|---|
| `feature/project-scaffolding` | Repo init, requirements, `.env.example`, `README.md` |
| `feature/database-models` | `models.py`, `database.py`, `config.py`, migrations |
| `feature/log-ingestion-api` | `routers/logs.py`, `schemas.py` |
| `feature/anomaly-engine` | `services/anomaly_detector.py` (all three tiers) |
| `feature/alert-manager` | `routers/alerts.py`, alert lifecycle (ACK, resolve) |
| `feature/webhook-dispatcher` | `services/webhook_dispatcher.py`, `routers/webhooks.py` |
| `feature/watchdog-scheduler` | `services/watchdog.py`, APScheduler integration |
| `feature/log-simulator` | `routers/simulate.py`, Faker-powered traffic generation |
| `feature/streamlit-dashboard` | `dashboard/app.py`, metric cards, chart, alert feed |
| `feature/smoke-tests` | `tests/` directory, unit + integration + smoke test |

### PR Rules

- Each PR maps to **one architectural layer or feature** (see branch table above)
- PR description must include:
  1. **What was built** — one-paragraph summary
  2. **How to test it** — exact commands to run
  3. **Elapsed time at merge** — cumulative session time
- **Squash merge** to keep `main` history clean (one commit per feature)
- No force-pushes to `main`
- Branch is deleted after merge
