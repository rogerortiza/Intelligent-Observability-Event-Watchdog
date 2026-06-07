"""Standalone smoke test — runs 8 end-to-end checks against a live server.

Usage:
    python tests/smoke_test.py

Environment:
    API_BASE_URL  Base URL of the running FastAPI server (default: http://localhost:8000)

Exit codes:
    0  All checks passed
    1  One or more checks failed
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any

import requests

_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/") + "/api/v1"
_TIMEOUT = 10

_PASS: list[str] = []
_FAIL: list[str] = []


def _check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        _PASS.append(label)
        print(f"  [PASS] {label}")
    else:
        _FAIL.append(label)
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def _get(path: str, **params: Any) -> requests.Response:
    return requests.get(f"{_BASE}{path}", params=params or None, timeout=_TIMEOUT)


def _post(path: str, body: dict | None = None) -> requests.Response:
    return requests.post(f"{_BASE}{path}", json=body, timeout=_TIMEOUT)


def main() -> int:
    print(f"\nSmoke test → {_BASE}\n")
    t0 = time.monotonic()

    # Step 1 — health check
    try:
        r = _get("/health")
        _check("Step 1: GET /health returns 200", r.status_code == 200, f"HTTP {r.status_code}")
        _check("Step 1: health.status == ok", r.json().get("status") == "ok", str(r.json()))
    except Exception as exc:
        _check("Step 1: GET /health reachable", False, str(exc))
        print("\nAPI unreachable — aborting smoke test.")
        return 1

    # Step 2 — seed all services
    r = _post("/simulate/seed-all-services")
    _check("Step 2: seed-all-services returns 201", r.status_code == 201, f"HTTP {r.status_code}")
    seeded = r.json().get("services", []) if r.status_code == 201 else []
    _check("Step 2: seeded 5 services", len(seeded) == 5, f"got {seeded}")

    # Step 3 — inject error spike
    r = _post("/simulate/error-spike", {"service": "auth-service", "error_count": 40, "spike_duration_minutes": 5})
    _check("Step 3: error-spike returns 201", r.status_code == 201, f"HTTP {r.status_code}")

    # Step 4 — trigger watchdog
    r = _post("/simulate/run-watchdog")
    _check("Step 4: run-watchdog returns 200", r.status_code == 200, f"HTTP {r.status_code}")

    # Step 5 — wait for background watchdog task
    print("  [WAIT] Sleeping 5s for watchdog background task …")
    time.sleep(5)

    # Step 6 — assert alerts endpoint
    r = _get("/alerts", limit=50)
    _check("Step 6: GET /alerts returns 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        body = r.json()
        _check("Step 6: alerts response has paginated shape", "items" in body and "total" in body, str(body.keys()))

    # Step 7 — assert metrics summary
    r = _get("/metrics/summary")
    _check("Step 7: GET /metrics/summary returns 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        body = r.json()
        score = body.get("health_score", -1)
        _check("Step 7: health_score is in [0, 100]", 0.0 <= score <= 100.0, f"score={score}")

    # Step 8 — assert webhook deliveries endpoint
    r = _get("/webhooks")
    _check("Step 8: GET /webhooks returns 200", r.status_code == 200, f"HTTP {r.status_code}")

    elapsed = round(time.monotonic() - t0, 1)
    passed, failed = len(_PASS), len(_FAIL)
    print(f"\n{'─' * 50}")
    print(f"Results: {passed} passed, {failed} failed  ({elapsed}s)")

    if failed == 0:
        print("PASS\n")
        return 0
    else:
        print(f"FAIL — {failed} check(s) did not pass\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
