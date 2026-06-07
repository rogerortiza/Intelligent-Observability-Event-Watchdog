"""Pydantic request/response schemas for all API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.models import AlertSeverity, AlertStatus, AlertType, LogLevel, WebhookStatus

T = TypeVar("T")


# ── Generic wrapper ──────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list envelope returned by all list endpoints."""

    items: list[T]
    total: int
    limit: int
    offset: int


# ── Log schemas ───────────────────────────────────────────────────────────────


class LogEntryCreate(BaseModel):
    """Request body for POST /logs/ingest (single and batch)."""

    timestamp: Optional[datetime] = None
    level: LogLevel
    service: str = Field(..., max_length=100)
    message: str
    latency_ms: Optional[float] = None
    host: Optional[str] = Field(None, max_length=100)
    trace_id: Optional[str] = Field(None, max_length=64)
    extra: Optional[dict[str, Any]] = None


class LogEntryOut(BaseModel):
    """Response schema for a persisted log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    level: LogLevel
    service: str
    message: str
    latency_ms: Optional[float]
    host: Optional[str]
    trace_id: Optional[str]
    extra: Optional[dict[str, Any]]
    ingested_at: datetime


class LogEntryBatch(BaseModel):
    """Request body for POST /logs/ingest/batch."""

    logs: list[LogEntryCreate] = Field(..., min_length=1, max_length=1000)


class BatchIngestResponse(BaseModel):
    """Response body for POST /logs/ingest/batch."""

    message: str
    count: int


# ── Metric schemas ────────────────────────────────────────────────────────────


class MetricSnapshotOut(BaseModel):
    """Response schema for a MetricSnapshot row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    window_start: datetime
    window_end: datetime
    service: str
    total_logs: int
    error_count: int
    warning_count: int
    error_rate: float
    avg_latency_ms: Optional[float]
    p95_latency_ms: Optional[float]
    max_latency_ms: Optional[float]
    error_zscore: Optional[float]
    volume_zscore: Optional[float]
    latency_zscore: Optional[float]
    created_at: datetime


class MetricsSummary(BaseModel):
    """Response for GET /metrics/summary — 24-hour aggregate KPIs."""

    total_logs_24h: int
    error_rate_24h: float
    error_count_24h: int
    active_alerts: int
    services_monitored: int
    avg_latency_ms: Optional[float]
    health_score: float
    last_updated: datetime


class TimeSeriesPoint(BaseModel):
    """Single data point in a time-series response."""

    timestamp: datetime
    value: float
    service: str


class TimeSeriesResponse(BaseModel):
    """Response for GET /metrics/timeseries."""

    metric: str
    service: Optional[str]
    points: list[TimeSeriesPoint]


# ── Alert schemas ─────────────────────────────────────────────────────────────


class AlertOut(BaseModel):
    """Response schema for a persisted Alert row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    service: str
    title: str
    description: str
    metric_value: Optional[float]
    threshold_value: Optional[float]
    zscore: Optional[float]
    snapshot_id: Optional[int]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]


class AlertAcknowledge(BaseModel):
    """Request body for PUT /alerts/{id}/acknowledge."""

    note: Optional[str] = None


# ── Webhook schemas ───────────────────────────────────────────────────────────


class WebhookCreate(BaseModel):
    """Request body for POST /webhooks."""

    name: str = Field(..., max_length=100)
    url: str = Field(..., max_length=512)
    secret: Optional[str] = Field(None, max_length=256)
    min_severity: AlertSeverity = AlertSeverity.MEDIUM
    alert_types: Optional[list[AlertType]] = None


class WebhookOut(BaseModel):
    """Response schema for a persisted WebhookConfig row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    secret: Optional[str]
    active: bool
    min_severity: AlertSeverity
    alert_types: Optional[list[str]]
    created_at: datetime


class WebhookDeliveryOut(BaseModel):
    """Response schema for a persisted WebhookDelivery row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    webhook_id: int
    alert_id: int
    status: WebhookStatus
    status_code: Optional[int]
    response_body: Optional[str]
    error_message: Optional[str]
    payload: Optional[dict[str, Any]]
    delivered_at: datetime


# ── Simulate schemas ──────────────────────────────────────────────────────────


class SimulateNormalRequest(BaseModel):
    """Request body for POST /simulate/normal-traffic."""

    service: str = Field(..., max_length=100)
    count: int = Field(50, ge=1, le=1000)
    error_rate: float = Field(0.05, ge=0.0, le=1.0)


class SimulateSpikeRequest(BaseModel):
    """Request body for POST /simulate/error-spike."""

    service: str = Field(..., max_length=100)
    error_count: int = Field(20, ge=1)
    spike_duration_minutes: int = Field(5, ge=1)


class SimulateResponse(BaseModel):
    """Generic response for simulate endpoints."""

    message: str
    logs_created: int
    service: str


# ── Health schema ─────────────────────────────────────────────────────────────


class HealthCheck(BaseModel):
    """Response for GET /api/v1/health."""

    status: str
    version: str
    database: str
    watchdog: str
    uptime_seconds: float
