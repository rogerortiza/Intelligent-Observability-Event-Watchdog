"""Webhook dispatcher — builds, signs, and POSTs alert payloads via httpx."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, AlertSeverity, WebhookConfig, WebhookDelivery, WebhookStatus

_SEVERITY_ORDER: dict[AlertSeverity, int] = {
    AlertSeverity.LOW: 0,
    AlertSeverity.MEDIUM: 1,
    AlertSeverity.HIGH: 2,
    AlertSeverity.CRITICAL: 3,
}

_WEBHOOK_TIMEOUT = 10.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_payload(alert: Alert) -> dict:
    """Serialize an alert to the JSON dict sent in every webhook POST."""
    return {
        "event": "alert.triggered",
        "alert_id": alert.id,
        "alert_type": alert.alert_type.value,
        "severity": alert.severity.value,
        "status": alert.status.value,
        "service": alert.service,
        "title": alert.title,
        "description": alert.description,
        "metric_value": alert.metric_value,
        "threshold_value": alert.threshold_value,
        "zscore": alert.zscore,
        "triggered_at": alert.triggered_at.isoformat(),
        "snapshot_id": alert.snapshot_id,
    }


def _sign_payload(secret: str, body: str) -> str:
    """Return the HMAC-SHA256 signature header value: 'sha256=<hex>'."""
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _matches_webhook(alert: Alert, webhook: WebhookConfig) -> bool:
    """Return True if this alert meets the webhook's severity and type filters."""
    if _SEVERITY_ORDER[alert.severity] < _SEVERITY_ORDER[webhook.min_severity]:
        return False
    if webhook.alert_types is not None:
        if alert.alert_type.value not in webhook.alert_types:
            return False
    return True


async def dispatch_alert(db: Session, alert: Alert) -> list[WebhookDelivery]:
    """POST the alert to every matching active webhook; persist a WebhookDelivery per attempt."""
    webhooks = db.scalars(
        select(WebhookConfig).where(WebhookConfig.active.is_(True))
    ).all()

    deliveries: list[WebhookDelivery] = []

    async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
        for webhook in webhooks:
            if not _matches_webhook(alert, webhook):
                continue

            payload = _build_payload(alert)
            body = json.dumps(payload, default=str)

            headers = {"Content-Type": "application/json"}
            if webhook.secret:
                headers["X-Watchdog-Signature"] = _sign_payload(webhook.secret, body)

            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                alert_id=alert.id,
                status=WebhookStatus.PENDING,
                payload=payload,
                delivered_at=_utcnow(),
            )

            try:
                response = await client.post(webhook.url, content=body, headers=headers)
                delivery.status_code = response.status_code
                delivery.response_body = response.text[:2000]
                delivery.status = (
                    WebhookStatus.SUCCESS
                    if response.is_success
                    else WebhookStatus.FAILED
                )
            except Exception as exc:
                delivery.status = WebhookStatus.FAILED
                delivery.error_message = str(exc)

            db.add(delivery)
            deliveries.append(delivery)

    return deliveries
