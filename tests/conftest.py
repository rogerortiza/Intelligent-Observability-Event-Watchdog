"""Pytest configuration — SQLite test DB, TestClient, and shared fixtures."""
from __future__ import annotations

import os
from datetime import datetime, timezone

# Force SQLite for all tests.  Must happen before any app import so that
# pydantic-settings reads the SQLite URL when the settings singleton is created.
_TEST_DB: str = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_watchdog.db")
os.environ["SUPABASE_DB_URL"] = _TEST_DB

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.database as _db_module  # noqa: E402 — import after env patch

# Re-create the engine with SQLite thread-safety flag, then patch the module so
# that watchdog and init_db use the same test engine throughout the session.
_test_engine = create_engine(
    _TEST_DB,
    connect_args={"check_same_thread": False} if "sqlite" in _TEST_DB else {},
    pool_pre_ping=True,
)
_TestSession = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)
_db_module.engine = _test_engine
_db_module.SessionLocal = _TestSession

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Alert, AlertSeverity, AlertStatus, AlertType  # noqa: E402


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    from app import models  # noqa: F401 — registers ORM models with Base
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(scope="session")
def client(_init_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(_init_db):
    session = _TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_log_entry(client):
    resp = client.post(
        "/api/v1/logs/ingest",
        json={
            "level": "ERROR",
            "service": "fixture-service",
            "message": "Fixture test error message",
            "latency_ms": 500.0,
            "host": "pod-1.fixture-service",
            "trace_id": "fixture-trace-001",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def sample_alert(db):
    alert = Alert(
        alert_type=AlertType.THRESHOLD_BREACH,
        severity=AlertSeverity.HIGH,
        service="fixture-alert-service",
        title="Fixture Test Alert",
        description="Alert created by test fixture",
        status=AlertStatus.OPEN,
        triggered_at=_utcnow(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
