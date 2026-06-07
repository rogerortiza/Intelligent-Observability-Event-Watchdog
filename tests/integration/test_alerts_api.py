"""Integration tests for GET /alerts, GET /alerts/{id}, acknowledge, resolve."""
from __future__ import annotations


def test_list_alerts_returns_paginated_response(client):
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert all(k in data for k in ("items", "total", "limit", "offset"))
    assert isinstance(data["items"], list)


def test_get_alert_by_id_returns_correct_alert(client, sample_alert):
    resp = client.get(f"/api/v1/alerts/{sample_alert.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sample_alert.id
    assert data["service"] == sample_alert.service
    assert data["status"] == "OPEN"


def test_get_alert_not_found_returns_404(client):
    resp = client.get("/api/v1/alerts/999999")
    assert resp.status_code == 404


def test_acknowledge_open_alert_sets_acknowledged_status(client, sample_alert):
    resp = client.put(
        f"/api/v1/alerts/{sample_alert.id}/acknowledge",
        json={"note": "Investigating now"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["acknowledged_at"] is not None


def test_acknowledge_non_open_alert_returns_400(client, sample_alert):
    client.put(f"/api/v1/alerts/{sample_alert.id}/acknowledge", json={"note": "first"})
    resp = client.put(f"/api/v1/alerts/{sample_alert.id}/acknowledge", json={"note": "second"})
    assert resp.status_code == 400


def test_resolve_alert_sets_resolved_status(client, sample_alert):
    resp = client.put(f"/api/v1/alerts/{sample_alert.id}/resolve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["resolved_at"] is not None
