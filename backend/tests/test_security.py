"""Security tests for the current API surface — real ASGI app + real SQLite, no mocks.

Scope is matched to what exists today (Task 0 + Task 1): the notes endpoint, list/detail reads,
input validation, and the method allow-list. Each test sends a hostile or malformed input and
asserts the app stays safe — parameterized queries, no mass-assignment, bounded input, typed
path/query, hostile unicode handled. New attack surface (the webhook/AI of Task 4) gets its own
security tests when built.
"""

import unicodedata
import uuid

from app.modules.calls.schema import Call, CallStatus


async def _insert_call(session_factory, **overrides) -> Call:
    async with session_factory() as session:
        call = Call(phone_number="+1 (555) 000-0000", status=CallStatus.in_progress, **overrides)
        session.add(call)
        await session.commit()
        await session.refresh(call)
        return call


async def test_sql_injection_in_notes_is_stored_verbatim_not_executed(client, session_factory):
    victim = await _insert_call(session_factory)
    bystander = await _insert_call(session_factory)
    payload = "Robert'); DROP TABLE calls;-- ' OR '1'='1"

    resp = await client.patch(f"/api/calls/{victim.id}/notes", json={"notes": payload})
    assert resp.status_code == 200
    assert resp.json()["notes"] == payload  # stored as literal text, not interpreted

    # The table still exists and the bystander row is still queryable -> the SQL never executed.
    listed = await client.get("/api/calls")
    assert listed.status_code == 200
    assert any(row["id"] == str(bystander.id) for row in listed.json()["data"])


async def test_non_uuid_path_id_is_422_not_500(client):
    # A typed UUID path param rejects injection/garbage with 422 — it never reaches the query layer.
    for bad in ["not-a-uuid", "1 OR 1=1", "x' OR '1'='1", "00000000"]:
        resp = await client.patch(f"/api/calls/{bad}/notes", json={"notes": "x"})
        assert resp.status_code == 422, f"{bad!r} -> {resp.status_code}"


async def test_injection_in_status_filter_is_rejected(client):
    # The status filter is a closed enum, so an injection string is a 422, not a query.
    resp = await client.get("/api/calls", params={"status": "success' OR '1'='1"})
    assert resp.status_code == 422


async def test_no_mass_assignment_via_notes_endpoint(client, session_factory):
    call = await _insert_call(session_factory)  # defaults: status=in_progress, summary=None

    # Over-post protected columns alongside notes — the closed model rejects it outright.
    resp = await client.patch(
        f"/api/calls/{call.id}/notes",
        json={
            "notes": "ok",
            "status": "success",
            "summary": "pwned",
            "id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 422

    # And nothing leaked through: protected columns are unchanged.
    got = await client.get(f"/api/calls/{call.id}")
    assert got.json()["status"] == "in_progress"
    assert got.json()["summary"] is None


async def test_notes_endpoint_rejects_other_methods(client, session_factory):
    call = await _insert_call(session_factory)
    for method in ("POST", "PUT", "DELETE"):
        resp = await client.request(method, f"/api/calls/{call.id}/notes", json={"notes": "x"})
        assert resp.status_code == 405, f"{method} -> {resp.status_code}"


async def test_oversize_notes_is_rejected_before_persistence(client, session_factory):
    call = await _insert_call(session_factory)
    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": "A" * 1_000_000})
    assert resp.status_code == 422  # bounded by max_length, rejected before any DB work
    got = await client.get(f"/api/calls/{call.id}")
    assert got.json()["notes"] is None  # not persisted


async def test_hostile_unicode_round_trips_without_corruption(client, session_factory):
    call = await _insert_call(session_factory)
    # RTL override + zero-width space + control char: must persist faithfully and never 500.
    hostile = "in‮verted​\tend"
    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": hostile})
    assert resp.status_code == 200

    expected = unicodedata.normalize("NFC", hostile).strip()
    assert resp.json()["notes"] == expected
    got = await client.get(f"/api/calls/{call.id}")
    assert got.json()["notes"] == expected
