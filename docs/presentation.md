# Intelligent Observability & Event Watchdog
### Graduate Vibe Coding Challenge — Project 3 | Site Reliability Engineering

---

## Slide 1 — Project Title

# Intelligent Observability & Event Watchdog

**Graduate Vibe Coding Challenge — Project 3**
*Site Reliability Engineering (SRE) Track*

- An API-first observability platform built entirely through AI-assisted development
- Ingests structured logs, detects anomalies, fires webhook alerts, and visualizes service health
- Built from zero to production-ready MVP in a single session — under 7 hours
- Zero manual code edits: every line was generated and fixed by Claude Code

> **Session timeline:** 2026-06-07 | Start: 09:48 CST | Completion: ~16:30 CST

---

> **Speaker Notes:**
> This project is a full SRE observability stack — not a tutorial clone, but an original platform
> with a real three-tier anomaly engine, live Streamlit dashboard, and a CI/CD pipeline.
> The headline constraint was "No Manual Edits" — every file, every bugfix, and every PR was
> produced by Claude Code from a single prompt at a time. This slide sets the stakes: a
> production-grade system built in under seven hours with zero hand-written code.

---

## Slide 2 — Problem Statement

# Why Observability Matters

**Modern distributed systems fail silently — and late.**

- Traditional logging dashboards are reactive: engineers see failures *after* users do
- Error spikes in one microservice cascade across auth, payments, and notifications before any alert fires
- Static threshold alerts create noise (too many false positives) or miss subtle degradations
- On-call engineers lack a single pane that shows *why* health is declining, not just *that* it is
- Small teams operating multiple services have no practical way to correlate log volume, latency, and error rate in real time

> **The gap this project fills:**
> An SRE platform that combines hard thresholds for immediate detection, statistical Z-score analysis
> for trend deviation, and machine learning (IsolationForest) for multi-dimensional outlier detection —
> all surfaced through a live dashboard with one-click traffic simulation.

---

> **Speaker Notes:**
> The problem framing is grounded in real SRE pain. Start with "silent failures" — most outages
> begin as subtle anomalies (error rate drifts from 2% to 8%) long before they become incidents.
> The three-tier detection approach directly maps to the progression: catch obvious breaches first
> (Tier 1), catch statistical deviations next (Tier 2), then use ML to catch multi-variable patterns
> that no single threshold would ever catch (Tier 3). Emphasize that this isn't academic — these
> are the same techniques used in DataDog, New Relic, and AWS CloudWatch Anomaly Detection.

---

## Slide 3 — Solution Overview

# API-First Observability Platform

**Four-stage pipeline from log ingestion to visual insight:**

- **Ingest** — REST API accepts structured log events (single or batch up to 1,000); Faker-powered `/simulate/*` endpoints generate realistic traffic for testing
- **Detect** — Watchdog service aggregates logs into 5-minute metric windows and runs three anomaly detection tiers on every new snapshot
- **Alert** — Anomalies become persisted `Alert` rows with severity scoring; active webhooks receive HMAC-signed HTTP POST payloads with full alert context
- **Visualize** — Streamlit dashboard with 5-second auto-refresh shows a Health Score badge, per-service health table, Plotly dual-axis trend chart, and a color-coded alert feed

> **Stack boundary:** Two processes — FastAPI API server + Streamlit dashboard — sharing one Supabase PostgreSQL database via SQLAlchemy ORM.

---

> **Speaker Notes:**
> Walk the audience through the pipeline left to right. A log event enters via POST /logs/ingest,
> lands in the log_entries table, gets aggregated into a MetricSnapshot by the background watchdog,
> analyzed by all three detection tiers, turned into an Alert row, and dispatched to any registered
> webhooks — all within 60 seconds. The Streamlit dashboard reads that same database and surfaces
> the alert in real time. This is a complete, closed-loop observability system with no external
> message brokers or queues in the MVP.

---

## Slide 4 — Tech Stack

# Technology Choices

**Every library selected for production credibility and free-tier availability:**

