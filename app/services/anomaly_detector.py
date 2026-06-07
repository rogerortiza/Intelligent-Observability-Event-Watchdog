"""Three-tier anomaly detection engine (hard threshold → Z-score → IsolationForest)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Alert, AlertSeverity, AlertStatus, AlertType, MetricSnapshot


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class AnomalyResult:
    """Lightweight result emitted by each detection tier; converted to an Alert row."""

    alert_type: AlertType
    severity: AlertSeverity
    service: str
    title: str
    description: str
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    zscore: Optional[float] = None


# ── Statistical helpers ───────────────────────────────────────────────────────


def _zscore(current: float, baseline: list[float]) -> Optional[float]:
    """Return the Z-score of `current` against `baseline`, or None if incalculable.

    Returns None when fewer than 5 samples exist or the baseline is flat
    (std < 1e-9) to avoid false positives on perfectly stable services.
    """
    if len(baseline) < 5:
        return None
    arr = np.array(baseline, dtype=float)
    std = float(np.std(arr))
    if std < 1e-9:
        return None
    return float((current - float(np.mean(arr))) / std)


def _severity_from_zscore(z: float) -> AlertSeverity:
    """Map |z| to AlertSeverity per spec §7 Tier 2 table."""
    abs_z = abs(z)
    if abs_z >= 5.0:
        return AlertSeverity.CRITICAL
    if abs_z >= 4.0:
        return AlertSeverity.HIGH
    if abs_z >= 3.0:
        return AlertSeverity.MEDIUM
    return AlertSeverity.LOW


def _severity_from_if_score(score: float) -> AlertSeverity:
    """Map IsolationForest decision score to AlertSeverity per spec §7 Tier 3."""
    if score < -0.3:
        return AlertSeverity.CRITICAL
    if score < -0.2:
        return AlertSeverity.HIGH
    return AlertSeverity.MEDIUM


def _get_baseline(db: Session, service: str, snapshot_id: int) -> list[MetricSnapshot]:
    """Return up to BASELINE_LOOKBACK_WINDOWS prior snapshots, excluding current."""
    return list(
        db.scalars(
            select(MetricSnapshot)
            .where(MetricSnapshot.service == service)
            .where(MetricSnapshot.id != snapshot_id)
            .order_by(MetricSnapshot.window_start.desc())
            .limit(settings.baseline_lookback_windows)
        ).all()
    )


# ── Tier 1: Hard Threshold ────────────────────────────────────────────────────


def _tier1(snapshot: MetricSnapshot) -> list[AnomalyResult]:
    """Check hard thresholds; dual error_count+error_rate breach → CRITICAL."""
    results: list[AnomalyResult] = []
    error_count_fired = False
    error_rate_fired = False

    if snapshot.error_count >= settings.error_count_threshold:
        error_count_fired = True
        results.append(
            AnomalyResult(
                alert_type=AlertType.THRESHOLD_BREACH,
                severity=AlertSeverity.HIGH,
                service=snapshot.service,
                title=f"Error count threshold breach: {snapshot.service}",
                description=(
                    f"Error count {snapshot.error_count} ≥ threshold "
                    f"{settings.error_count_threshold} in window "
                    f"{snapshot.window_start} – {snapshot.window_end}."
                ),
                metric_value=float(snapshot.error_count),
                threshold_value=float(settings.error_count_threshold),
            )
        )

    if snapshot.error_rate >= settings.error_rate_threshold:
        error_rate_fired = True
        results.append(
            AnomalyResult(
                alert_type=AlertType.ERROR_RATE_SPIKE,
                severity=AlertSeverity.HIGH,
                service=snapshot.service,
                title=f"Error rate spike: {snapshot.service}",
                description=(
                    f"Error rate {snapshot.error_rate:.1%} ≥ threshold "
                    f"{settings.error_rate_threshold:.1%} in window "
                    f"{snapshot.window_start} – {snapshot.window_end}."
                ),
                metric_value=snapshot.error_rate,
                threshold_value=settings.error_rate_threshold,
            )
        )

    if error_count_fired and error_rate_fired:
        for r in results:
            r.severity = AlertSeverity.CRITICAL

    if (
        snapshot.avg_latency_ms is not None
        and snapshot.avg_latency_ms >= settings.latency_threshold_ms
    ):
        results.append(
            AnomalyResult(
                alert_type=AlertType.LATENCY_SPIKE,
                severity=AlertSeverity.HIGH,
                service=snapshot.service,
                title=f"Latency spike: {snapshot.service}",
                description=(
                    f"Avg latency {snapshot.avg_latency_ms:.1f}ms ≥ threshold "
                    f"{settings.latency_threshold_ms:.0f}ms in window "
                    f"{snapshot.window_start} – {snapshot.window_end}."
                ),
                metric_value=snapshot.avg_latency_ms,
                threshold_value=settings.latency_threshold_ms,
            )
        )

    return results


# ── Tier 2: Z-score Statistical Detection ────────────────────────────────────


def _tier2(
    snapshot: MetricSnapshot,
    baseline: list[MetricSnapshot],
) -> list[AnomalyResult]:
    """Z-score detection on error_count, total_logs, and avg_latency_ms."""
    results: list[AnomalyResult] = []

    if len(baseline) < 5:
        return results

    # error_count
    error_counts = [float(b.error_count) for b in baseline]
    z_err = _zscore(float(snapshot.error_count), error_counts)
    if z_err is not None and abs(z_err) >= settings.zscore_threshold:
        results.append(
            AnomalyResult(
                alert_type=AlertType.THRESHOLD_BREACH,
                severity=_severity_from_zscore(z_err),
                service=snapshot.service,
                title=f"Error count anomaly (Z-score): {snapshot.service}",
                description=(
                    f"Error count {snapshot.error_count} is {z_err:+.2f}σ from "
                    f"baseline (mean={np.mean(error_counts):.1f}, "
                    f"std={np.std(error_counts):.1f})."
                ),
                metric_value=float(snapshot.error_count),
                zscore=z_err,
            )
        )

    # total_logs (volume)
    volumes = [float(b.total_logs) for b in baseline]
    z_vol = _zscore(float(snapshot.total_logs), volumes)
    if z_vol is not None and abs(z_vol) >= settings.volume_zscore_threshold:
        results.append(
            AnomalyResult(
                alert_type=AlertType.LOG_VOLUME_SPIKE,
                severity=_severity_from_zscore(z_vol),
                service=snapshot.service,
                title=f"Log volume anomaly (Z-score): {snapshot.service}",
                description=(
                    f"Log volume {snapshot.total_logs} is {z_vol:+.2f}σ from "
                    f"baseline (mean={np.mean(volumes):.1f}, "
                    f"std={np.std(volumes):.1f})."
                ),
                metric_value=float(snapshot.total_logs),
                zscore=z_vol,
            )
        )

    # avg_latency_ms
    if snapshot.avg_latency_ms is not None:
        latencies = [
            float(b.avg_latency_ms)
            for b in baseline
            if b.avg_latency_ms is not None
        ]
        if len(latencies) >= 5:
            z_lat = _zscore(snapshot.avg_latency_ms, latencies)
            if z_lat is not None and abs(z_lat) >= settings.zscore_threshold:
                results.append(
                    AnomalyResult(
                        alert_type=AlertType.LATENCY_SPIKE,
                        severity=_severity_from_zscore(z_lat),
                        service=snapshot.service,
                        title=f"Latency anomaly (Z-score): {snapshot.service}",
                        description=(
                            f"Avg latency {snapshot.avg_latency_ms:.1f}ms is "
                            f"{z_lat:+.2f}σ from baseline "
                            f"(mean={np.mean(latencies):.1f}ms, "
                            f"std={np.std(latencies):.1f}ms)."
                        ),
                        metric_value=snapshot.avg_latency_ms,
                        zscore=z_lat,
                    )
                )

    return results


# ── Tier 3: IsolationForest ───────────────────────────────────────────────────


def _tier3(
    snapshot: MetricSnapshot,
    baseline: list[MetricSnapshot],
) -> list[AnomalyResult]:
    """Fit an IsolationForest on baseline windows and score the current snapshot."""
    if len(baseline) < settings.isolation_forest_min_samples:
        return []

    X_train = np.array(
        [
            [float(b.error_count), float(b.total_logs), b.avg_latency_ms or 0.0]
            for b in baseline
        ],
        dtype=float,
    )

    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X_train)

    x_current = np.array(
        [[float(snapshot.error_count), float(snapshot.total_logs), snapshot.avg_latency_ms or 0.0]],
        dtype=float,
    )
    score = float(model.decision_function(x_current)[0])
    label = int(model.predict(x_current)[0])

    if score < -0.1 and label == -1:
        return [
            AnomalyResult(
                alert_type=AlertType.ISOLATION_FOREST,
                severity=_severity_from_if_score(score),
                service=snapshot.service,
                title=f"IsolationForest anomaly: {snapshot.service}",
                description=(
                    f"Snapshot flagged as outlier (score={score:.3f}, "
                    f"error_count={snapshot.error_count}, "
                    f"total_logs={snapshot.total_logs}, "
                    f"avg_latency_ms={snapshot.avg_latency_ms or 0.0:.1f}ms)."
                ),
                metric_value=score,
            )
        ]

    return []


# ── Orchestrator ──────────────────────────────────────────────────────────────


def detect_anomalies(db: Session, snapshot: MetricSnapshot) -> list[AnomalyResult]:
    """Run all three tiers against `snapshot` and return combined results."""
    baseline = _get_baseline(db, snapshot.service, snapshot.id)
    results: list[AnomalyResult] = []
    results.extend(_tier1(snapshot))
    results.extend(_tier2(snapshot, baseline))
    results.extend(_tier3(snapshot, baseline))
    return results


def create_alert_from_result(
    db: Session,
    result: AnomalyResult,
    snapshot: MetricSnapshot,
) -> Alert:
    """Add an Alert row to the session; caller is responsible for commit/flush."""
    alert = Alert(
        alert_type=result.alert_type,
        severity=result.severity,
        status=AlertStatus.OPEN,
        service=result.service,
        title=result.title,
        description=result.description,
        metric_value=result.metric_value,
        threshold_value=result.threshold_value,
        zscore=result.zscore,
        snapshot_id=snapshot.id,
    )
    db.add(alert)
    return alert
