"""Metrics router — /api/v1/metrics (summary, timeseries, snapshots)."""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, AlertStatus, MetricSnapshot
from app.schemas import (
    MetricSnapshotOut,
    MetricsSummary,
    PaginatedResponse,
    TimeSeriesPoint,
    TimeSeriesResponse,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


class MetricField(str, enum.Enum):
    """Valid metric names for the timeseries endpoint."""

    error_count = "error_count"
    total_logs = "total_logs"
    avg_latency_ms = "avg_latency_ms"
    error_rate = "error_rate"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/summary", response_model=MetricsSummary)
def get_summary(db: Session = Depends(get_db)) -> MetricsSummary:
    """Return 24-hour aggregate KPIs across all services."""
    cutoff = _utcnow() - timedelta(hours=24)

    agg = db.execute(
        select(
            func.coalesce(func.sum(MetricSnapshot.total_logs), 0),
            func.coalesce(func.sum(MetricSnapshot.error_count), 0),
            func.avg(MetricSnapshot.avg_latency_ms),
            func.count(distinct(MetricSnapshot.service)),
        ).where(MetricSnapshot.window_start >= cutoff)
    ).one()

    total_logs: int = int(agg[0])
    error_count: int = int(agg[1])
    avg_latency: Optional[float] = float(agg[2]) if agg[2] is not None else None
    services_count: int = int(agg[3])

    error_rate = error_count / total_logs if total_logs > 0 else 0.0

    active_alerts: int = (
        db.scalar(
            select(func.count(Alert.id)).where(Alert.status == AlertStatus.OPEN)
        )
        or 0
    )

    health_score = max(
        0.0,
        min(100.0, 100.0 - error_rate * 50.0 - active_alerts * 5.0),
    )

    return MetricsSummary(
        total_logs_24h=total_logs,
        error_rate_24h=round(error_rate, 4),
        error_count_24h=error_count,
        active_alerts=active_alerts,
        services_monitored=services_count,
        avg_latency_ms=avg_latency,
        health_score=round(health_score, 1),
        last_updated=_utcnow(),
    )


@router.get("/timeseries", response_model=TimeSeriesResponse)
def get_timeseries(
    metric: MetricField = Query(...),
    service: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> TimeSeriesResponse:
    """Return time-series data from MetricSnapshot for charting."""
    cutoff = _utcnow() - timedelta(hours=hours)

    stmt = select(MetricSnapshot).where(MetricSnapshot.window_start >= cutoff)
    if service is not None:
        stmt = stmt.where(MetricSnapshot.service == service)
    stmt = stmt.order_by(MetricSnapshot.window_start.asc())

    rows = db.scalars(stmt).all()
    points = [
        TimeSeriesPoint(
            timestamp=row.window_start,
            value=float(getattr(row, metric.value) or 0.0),
            service=row.service,
        )
        for row in rows
    ]

    return TimeSeriesResponse(
        metric=metric.value,
        service=service,
        points=points,
    )


@router.get("/snapshots", response_model=PaginatedResponse[MetricSnapshotOut])
def get_snapshots(
    service: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[MetricSnapshotOut]:
    """Return paginated MetricSnapshot history."""
    cutoff = _utcnow() - timedelta(hours=hours)

    stmt = select(MetricSnapshot).where(MetricSnapshot.window_start >= cutoff)
    if service is not None:
        stmt = stmt.where(MetricSnapshot.service == service)

    total: int = (
        db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    rows = list(
        db.scalars(
            stmt.order_by(MetricSnapshot.window_start.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )

    return PaginatedResponse[MetricSnapshotOut](
        items=rows,
        total=total,
        limit=limit,
        offset=offset,
    )
