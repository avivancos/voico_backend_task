"""Single source of truth for the application clock.

All timestamps are NAIVE UTC to stay consistent with the existing columns. Use this helper instead
of the deprecated ``datetime.utcnow()``, and inject it where determinism matters (e.g. the
background jobs) so tests can pin the clock.
"""

from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return the current UTC time as a naive datetime (tzinfo stripped)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
