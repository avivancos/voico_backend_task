"""Property-based tests (Hypothesis) over the PURE helpers.

Deliberately scoped to pure functions only — no DB, no async, no fixtures — which sidesteps the
known hypothesis × pytest-asyncio × function-scoped-fixture friction and is exactly where property
testing has the most signal: the LIKE-escaping (a security boundary), phone normalization, and the
strict expiry boundary all hold for *every* input, not just the handful the example tests pin.
"""

import re
from datetime import datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.modules.calls.repository import _escape_like, _phone_digits
from app.modules.calls.tasks import is_expired

pytestmark = pytest.mark.property


def _unescape_like(s: str) -> str:
    """Reverse _escape_like: a backslash makes the next char literal."""
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


@given(st.text())
def test_escape_like_is_lossless_and_leaves_no_active_wildcard(s):
    escaped = _escape_like(s)
    # Round-trips exactly -> the pattern represents s and nothing more (no wildcard injection).
    assert _unescape_like(escaped) == s
    # Every % and _ in the output is escaped (preceded by a backslash), so none acts as a wildcard.
    for i, ch in enumerate(escaped):
        if ch in "%_":
            assert i > 0 and escaped[i - 1] == "\\"


@given(st.text())
def test_phone_digits_keeps_only_digits_idempotently(s):
    out = _phone_digits(s)
    assert re.fullmatch(r"\d*", out) is not None  # only digit characters remain
    assert _phone_digits(out) == out  # idempotent
    assert len(out) <= len(s)  # never adds characters


@given(
    now=st.datetimes(min_value=datetime(2001, 1, 1), max_value=datetime(2100, 1, 1)),
    threshold=st.floats(min_value=0, max_value=100_000, allow_nan=False, allow_infinity=False),
)
def test_is_expired_boundary_is_strict_and_monotonic(now, threshold):
    started_exact = now - timedelta(minutes=threshold)
    # Strict "<": a call exactly at the threshold is NOT yet expired; one second older IS.
    assert is_expired(started_exact, now, threshold) is False
    assert is_expired(started_exact - timedelta(seconds=1), now, threshold) is True
    # Monotonic: if a call is expired, any older call is expired too.
    assert is_expired(started_exact - timedelta(minutes=1), now, threshold) is True