| Layer | Technology | Version | Why |
|---|---|---|---|
| API | FastAPI + Uvicorn | 0.115.0 / 0.30.6 | Async-capable, typed, auto-docs via OpenAPI |
| Database | Supabase PostgreSQL | hosted | Managed free tier, full Postgres compatibility |
| ORM | SQLAlchemy 2.0 (sync) | 2.0.35 | Industry standard, thread-safe sync engine for background jobs |
| Settings | pydantic-settings | 2.5.2 | Type-validated config from `.env` with zero boilerplate |
| Anomaly ML | scikit-learn IsolationForest | 1.5.2 | Unsupervised outlier detection with no labeled training data required |
| Statistics | numpy | 2.1.1 | Z-score baseline calculations, p95 latency percentiles |
| HTTP Client | httpx | 0.27.2 | Async webhook dispatch with timeout and retry semantics |
| Dashboard | Streamlit + Plotly | 1.39.0 / 5.24.1 | Production-quality data UI with minimal boilerplate |
| Test DB | SQLite (`sqlite:///./test_watchdog.db`) | stdlib | Zero-dependency CI database; same ORM, no Supabase secrets needed |
| CI/CD | GitHub Actions | — | Lint → unit tests → integration tests → smoke test pipeline |

---

> **Speaker Notes:**
> The stack was deliberately chosen to run on free tiers. Supabase gives us a real Postgres instance
> without provisioning a server. SQLAlchemy sync engine was a deliberate choice over async — the
> watchdog runs in a background asyncio task but uses sync SQLAlchemy in a thread pool, which is
> simpler to reason about and avoids async session management complexity. IsolationForest requires
> zero labeled anomaly data, which is realistic for a new platform with no incident history.
> The SQLite test override is a key design decision: CI never touches the production database.

---

## Slide 5 — Architecture

# System Design

**Three-tier anomaly detection engine and layered design patterns:**

### Anomaly Detection Tiers

| Tier | Method | Trigger Condition | Min History |
|---|---|---|---|
| 1 — Hard Threshold | Rule-based | error_count ≥ 10 OR error_rate ≥ 25% OR latency ≥ 2000ms | None |
| 2 — Z-Score | Statistical | \|z\| ≥ 2.5 standard deviations from 60-window baseline | 5 windows |
| 3 — IsolationForest | Machine Learning | anomaly_score < -0.1 AND predict == -1 on feature vector [errors, volume, latency] | 20 windows |

**Dual breach rule:** error_count AND error_rate both breaching simultaneously → CRITICAL (overrides HIGH)

### Design Patterns Applied

- **Strategy** — Each detection tier (`_tier1`, `_tier2`, `_tier3`) is a self-contained function with identical signature; new tiers can be added without modifying the orchestrator
- **Repository** — All DB access goes through SQLAlchemy ORM sessions injected via FastAPI `Depends()`; routers contain no raw SQL
- **Factory** — Watchdog service is instantiated during FastAPI lifespan startup; clean teardown on shutdown
- **Dependency Injection** — `get_db()` generator provides session-per-request; test suite overrides it with SQLite without touching application code

### SOLID Principles

- **Open/Closed** — `detect_anomalies()` orchestrator calls all tiers; adding Tier 4 requires zero changes to existing tiers
- **Single Responsibility** — `anomaly_detector.py` detects, `webhook_dispatcher.py` dispatches, `watchdog.py` orchestrates; no file does two jobs

---

> **Speaker Notes:**
> The three-tier architecture is the core engineering contribution. Tier 1 is fast and cheap —
> catches obvious incidents immediately with no history. Tier 2 catches subtle drift that no fixed
> threshold would catch (e.g., error rate doubles but is still below the hard threshold). Tier 3
> catches multi-variable anomalies: a snapshot with moderate errors, high latency, AND unusual volume
> might not trigger Tier 1 or 2 individually, but IsolationForest sees the combination as an outlier.
> The Strategy pattern means a Tier 4 (LSTM-based sequence detection) could be dropped in with one
> function call in the orchestrator.

