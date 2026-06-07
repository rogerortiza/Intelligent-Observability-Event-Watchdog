"""SQLAlchemy ORM models for all five database tables."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (tzinfo stripped)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Enums ─────────────────────────────────────────────────────────────────────


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertType(str, enum.Enum):
    ERROR_RATE_SPIKE = "ERROR_RATE_SPIKE"
    LOG_VOLUME_SPIKE = "LOG_VOLUME_SPIKE"
    LATENCY_SPIKE = "LATENCY_SPIKE"
    THRESHOLD_BREACH = "THRESHOLD_BREACH"
    ISOLATION_FOREST = "ISOLATION_FOREST"


class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class WebhookStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


# ── Models ────────────────────────────────────────────────────────────────────


class LogEntry(Base):
    """Single ingested log event from any service.

    Table: log_entries
    """

    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, default=_utcnow
    )
    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, native_enum=False), nullable=False, index=True
    )
    service: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    host: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )


class MetricSnapshot(Base):
    """Aggregated statistics for one service over one time window.

    Table: metric_snapshots
    """

    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    window_start: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    service: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    total_logs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    alerts: Mapped[list[Alert]] = relationship(
        "Alert", back_populates="snapshot", cascade="all, delete-orphan"
    )


class Alert(Base):
    """Triggered anomaly event produced by the watchdog.

    Table: alerts
    """

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_service_status", "service", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, native_enum=False), nullable=False, index=True
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, native_enum=False), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, native_enum=False),
        nullable=False,
        default=AlertStatus.OPEN,
        index=True,
    )
    service: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapshot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("metric_snapshots.id"), nullable=True
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, index=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    snapshot: Mapped[MetricSnapshot | None] = relationship(
        "MetricSnapshot", back_populates="alerts"
    )
    deliveries: Mapped[list[WebhookDelivery]] = relationship(
        "WebhookDelivery", back_populates="alert", cascade="all, delete-orphan"
    )


class WebhookConfig(Base):
    """Registered external URL to receive alert payloads via HTTP POST.

    Table: webhook_configs
    """

    __tablename__ = "webhook_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    secret: Mapped[str | None] = mapped_column(String(256), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, native_enum=False),
        nullable=False,
        default=AlertSeverity.MEDIUM,
    )
    alert_types: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    deliveries: Mapped[list[WebhookDelivery]] = relationship(
        "WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan"
    )


class WebhookDelivery(Base):
    """Audit record of every webhook POST attempt.

    Table: webhook_deliveries
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    webhook_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webhook_configs.id"), nullable=False
    )
    alert_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerts.id"), nullable=False
    )
    status: Mapped[WebhookStatus] = mapped_column(
        Enum(WebhookStatus, native_enum=False),
        nullable=False,
        default=WebhookStatus.PENDING,
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    webhook: Mapped[WebhookConfig] = relationship(
        "WebhookConfig", back_populates="deliveries"
    )
    alert: Mapped[Alert] = relationship(
        "Alert", back_populates="deliveries"
    )
