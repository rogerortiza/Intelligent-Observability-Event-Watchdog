"""Watchdog scheduler — stub replaced by full implementation in Task 23.

This module defines the public interface (start_watchdog, stop_watchdog,
is_running) so main.py can import cleanly before Task 23 is merged.
"""

from __future__ import annotations

import asyncio

_task: asyncio.Task | None = None  # type: ignore[type-arg]


async def run_watchdog_cycle() -> None:
    """Execute one watchdog cycle (no-op until Task 23)."""


async def start_watchdog() -> None:
    """Schedule the background watchdog loop."""
    global _task
    _task = asyncio.create_task(_loop())


async def stop_watchdog() -> None:
    """Cancel the background watchdog loop."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None


def is_running() -> bool:
    """Return True if the watchdog background task is active."""
    return _task is not None and not _task.done()


async def _loop() -> None:
    """Minimal loop — real cycle logic added in Task 23."""
    from app.config import settings

    while True:
        await asyncio.sleep(settings.watchdog_interval_seconds)
