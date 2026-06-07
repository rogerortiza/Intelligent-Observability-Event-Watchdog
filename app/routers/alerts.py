"""Alerts router — /api/v1/alerts (list, detail, acknowledge, resolve)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, AlertSeverity, AlertStatus, AlertType
from app.schemas import AlertAcknowledge, AlertOut, PaginatedResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("", response_model=PaginatedResponse[AlertOut])
def list_alerts(
    status: Optional[AlertStatus] = Query(None),
    severity: Optional[AlertSeverity] = Query(None),
    alert_type: Optional[AlertType] = Query(None),
    service: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AlertOut]:
    """Return paginated alerts ordered by triggered_at descending."""
    stmt = select(Alert)
    if status is not None:
        stmt = stmt.where(Alert.status == status)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if alert_type is not None:
        stmt = stmt.where(Alert.alert_type == alert_type)
    if service is not None:
        stmt = stmt.where(Alert.service == service)

    total: int = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(Alert.triggered_at.desc()).limit(limit).offset(offset)
        ).all()
    )
    return PaginatedResponse[AlertOut](items=rows, total=total, limit=limit, offset=offset)


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> Alert:
    """Return a single alert by ID or 404."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.put("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int,
    body: AlertAcknowledge,
    db: Session = Depends(get_db),
) -> Alert:
    """Acknowledge an OPEN alert; returns 400 if already non-OPEN."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if alert.status != AlertStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alert is already {alert.status.value}; only OPEN alerts can be acknowledged",
        )
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = _utcnow()
    db.commit()
    db.refresh(alert)
    return alert


@router.put("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)) -> Alert:
    """Resolve an alert; returns 400 if already resolved."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is already RESOLVED",
        )
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = _utcnow()
    db.commit()
    db.refresh(alert)
    return alert