---

## Slide 6 — Live Demo Results

# Platform in Action

**End-to-end pipeline validated against Supabase PostgreSQL:**

- **Health Score Dashboard** — The top panel displays a real-time Health Score badge: green (≥ 80%), yellow (60–79%), red (< 60%); after injecting an error spike into `auth-service`, the score drops from 95 → 62 within one watchdog cycle
- **Alert Feed** — The bottom panel shows color-coded rows: CRITICAL alerts in deep red (`#7f1d1d`), HIGH in dark orange (`#7c2d12`), MEDIUM in amber (`#713f12`), LOW in dark green (`#14532d`); RESOLVED alerts display with strikethrough
- **Health Trend Chart** — Plotly dual-axis line chart shows `error_count` (red, left axis) spiking against `total_logs` (blue dotted, right axis) remaining flat — the visual signal that the error *rate* is climbing, not just volume
- **Webhook Delivery** — HMAC-SHA256 signed POST payloads dispatched to registered URLs; `WebhookDelivery` rows persist status code, response body, and error message for every attempt
- **Smoke Test** — `python tests/smoke_test.py` confirms all 8 steps in sequence: seed → spike → watchdog → alerts exist → summary valid → webhooks accessible

---

> **Speaker Notes:**
> If doing a live demo, walk through these steps in order using the sidebar buttons:
> (1) Click "Seed Normal Traffic" → 5 services get baseline logs.
> (2) Select auth-service in the sidebar, click "Inject Error Spike" → 40 CRITICAL/ERROR logs injected.
> (3) Click "Run Watchdog Now" → triggers a background watchdog cycle immediately.
> (4) Wait 5 seconds, refresh → Health Score drops, new alerts appear in the feed.
> If no live demo, walk through the architecture diagram and explain the data flow.
> The smoke test script is the proof of end-to-end correctness — it runs unattended in CI.

---

## Slide 7 — Vibe Coding Process

# The Two-Claude Workflow

**Architectural control + AI autonomy, not a choice between them:**

- **Lead Architect Rules** — The human acted as Product Owner and Architect: defining specs, approving plans, issuing prompts, and merging PRs — but writing zero lines of code; Claude Code handled every implementation detail
- **prompts.md Audit Log** — Every prompt issued was appended to `prompts.md` in the same commit it produced; the project is fully reproducible — 21 recorded turns, 10 PRs, 37 tasks
- **Plan Mode** — Architectural decisions (spec design, tech stack pivot, task ordering) were made in Plan Mode before a single file was created; no code was written before the spec was locked
- **Spec-First Development** — `specifications.md` was written and locked before `requirements.txt` existed; all 37 tasks derived from it; no scope changes after lock
- **GitHub Flow** — Each task group lived on its own `feature/*` branch; every merge was via a pull request with acceptance criteria; CI ran lint + unit + integration tests on every PR

> **Workflow summary:**
> Human: strategic prompts + PR approvals → Claude: spec, plan, code, tests, CI fixes → Human: merge

---

> **Speaker Notes:**
> The "Two-Claude" framing highlights the disciplined split of responsibilities. The human's job was
> to be a good product manager: write precise prompts, approve plans before implementation, and review
> PRs. Claude's job was to be a senior engineer: interpret requirements, architect solutions, write
> production-quality code, and fix its own bugs. The prompts.md audit log is proof of work — any
> reviewer can replay the session prompt by prompt and understand every decision. Plan Mode was
> critical: it forced explicit alignment on architecture BEFORE any code was written, eliminating
> the most common AI coding pitfall (writing the wrong thing perfectly).

---

## Slide 8 — Key Learnings

# What This Process Teaches

**Precision beats volume: better prompts produce better systems.**

