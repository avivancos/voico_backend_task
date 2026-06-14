"""Leak-guard: the public CallResponse exposes exactly the intended fields.

As later tasks add columns (notes, enrichment_*), update PUBLIC_FIELDS to add ONLY the fields meant
to be public — internal queue/lease/audit columns must never appear in the response.
"""

from app.modules.calls.schema import Call, CallResponse

PUBLIC_FIELDS = {
    "id",
    "phone_number",
    "caller_name",
    "duration_seconds",
    "status",
    "summary",
    "label",
    "started_at",
    "ended_at",
    "created_at",
    "updated_at",
    "raw_transcript",
    "notes",
}


def test_call_response_exposes_only_public_fields():
    assert set(CallResponse.model_fields) == PUBLIC_FIELDS


def test_no_internal_call_column_leaks_into_response():
    # Any Call column that is not declared public must not appear in CallResponse.
    internal = set(Call.model_fields) - PUBLIC_FIELDS
    leaked = internal & set(CallResponse.model_fields)
    assert not leaked, f"internal columns leaked into CallResponse: {sorted(leaked)}"
