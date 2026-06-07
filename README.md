# Intelligent Observability & Event Watchdog

A Python-based, API-first SRE observability platform that ingests application
logs, detects anomalies using statistical and ML logic (Z-score + IsolationForest),
fires simulated webhook alerts on threshold breaches, and visualizes service
health trends on a live Streamlit dashboard.

**Graduate Vibe Coding Challenge — Project 3: Site Reliability Engineering**

---

## Architecture Overview

```
FastAPI (REST API)  ──▶  PostgreSQL (Supabase)
       │
       ├── POST /api/v1/logs/ingest          Log ingestion
       ├── GET  /api/v1/metrics/summary      Health KPIs
       ├── GET  /api/v1/alerts               Alert feed
       └── POST /api/v1/simulate/*           Demo traffic

APScheduler (background)
       └── Watchdog cycle (every 60s)
             ├── Aggregate logs → MetricSnapshot
             ├── Detect anomalies (Tier 1 / 2 / 3)
             ├── Create Alert rows
             └── Dispatch webhook POSTs

Streamlit Dashboard (separate process, auto-refresh 5s)
       ├── Panel 1: Metric cards (health score, error rate, alerts)
       ├── Panel 2: Service health table
       ├── Panel 3: Error trend line chart (Plotly)
       └── Panel 4: Alert feed (color-coded by severity)
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Git | any | |
| Supabase account | free tier | [supabase.com](https://supabase.com) |
| pip | bundled | |

---

## Setup

### 1. Clone the repository

```bash
git clone git@github.com:rogerortiza/Intelligent-Observability-Event-Watchdog.git
cd Intelligent-Observability-Event-Watchdog
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Supabase

