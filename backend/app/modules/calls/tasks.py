"""Background tasks for the calls module."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from app.core.time import now_utc
from app.modules.calls.repository import CallRepository
from app.modules.calls.service import CallService

logger = logging.getLogger(__name__)


def is_expired(started_at: datetime, now: datetime, threshold_minutes: float) -> bool:
    """Pure predicate mirroring the expiry SQL: a call is stale once it has been in_progress for
    *strictly* more than ``threshold_minutes`` (``started_at < now - threshold``). Kept as the single,
    SQLite-independent source of truth for the boundary so it can be exhaustively property-tested.
    """
    return started_at < now - timedelta(minutes=threshold_minutes)


async def run_expiry_once(
    session_factory,
    *,
    threshold_minutes: float,
    now: Optional[datetime] = None,
) -> int:
    """Run one stale-call expiry sweep and commit it, logging how many calls were expired.

    This owns its own session and commits explicitly — it is a background job, not a request, so it
    does not go through the ``@session_manager`` decorator. ``now`` is injectable for deterministic
    tests; it defaults to the single application clock.
    """
    stamp = now if now is not None else now_utc()
    async with session_factory() as session:
        service = CallService(CallRepository(session))
        count = await service.expire_stale_calls(now=stamp, threshold_minutes=threshold_minutes)
        await session.commit()
    logger.info(
        "Stale-call expiry: marked %d call(s) failed (idle > %g min)", count, threshold_minutes
    )
    return count


async def expiry_scheduler(
    session_factory,
    *,
    interval_seconds: float,
    threshold_minutes: float,
    run_once: Callable = run_expiry_once,
) -> None:
    """Run the expiry sweep every ``interval_seconds``, forever, until cancelled.

    Sleeps *before* the first sweep, so starting the app never triggers an immediate run (and a
    short-lived test that boots the app via its lifespan never runs one). A failed sweep is logged
    and the loop continues — one bad run must not stop the scheduler. Every dependency is injected
    (no module globals), so both the loop and the lifespan wiring are unit-testable.
    """
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await run_once(session_factory, threshold_minutes=threshold_minutes)
        except Exception:
            logger.exception("stale-call expiry sweep failed")
