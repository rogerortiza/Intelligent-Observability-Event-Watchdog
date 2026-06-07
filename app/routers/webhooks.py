"""Webhooks router — /api/v1/webhooks (CRUD, toggle, delivery history)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WebhookConfig, WebhookDelivery
from app.schemas import (
    PaginatedResponse,
    WebhookCreate,
    WebhookDeliveryOut,
    WebhookOut,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook(payload: WebhookCreate, db: Session = Depends(get_db)) -> WebhookConfig:
    """Register a new webhook destination."""
    webhook = WebhookConfig(
        name=payload.name,
        url=payload.url,
        secret=payload.secret,
        min_severity=payload.min_severity,
        alert_types=[t.value for t in payload.alert_types] if payload.alert_types else None,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


@router.get("", response_model=list[WebhookOut])
def list_webhooks(db: Session = Depends(get_db)) -> list[WebhookConfig]:
    """Return all registered webhooks."""
    return list(db.scalars(select(WebhookConfig).order_by(WebhookConfig.id)).all())


@router.get("/{webhook_id}", response_model=WebhookOut)
def get_webhook(webhook_id: int, db: Session = Depends(get_db)) -> WebhookConfig:
    """Return a single webhook by ID or 404."""
    webhook = db.get(WebhookConfig, webhook_id)
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_webhook(webhook_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a webhook and all its delivery records."""
    webhook = db.get(WebhookConfig, webhook_id)
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    db.delete(webhook)
    db.commit()


@router.put("/{webhook_id}/toggle", response_model=WebhookOut)
def toggle_webhook(webhook_id: int, db: Session = Depends(get_db)) -> WebhookConfig:
    """Flip the active flag on a webhook."""
    webhook = db.get(WebhookConfig, webhook_id)
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    webhook.active = not webhook.active
    db.commit()
    db.refresh(webhook)
    return webhook


@router.get("/{webhook_id}/deliveries", response_model=PaginatedResponse[WebhookDeliveryOut])
def list_deliveries(
    webhook_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[WebhookDeliveryOut]:
    """Return paginated delivery history for a webhook."""
    if db.get(WebhookConfig, webhook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    stmt = select(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id)
    total: int = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(WebhookDelivery.delivered_at.desc()).limit(limit).offset(offset)
        ).all()
    )
    return PaginatedResponse[WebhookDeliveryOut](
        items=rows, total=total, limit=limit, offset=offset
    )
