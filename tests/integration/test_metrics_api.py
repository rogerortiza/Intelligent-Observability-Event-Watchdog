"""Integration tests for GET /metrics/summary, /timeseries, /snapshots."""
from __future__ import annotations


def test_summary_returns_expected_schema(client):
    resp = client.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("health_score", "total_logs_24h", "error_rate_24h", "active_alerts", "services_monitored"):
        assert key in data, f"Missing summary field: {key}"


def test_summary_health_score_is_in_valid_range(client):
    resp = client.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    score = resp.json()["health_score"]
    assert 0.0 <= score <= 100.0


def test_timeseries_valid_metric_returns_response_structure(client):
    resp = client.get("/api/v1/metrics/timeseries", params={"metric": "error_count"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric"] == "error_count"
    assert "points" in data
    assert isinstance(data["points"], list)


def test_timeseries_invalid_metric_returns_422(client):
    resp = client.get("/api/v1/metrics/timeseries", params={"metric": "not_a_real_metric"})
    assert resp.status_code == 422


def test_snapshots_returns_paginated_response(client):
    resp = client.get("/api/v1/metrics/snapshots")
    assert resp.status_code == 200
    data = resp.json()
    assert all(k in data for k in ("items", "total", "limit", "offset"))
    assert isinstance(data["items"], list)
