"""Behavioral tests for Task 3 — Stale Call Auto-Expiry.

Real SQLite, no mocks, injected clock (no sleep, no wall-clock). We exercise ``run_expiry_once`` —
the single iteration the scheduler loop runs — directly, so the logic is deterministic and the
background loop stays a thin wrapper. The scheduler loop/lifespan itself is covered in
``test_scheduler.py``.
"""

from datetime import datetime, timedelta

import pytest

from app.core.config import Settings
from app.modules.calls.schema import Call, CallStatus
from app.modules.calls.tasks import run_expiry_once

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, 12, 0, 0)  # the injected clock; nothing here depends on real time


async def _get(session_factory, call_id) -> Call:
    async with session_factory() as session:
        return await session.get(Call, call_id)


async def test_expires_in_progress_older_than_threshold(make_call, session_factory):
    stale = await make_call(status=CallStatus.in_progress, minutes_ago=31, now=NOW)

    count = await run_expiry_once(session_factory, threshold_minutes=30, now=NOW)

    assert count == 1
    got = await _get(session_factory, stale.id)
    assert got.status == CallStatus.failed
    assert got.updated_at == NOW  # writer-set timestamp, from the injected clock


async def test_threshold_boundary_is_strict(make_call, session_factory):
    # "more than 30 minutes" -> a call started exactly 29 min ago stays, 31 min ago expires.
    young = await make_call(status=CallStatus.in_progress, minutes_ago=29, now=NOW)
    old = await make_call(status=CallStatus.in_progress, minutes_ago=31, now=NOW)

    count = await run_expiry_once(session_factory, threshold_minutes=30, now=NOW)

    assert count == 1
    assert (await _get(session_factory, young.id)).status == CallStatus.in_progress
    assert (await _get(session_factory, old.id)).status == CallStatus.failed


async def test_does_not_touch_terminal_calls(make_call, session_factory):
    # Already-resolved calls must never be re-failed, however old they are.
    succ = await make_call(status=CallStatus.success, minutes_ago=120, now=NOW)
    fail = await make_call(status=CallStatus.failed, minutes_ago=120, now=NOW)

    count = await run_expiry_once(session_factory, threshold_minutes=30, now=NOW)

    assert count == 0
    assert (await _get(session_factory, succ.id)).status == CallStatus.success
    assert (await _get(session_factory, fail.id)).status == CallStatus.failed


async def test_expiry_is_idempotent(make_call, session_factory):
    await make_call(status=CallStatus.in_progress, minutes_ago=31, now=NOW)

    first = await run_expiry_once(session_factory, threshold_minutes=30, now=NOW)
    second = await run_expiry_once(
        session_factory, threshold_minutes=30, now=NOW + timedelta(minutes=5)
    )

    assert first == 1
    assert second == 0  # nothing left to expire on a second pass


async def test_expiry_is_a_single_batch_update(make_call, session_factory, count_queries):
    for _ in range(20):
        await make_call(status=CallStatus.in_progress, minutes_ago=60, now=NOW)

    before = count_queries["n"]
    count = await run_expiry_once(session_factory, threshold_minutes=30, now=NOW)
    delta = count_queries["n"] - before

    assert count == 20  # all expired together
    assert delta <= 3, f"expected one batch UPDATE, got {delta} statements (per-row loop?)"


def test_config_exposes_env_tunable_interval_and_threshold(monkeypatch):
    # Defaults match the spec (10 / 30), independent of any local .env file.
    defaults = Settings(_env_file=None)
    assert defaults.expiry_interval_minutes == 10
    assert defaults.expiry_threshold_minutes == 30

    # The actual requirement: tunable from the environment without touching code.
    monkeypatch.setenv("EXPIRY_THRESHOLD_MINUTES", "0.1")
    monkeypatch.setenv("EXPIRY_INTERVAL_MINUTES", "0.2")
    tuned = Settings(_env_file=None)
    assert tuned.expiry_threshold_minutes == 0.1
    assert tuned.expiry_interval_minutes == 0.2