1. Create a free project at [supabase.com](https://supabase.com).
2. Go to **Settings → Database → Connection string → URI**.
3. Copy the URI — it looks like:
   ```
   postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
   ```

### 5. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and set **at minimum**:

```
SUPABASE_DB_URL=postgresql://postgres:<your-password>@db.<your-project>.supabase.co:5432/postgres
```

All other variables have sensible defaults and do not need to be changed for local development.

---

## Running the API

```bash
uvicorn app.main:app --reload
```

The API starts at **http://localhost:8000**.

| URL | Description |
|---|---|
| http://localhost:8000/docs | Swagger UI — interactive API explorer |
| http://localhost:8000/redoc | ReDoc API reference |
| http://localhost:8000/api/v1/health | Health check |

On first start the app creates all database tables automatically via SQLAlchemy.

---

## Running the Dashboard

In a **separate terminal** (with the API already running):

```bash
streamlit run dashboard/app.py
```

The dashboard opens at **http://localhost:8501** and auto-refreshes every 5 seconds.

---

## Seeding Demo Data

Use the simulate endpoints to generate realistic traffic without a real log source:

```bash
# Seed baseline traffic across all 5 built-in services
curl -X POST http://localhost:8000/api/v1/simulate/seed-all-services

# Inject an error spike to trigger anomaly detection
curl -X POST http://localhost:8000/api/v1/simulate/error-spike \
  -H "Content-Type: application/json" \
  -d '{"service": "auth-service", "error_count": 30, "spike_duration_minutes": 5}'

# Manually trigger one watchdog cycle (no need to wait 60s)
curl -X POST http://localhost:8000/api/v1/simulate/run-watchdog
```

After the watchdog cycle completes, alerts will appear in the dashboard and any
registered webhooks will receive a POST.

---

## Registering a Webhook

```bash
curl -X POST http://localhost:8000/api/v1/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Webhook",
    "url": "https://webhook.site/<your-uuid>",
    "min_severity": "MEDIUM"
  }'
```

Use [webhook.site](https://webhook.site) to inspect received payloads in real time.

---

## CI/CD

The project uses GitHub Actions (`.github/workflows/ci.yml`) with three jobs:

| Job | Trigger | What it does |
|---|---|---|
| `lint` | every push | `ruff check .` |
| `test` | every push (after lint) | pytest unit + integration with coverage; uses local SQLite |
| `smoke-test` | PR → main only (after test) | starts FastAPI server, polls `/health`, runs `smoke_test.py` |

### Required GitHub Secret

Before CI can run the smoke-test job, add this secret in your repository:

**Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `SUPABASE_DB_URL` | Your full Supabase PostgreSQL connection string |

The `lint` and `test` jobs do **not** require this secret — they use a local SQLite database via `TEST_DATABASE_URL`.

---

## Running Tests

### Unit + Integration tests (against local SQLite — never touches Supabase)

```bash
pytest tests/ -v
```

### Smoke test (requires the API to be running)

```bash
python tests/smoke_test.py
```

Expected output:

```
[PASS] Step 1: GET /health returned 200
[PASS] Step 2: Seeded all services
[PASS] Step 3: Injected error spike
[PASS] Step 4: Watchdog cycle complete
[PASS] Step 5: Alert created (total=1)
[PASS] Step 6: active_alerts >= 1 in summary
[PASS] Step 7: Webhook delivery recorded
All 7 steps passed in 24.3s
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `SUPABASE_DB_URL` | **YES** | — | PostgreSQL connection string |
| `DEBUG` | no | `false` | Enable SQLAlchemy query logging |
| `ERROR_COUNT_THRESHOLD` | no | `10` | Hard error count threshold per window |
| `ERROR_RATE_THRESHOLD` | no | `0.25` | Hard error rate threshold (0–1) |
| `LATENCY_THRESHOLD_MS` | no | `2000` | Hard latency threshold (ms) |
| `ZSCORE_THRESHOLD` | no | `2.5` | Z-score standard deviations for alert |
| `VOLUME_ZSCORE_THRESHOLD` | no | `3.0` | Z-score threshold for volume spikes |
| `WATCHDOG_INTERVAL_SECONDS` | no | `60` | Watchdog cycle frequency |
| `METRIC_WINDOW_MINUTES` | no | `5` | Aggregation window size |
| `BASELINE_LOOKBACK_WINDOWS` | no | `60` | Windows used for statistical baseline |
| `ISOLATION_FOREST_MIN_SAMPLES` | no | `20` | Min windows before IsolationForest runs |
| `API_BASE_URL` | no | `http://localhost:8000` | FastAPI base URL for Streamlit |
| `TEST_DATABASE_URL` | no | `sqlite:///./test_watchdog.db` | Isolated test database |

---

## Project Structure

```
.
├── app/
│   ├── config.py               Settings (Pydantic BaseSettings)
│   ├── database.py             SQLAlchemy engine + session factory
│   ├── models.py               ORM models (5 tables)
│   ├── schemas.py              Pydantic I/O schemas
│   ├── main.py                 FastAPI app + lifespan + health endpoint
│   ├── routers/
│   │   ├── logs.py             Log ingestion + query
│   │   ├── metrics.py          Health KPIs + time series
│   │   ├── alerts.py           Alert lifecycle (ACK, resolve)
│   │   ├── webhooks.py         Webhook CRUD + delivery history
│   │   └── simulate.py         Faker-powered demo traffic
│   └── services/
│       ├── anomaly_detector.py Three-tier detection engine
│       ├── watchdog.py         APScheduler background loop
│       └── webhook_dispatcher.py httpx webhook sender
├── dashboard/
│   └── app.py                  Streamlit dashboard
├── tests/
│   ├── conftest.py             Test DB setup + fixtures
│   ├── unit/
│   │   └── test_anomaly_detector.py
│   ├── integration/
│   │   ├── test_logs_api.py
│   │   ├── test_metrics_api.py
│   │   └── test_alerts_api.py
│   └── smoke_test.py
├── .env.example                Environment variable template
├── requirements.txt            Pinned dependencies
└── specifications.md           Full technical specification
```

---

## Tech Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI 0.115 + Uvicorn |
| Database | Supabase PostgreSQL (free tier) |
| ORM | SQLAlchemy 2.0 (sync) + psycopg2-binary |
| Anomaly Detection | NumPy (Z-score) + scikit-learn (IsolationForest) |
| Scheduler | APScheduler 3.10 |
| Webhook Dispatch | httpx |
| Log Simulation | Faker |
| Dashboard | Streamlit 1.39 + Plotly |
| Testing | pytest + pytest-asyncio |
