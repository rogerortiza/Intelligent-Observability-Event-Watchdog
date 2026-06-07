"""Log simulator router — /api/v1/simulate (Faker-powered traffic generation)."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LogEntry, LogLevel
from app.schemas import SimulateNormalRequest, SimulateSpikeRequest, SimulateResponse
from app.services.watchdog import run_watchdog_cycle

router = APIRouter(prefix="/simulate", tags=["simulate"])

_faker = Faker()

_BUILT_IN_SERVICES: list[str] = [
    "auth-service",
    "api-gateway",
    "payment-service",
    "user-service",
    "notification-service",
]

_MESSAGES: dict[LogLevel, list[str]] = {
    LogLevel.CRITICAL: [
        "Service health check FAILED — restarting",
        "Database primary node unreachable",
        "Out of memory: killing process",
        "SSL certificate expired",
        "Disk usage at 99%: writes failing",
    ],
    LogLevel.ERROR: [
        "Connection timeout after 30000ms",
        "Database connection refused: max pool size reached",
        "Authentication failed: invalid JWT signature",
        "Failed to process request: upstream service unavailable",
        "Unhandled exception in request handler",
        "Rate limit exceeded: 429 Too Many Requests",
        "Failed to acquire lock after 5 retries",
    ],
    LogLevel.WARNING: [
        "Response time exceeded 1000ms SLA",
        "Memory usage at 85%",
        "Cache miss rate above 60%",
        "Retry attempt 2/3 for external API",
        "Connection pool at 80% capacity",
    ],
    LogLevel.INFO: [
        "Request processed successfully",
        "User authenticated",
        "Cache refreshed",
        "Scheduled job completed",
        "Configuration reloaded",
        "HTTP GET /api/health 200 OK",
    ],
    LogLevel.DEBUG: [
        "Query executed in 12ms",
        "Cache hit for key user_session",
        "Background task enqueued",
        "Redis connection established",
        "Payload deserialized successfully",
    ],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _pick_level(error_rate: float) -> LogLevel:
    """Choose a log level proportional to error_rate."""
    r = random.random()
    if r < error_rate * 0.8:   # 80% of error budget → ERROR
        return LogLevel.ERROR
    if r < error_rate:          # remaining 20% → CRITICAL
        return LogLevel.CRITICAL
    r2 = random.random()
    if r2 < 0.15:
        return LogLevel.WARNING
    if r2 < 0.40:
        return LogLevel.DEBUG
    return LogLevel.INFO


def _make_entry(service: str, level: LogLevel, ts: datetime) -> LogEntry:
    """Build a single realistic LogEntry without adding it to any session."""
    if level in (LogLevel.ERROR, LogLevel.CRITICAL):
        latency = round(random.uniform(1200.0, 4000.0), 1)
    elif level == LogLevel.WARNING:
        latency = round(random.uniform(800.0, 1500.0), 1)
    else:
        latency = round(random.uniform(20.0, 400.0), 1)

    return LogEntry(
        timestamp=ts,
        level=level,
        service=service,
        message=random.choice(_MESSAGES[level]),
        latency_ms=latency,
        host=f"pod-{random.randint(1, 5)}.{service}",
        trace_id=_faker.uuid4()[:16],
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/normal-traffic",
    response_model=SimulateResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_normal_traffic(
    payload: SimulateNormalRequest,
    db: Session = Depends(get_db),
) -> SimulateResponse:
    """Generate realistic mixed-level log traffic for one service."""
    now = _utcnow()
    entries = [
        _make_entry(payload.service, _pick_level(payload.error_rate), now)
        for _ in range(payload.count)
    ]
    db.add_all(entries)
    db.commit()
    return SimulateResponse(
        message=f"Generated {len(entries)} log entries for {payload.service}",
        logs_created=len(entries),
        service=payload.service,
    )


@router.post(
    "/error-spike",
    response_model=SimulateResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_error_spike(
    payload: SimulateSpikeRequest,
    db: Session = Depends(get_db),
) -> SimulateResponse:
    """Inject a burst of ERROR/CRITICAL logs spread over spike_duration_minutes."""
    now = _utcnow()
    duration = timedelta(minutes=payload.spike_duration_minutes)
    entries = []
    for i in range(payload.error_count):
        frac = i / max(payload.error_count - 1, 1)
        ts = now - duration + duration * frac
        level = LogLevel.CRITICAL if random.random() < 0.2 else LogLevel.ERROR
        entries.append(_make_entry(payload.service, level, ts))
    db.add_all(entries)
    db.commit()
    return SimulateResponse(
        message=f"Injected {len(entries)} error logs into {payload.service}",
        logs_created=len(entries),
        service=payload.service,
    )


@router.post("/run-watchdog", status_code=status.HTTP_200_OK)
async def trigger_watchdog(background_tasks: BackgroundTasks) -> dict:
    """Trigger one watchdog cycle immediately in the background."""
    background_tasks.add_task(run_watchdog_cycle)
    return {"message": "Watchdog cycle triggered in background"}


@router.post("/seed-all-services", status_code=status.HTTP_201_CREATED)
def seed_all_services(db: Session = Depends(get_db)) -> dict:
    """Seed all five built-in services with 100 mixed-level log entries each."""
    now = _utcnow()
    total = 0
    for service in _BUILT_IN_SERVICES:
        entries = [
            _make_entry(service, _pick_level(0.05), now)
            for _ in range(100)
        ]
        db.add_all(entries)
        total += len(entries)
    db.commit()
    return {
        "message": f"Seeded {total} log entries across {len(_BUILT_IN_SERVICES)} services",
        "services": _BUILT_IN_SERVICES,
    }
