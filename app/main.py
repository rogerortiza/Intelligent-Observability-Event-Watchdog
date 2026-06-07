"""FastAPI application factory — lifespan, middleware, routers, health endpoint."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, init_db
from app.routers import alerts, logs, metrics, webhooks
from app.schemas import HealthCheck
from app.services import watchdog

_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create tables and launch watchdog. Shutdown: stop watchdog."""
    global _start_time
    _start_time = time.monotonic()
    init_db()
    await watchdog.start_watchdog()
    yield
    await watchdog.stop_watchdog()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(logs.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")


@app.get("/api/v1/health", response_model=HealthCheck, tags=["health"])
def health() -> HealthCheck:
    """Liveness check — reports database dialect and watchdog state."""
    return HealthCheck(
        status="ok",
        version=settings.app_version,
        database=engine.dialect.name,
        watchdog="running" if watchdog.is_running() else "stopped",
        uptime_seconds=round(time.monotonic() - _start_time, 1),
    )
