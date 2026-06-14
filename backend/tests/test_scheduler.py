"""Unit tests for the stale-call expiry *scheduler* (the background loop + its lifespan wiring).

The loop takes all its dependencies as parameters (session_factory / interval / threshold / a
``run_once`` callable), so we drive it with a fake sweep and a sub-millisecond interval — no global
monkeypatching, no real DB, no wall-clock waits beyond a few tens of ms. ``test_expiry.py`` covers the
sweep itself; this file covers the loop and the FastAPI lifespan that owns it.
"""

import asyncio
import logging

import pytest
from asgi_lifespan import LifespanManager

from app.main import app
from app.modules.calls.tasks import expiry_scheduler

pytestmark = pytest.mark.unit


async def _run_briefly(task: asyncio.Task, seconds: float = 0.05) -> None:
    """Let the loop spin for a moment, then cancel and await it cleanly."""
    try:
        await asyncio.sleep(seconds)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def _sweeper_tasks() -> list:
    return [
        t
        for t in asyncio.all_tasks()
        if getattr(t.get_coro(), "__qualname__", "") == "expiry_scheduler"
    ]


async def test_lifespan_starts_and_cancels_the_sweeper():
    # Exercises the REAL lifespan wiring (not a faked loop): the scheduler task exists while the app
    # is up and is cancelled cleanly on shutdown.
    assert _sweeper_tasks() == []
    async with LifespanManager(app):
        await asyncio.sleep(0)  # let create_task schedule
        running = _sweeper_tasks()
        assert len(running) == 1 and not running[0].done()
    assert _sweeper_tasks() == []  # cancelled + awaited on shutdown, no leak


async def test_loop_runs_on_cadence():
    calls: list[float] = []

    async def fake_once(session_factory, *, threshold_minutes):
        calls.append(threshold_minutes)

    task = asyncio.create_task(
        expiry_scheduler(None, interval_seconds=0.001, threshold_minutes=30, run_once=fake_once)
    )
    await _run_briefly(task)

    assert len(calls) >= 2  # ran every interval, repeatedly
    assert all(t == 30 for t in calls)  # the injected threshold is passed through unchanged


async def test_loop_survives_a_failing_sweep():
    calls: list[int] = []

    async def fake_once(session_factory, *, threshold_minutes):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")  # the first sweep blows up

    task = asyncio.create_task(
        expiry_scheduler(None, interval_seconds=0.001, threshold_minutes=30, run_once=fake_once)
    )
    await _run_briefly(task)

    assert len(calls) >= 2  # one bad sweep did not kill the loop


async def test_sleeps_before_first_sweep():
    # Boot grace: with a long interval, no sweep fires during startup. (christian-hawk has the
    # sleep-first behavior but never tests it.)
    calls: list[int] = []

    async def fake_once(session_factory, *, threshold_minutes):
        calls.append(1)

    task = asyncio.create_task(
        expiry_scheduler(None, interval_seconds=3600, threshold_minutes=30, run_once=fake_once)
    )
    try:
        await asyncio.sleep(0.02)  # well inside the first interval
        assert calls == []  # nothing swept yet — it sleeps first
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_failing_sweep_is_logged(caplog):
    async def fake_once(session_factory, *, threshold_minutes):
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="app.modules.calls.tasks"):
        task = asyncio.create_task(
            expiry_scheduler(None, interval_seconds=0.001, threshold_minutes=30, run_once=fake_once)
        )
        await _run_briefly(task, seconds=0.02)

    assert "stale-call expiry sweep failed" in caplog.text
