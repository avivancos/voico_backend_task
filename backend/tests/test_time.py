"""The single clock helper returns naive UTC (consistent with the existing columns)."""

from datetime import datetime, timezone

from app.core.time import now_utc


def test_now_utc_is_naive():
    assert now_utc().tzinfo is None


def test_now_utc_is_current():
    before = datetime.now(timezone.utc).replace(tzinfo=None)
    value = now_utc()
    after = datetime.now(timezone.utc).replace(tzinfo=None)
    assert before <= value <= after
