"""Watchdog scheduler — aggregates logs, detects anomalies, dispatches webhooks."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import LogEntry, LogLevel, MetricSnapshot
from app.services.anomaly_detector import create_alert_from_result, detect_anomalies
from app.services.webhook_dispatcher import dispatch_alert

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None  # type: ignore[type-arg]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Aggregation ───────────────────────────────────────────────────────────────


def _aggregate_window(
    db: Session,
    service: str,
    window_start: datetime,
    window_end: datetime,
) -> MetricSnapshot:
    """Build a MetricSnapshot from LogEntry rows in [window_start, window_end)."""
    rows = db.scalars(
        select(LogEntry)
        .where(LogEntry.service == service)
        .where(LogEntry.timestamp >= window_start)
        .where(LogEntry.timestamp < window_end)
    ).all()

    total_logs = len(rows)
    error_count = sum(
        1 for r in rows if r.level in (LogLevel.ERROR, LogLevel.CRITICAL)
    )
    warning_count = sum(1 for r in rows if r.level == LogLevel.WARNING)
    error_rate = error_count / total_logs if total_logs > 0 else 0.0

    latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
    avg_latency = float(np.mean(latencies)) if latencies else None
    p95_latency = float(np.percentile(latencies, 95)) if latencies else None
    max_latency = float(np.max(latencies)) if latencies else None

    return MetricSnapshot(
        service=service,
        window_start=window_start,
        window_end=window_end,
        total_logs=total_logs,
        error_count=error_count,
        warning_count=warning_count,
        error_rate=error_rate,
        avg_latency_ms=avg_latency,
        p95_latency_ms=p95_latency,
        max_latency_ms=max_latency,
    )


# ── Cycle ─────────────────────────────────────────────────────────────────────


async def run_watchdog_cycle() -> None:
    """Aggregate the current window, detect anomalies, and dispatch webhooks.

    Idempotent: skips any (service, window_start) pair that already has a
    MetricSnapshot.  Safe to call manually from the simulate endpoint.
    """
    window_end = _utcnow()
    window_start = window_end - timedelta(minutes=settings.metric_window_minutes)

    db = SessionLocal()
    try:
        services = list(
            db.scalars(
                select(distinct(LogEntry.service))
                .where(LogEntry.timestamp >= window_start)
                .where(LogEntry.timestamp < window_end)
            ).all()
        )

        new_alerts = []

        for service in services:
            existing = db.scalar(
                select(MetricSnapshot)
                .where(MetricSnapshot.service == service)
                .where(MetricSnapshot.window_start == window_start)
            )
            if existing is not None:
                continue

            snapshot = _aggregate_window(db, service, window_start, window_end)
            db.add(snapshot)
            db.flush()  # assigns snapshot.id before detection queries it

            for result in detect_anomalies(db, snapshot):
                new_alerts.append(create_alert_from_result(db, result, snapshot))

        db.flush()   # assigns IDs to all new Alert rows
        db.commit()  # commit snapshots + alerts

        for alert in new_alerts:
            await dispatch_alert(db, alert)

        db.commit()  # commit WebhookDelivery records

    except Exception as exc:
        logger.exception("Watchdog cycle failed: %s", exc)
        db.rollback()
    finally:
        db.close()


# ── Scheduler ─────────────────────────────────────────────────────────────────


async def _loop() -> None:
    """Sleep WATCHDOG_INTERVAL_SECONDS, then run one cycle, indefinitely."""
    while True:
        await asyncio.sleep(settings.watchdog_interval_seconds)
        await run_watchdog_cycle()


async def start_watchdog() -> None:
    """Schedule the background watchdog loop as an asyncio Task."""
    global _task
    _task = asyncio.create_task(_loop())


async def stop_watchdog() -> None:
    """Cancel the background watchdog loop and await its cleanup."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None


def is_running() -> bool:
    """Return True if the watchdog Task is active."""
    return _task is not None and not _task.done()
