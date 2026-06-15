"""Config guards: a misconfigured env value fails fast at startup instead of silently misbehaving.

Without these bounds a `0`/negative interval would busy-loop the expiry scheduler, a non-positive
threshold would force-fail fresh calls, a non-positive webhook tolerance would reject every signed
request, and a non-positive OpenAI timeout would defeat the latency bound. We want a loud
ValidationError at boot, not a subtle production misbehavior.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_are_sane():
    s = Settings(_env_file=None)
    assert s.expiry_interval_minutes == 10
    assert s.expiry_threshold_minutes == 30
    assert s.webhook_tolerance_seconds == 300
    assert s.openai_timeout_seconds == 20.0
    assert s.openai_max_retries == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("expiry_interval_minutes", 0),
        ("expiry_interval_minutes", -1),
        ("expiry_threshold_minutes", 0),
        ("expiry_threshold_minutes", -5),
        ("webhook_tolerance_seconds", 0),
        ("webhook_tolerance_seconds", -10),
        ("openai_timeout_seconds", 0),
        ("openai_timeout_seconds", -0.5),
        ("openai_max_retries", -1),
    ],
)
def test_nonpositive_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_zero_retries_is_allowed():
    # max_retries=0 (no retries) is a legitimate choice; only negatives are rejected.
    assert Settings(_env_file=None, openai_max_retries=0).openai_max_retries == 0
