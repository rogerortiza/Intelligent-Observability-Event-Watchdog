"""Integration tests for POST /ingest, POST /ingest/batch, GET /logs."""
from __future__ import annotations


def test_ingest_single_log_returns_201(client):
    resp = client.post(
        "/api/v1/logs/ingest",
        json={
            "level": "INFO",
            "service": "ingest-test-svc",
            "message": "Integration test log entry",
            "latency_ms": 42.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["service"] == "ingest-test-svc"
    assert data["level"] == "INFO"
    assert "id" in data


def test_ingest_batch_returns_201_with_count(client):
    resp = client.post(
        "/api/v1/logs/ingest/batch",
        json={
            "logs": [
                {
                    "level": "ERROR",
                    "service": "batch-test-svc",
                    "message": f"batch-msg-{i}",
                    "latency_ms": 100.0,
                }
                for i in range(5)
            ]
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["count"] == 5


def test_ingest_batch_empty_list_returns_422(client):
    resp = client.post("/api/v1/logs/ingest/batch", json={"logs": []})
    assert resp.status_code == 422


def test_ingest_batch_over_1000_entries_returns_422(client):
    resp = client.post(
        "/api/v1/logs/ingest/batch",
        json={
            "logs": [
                {"level": "INFO", "service": "overflow-svc", "message": "x", "latency_ms": 10.0}
                for _ in range(1001)
            ]
        },
    )
    assert resp.status_code == 422


def test_get_logs_returns_paginated_response(client):
    resp = client.get("/api/v1/logs")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("items", "total", "limit", "offset"):
        assert key in data, f"Missing key: {key}"


def test_get_logs_filters_by_service(client):
    svc = "filter-unique-svc-logs-001"
    client.post(
        "/api/v1/logs/ingest",
        json={"level": "DEBUG", "service": svc, "message": "filter-test", "latency_ms": 5.0},
    )
    resp = client.get("/api/v1/logs", params={"service": svc})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(item["service"] == svc for item in items)


def test_get_logs_filters_by_level(client):
    svc = "level-filter-svc-001"
    client.post(
        "/api/v1/logs/ingest",
        json={"level": "CRITICAL", "service": svc, "message": "crit-msg", "latency_ms": 3000.0},
    )
    resp = client.get("/api/v1/logs", params={"service": svc, "level": "CRITICAL"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(item["level"] == "CRITICAL" for item in items)
