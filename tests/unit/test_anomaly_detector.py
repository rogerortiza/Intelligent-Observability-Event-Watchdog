"""Unit tests for the three-tier anomaly detection engine."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import AlertSeverity, AlertType, MetricSnapshot
from app.services.anomaly_detector import (
    _severity_from_zscore,
    _tier1,
    _tier2,
    _tier3,
    _zscore,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _snap(**kwargs) -> MetricSnapshot:
    now = _utcnow()
    defaults = dict(
        service="unit-test-svc",
        window_start=now,
        window_end=now,
        total_logs=100,
        error_count=0,
        error_rate=0.0,
        avg_latency_ms=100.0,
        p95_latency_ms=200.0,
        max_latency_ms=500.0,
    )
    defaults.update(kwargs)
    return MetricSnapshot(**defaults)


# ── _zscore ────────────────────────────────────────────────────────────────────


def test_zscore_returns_none_with_fewer_than_5_samples():
    assert _zscore(10.0, [1.0, 2.0, 3.0, 4.0]) is None


def test_zscore_returns_elevated_value_for_spike():
    baseline = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    z = _zscore(50.0, baseline)
    assert z is not None
    assert z > 2.5


# ── _tier1 ─────────────────────────────────────────────────────────────────────


def test_tier1_fires_threshold_breach_on_error_count():
    snap = _snap(error_count=15, error_rate=0.05, avg_latency_ms=100.0)
    results = _tier1(snap)
    assert any(r.alert_type == AlertType.THRESHOLD_BREACH for r in results)


def test_tier1_dual_breach_upgrades_both_results_to_critical():
    snap = _snap(error_count=15, error_rate=0.30, avg_latency_ms=100.0)
    results = _tier1(snap)
    assert len(results) >= 2
    assert all(r.severity == AlertSeverity.CRITICAL for r in results)


def test_tier1_returns_empty_list_below_all_thresholds():
    snap = _snap(error_count=1, error_rate=0.01, avg_latency_ms=100.0)
    assert _tier1(snap) == []


# ── _tier2 ─────────────────────────────────────────────────────────────────────


def test_tier2_fires_on_extreme_error_count_spike():
    baseline = [
        _snap(service="t2-svc", error_count=i, total_logs=100, error_rate=0.01, avg_latency_ms=50.0)
        for i in range(6)
    ]
    spike = _snap(service="t2-svc", error_count=5000, total_logs=100, error_rate=0.01, avg_latency_ms=50.0)
    results = _tier2(spike, baseline)
    assert len(results) > 0


# ── _tier3 ─────────────────────────────────────────────────────────────────────


def test_tier3_returns_empty_with_fewer_than_20_baseline_windows():
    baseline = [_snap(service="t3-svc") for _ in range(10)]
    snap = _snap(service="t3-svc", error_count=9999)
    assert _tier3(snap, baseline) == []


# ── _severity_from_zscore ──────────────────────────────────────────────────────


def test_severity_from_zscore_maps_all_levels_correctly():
    assert _severity_from_zscore(5.5) == AlertSeverity.CRITICAL
    assert _severity_from_zscore(4.2) == AlertSeverity.HIGH
    assert _severity_from_zscore(3.1) == AlertSeverity.MEDIUM
    assert _severity_from_zscore(2.0) == AlertSeverity.LOW