- **Spec before code eliminates rework** — The locked `specifications.md` (12 sections, 680+ lines) made every subsequent implementation prompt unambiguous; the AI never had to guess intent, and scope never drifted
- **Prompt precision is a design skill** — Vague prompts produce vague code; "implement anomaly detection" produces a stub; "implement a three-tier detector with Z-score threshold 2.5, IsolationForest contamination 0.05, and CRITICAL on dual error_count+error_rate breach" produces production code
- **AI autonomy requires guardrails** — The "No Manual Edits" rule forced the human to give the AI enough context to self-correct; every bug (hashFiles at job level, ruff F401, FastAPI 204 body assertion, bash -e curl exit) was fixed by issuing a targeted fix prompt, not by touching a keyboard
- **Feature branch workflow survives AI sessions** — Structuring work as 10 PRs across 37 tasks meant context limits reset cleanly; each branch was self-contained and mergeable independently
- **Test infrastructure is not optional** — The SQLite conftest.py override pattern (patch engine before import) was the most architecturally demanding piece of the test suite; without it, CI would require a live database and would be unusable on open PRs

---

> **Speaker Notes:**
> These are the transferable lessons from this specific project, not generic AI advice.
> The hashFiles bug (used in job-level `if` before checkout) is a concrete example of where AI
> confidence ≠ correctness — the assistant correctly flagged the linter warning as a possible false
> positive, but when GitHub Actions disagreed, the fix required understanding WHY job-level conditions
> run before workspace checkout. Spec-first development is the single highest-leverage habit:
> it forces the human to think clearly about what they want before delegating. Without it, you get
> a fast but incoherent codebase.

---

## Slide 9 — V2 Roadmap

# What Comes After the MVP

**From dev laptop to production SRE platform:**

- **AWS SNS Webhook Fan-Out** — Replace simulated HTTP POSTs with SNS topic publication; Slack, PagerDuty, and email subscribers receive alerts natively with built-in retry, dead-letter queues, and subscription management — eliminating the custom `WebhookDelivery` retry logic
- **CloudWatch Log Source** — Add a `boto3`-powered log poller service that reads from AWS CloudWatch Logs groups and maps events to the `LogEntry` schema; replaces Faker simulation with real production traffic
- **EC2/ECS Deployment** — Dockerize FastAPI + Streamlit; deploy to ECS Fargate (free tier eligible); swap Supabase for RDS PostgreSQL; add an Application Load Balancer for HTTPS termination — moves the platform from a localhost demo to an always-on cloud service
- **Alert Deduplication** — Suppress duplicate alerts for the same `(service, alert_type)` pair within a configurable cooldown window (default: 15 min) to eliminate alert fatigue during sustained incidents
- **Grafana Integration** — Expose `/metrics` in Prometheus format via `prometheus-fastapi-instrumentator`; connect to Grafana Cloud free tier for industry-standard dashboarding alongside or replacing the Streamlit panel

> **V2 design principle:** Same API surface, same detection tiers, same database schema — only the infrastructure layer changes. The MVP was built to be extensible without being over-engineered.

---

> **Speaker Notes:**
> The V2 roadmap was written into the spec before a single line of MVP code was written — this is
> the Open/Closed Principle applied at the product level. SNS replaces the webhook dispatcher module
> without touching the anomaly detection or watchdog. CloudWatch replaces the simulate router
> without touching ingestion logic. The architecture was designed for this substitution.
> If asked about priorities: SNS + ECS is the highest-leverage combination — it turns a demo into
> a service that could actually page an on-call engineer during a real incident.

---

## Appendix — Project Metrics

| Metric | Value |
|---|---|
| Total tasks | 37 |
| Feature branches | 10 |
| Pull requests | 10 |
| Recorded prompt turns | 21 |
| Source files written | 22 |
| Test files | 5 |
| Tests passing | 26 / 26 |
| Lines of application code | ~1,200 |
| Lines of test code | ~320 |
| Lines of specification | ~680 |
| Manual code edits | **0** |
| Time to MVP | **< 7 hours** |

---

*Built with Claude Code (claude-sonnet-4-6) — Graduate Vibe Coding Challenge 2026*
