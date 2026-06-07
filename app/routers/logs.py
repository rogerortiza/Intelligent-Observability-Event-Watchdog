"""Log ingestion and query router — /api/v1/logs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LogEntry, LogLevel
from app.schemas import (
    BatchIngestResponse,
    LogEntryBatch,
    LogEntryCreate,
    LogEntryOut,
    PaginatedResponse,
)

router = APIRouter(prefix="/logs", tags=["logs"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post(
    "/ingest",
    response_model=LogEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def ingest_log(
    payload: LogEntryCreate,
    db: Session = Depends(get_db),
) -> LogEntry:
    """Ingest a single log entry and return the persisted row."""
    entry = LogEntry(
        timestamp=payload.timestamp or _utcnow(),
        level=payload.level,
        service=payload.service,
        message=payload.message,
        latency_ms=payload.latency_ms,
        host=payload.host,
        trace_id=payload.trace_id,
        extra=payload.extra,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post(
    "/ingest/batch",
    response_model=BatchIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_batch(
    payload: LogEntryBatch,
    db: Session = Depends(get_db),
) -> BatchIngestResponse:
    """Ingest 1–1000 log entries in a single request."""
    entries = [
        LogEntry(
            timestamp=log.timestamp or _utcnow(),
            level=log.level,
            service=log.service,
            message=log.message,
            latency_ms=log.latency_ms,
            host=log.host,
            trace_id=log.trace_id,
            extra=log.extra,
        )
        for log in payload.logs
    ]
    db.add_all(entries)
    db.commit()
    return BatchIngestResponse(
        message=f"Ingested {len(entries)} log entries",
        count=len(entries),
    )


@router.get("", response_model=PaginatedResponse[LogEntryOut])
def get_logs(
    service: Optional[str] = Query(None),
    level: Optional[LogLevel] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LogEntryOut]:
    """Return paginated log entries ordered by timestamp descending."""
    stmt = select(LogEntry)
    if service is not None:
        stmt = stmt.where(LogEntry.service == service)
    if level is not None:
        stmt = stmt.where(LogEntry.level == level)
    if start_time is not None:
        stmt = stmt.where(LogEntry.timestamp >= start_time)
    if end_time is not None:
        stmt = stmt.where(LogEntry.timestamp <= end_time)

    total: int = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(LogEntry.timestamp.desc()).limit(limit).offset(offset)
        ).all()
    )
    return PaginatedResponse[LogEntryOut](
        items=rows,
        total=total,
        limit=limit,
        offset=offset,
    )
