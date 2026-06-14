"""Security tests for the current API surface — real ASGI app + real SQLite, no mocks.

Scope is matched to what exists today (Task 0–2): the notes endpoint, the list/filter/search/sort
surface, input validation, and the method allow-list. Each test sends a hostile or malformed input
and asserts the app stays safe — parameterized queries, escaped LIKE patterns, a whitelisted sort
column, no mass-assignment, bounded input (no bulk extraction, no integer overflow), typed
path/query, hostile unicode handled. New attack surface (the webhook/AI of Task 4) gets its own
security tests when built.
"""

import unicodedata
import uuid

from app.modules.calls.schema import Call, CallStatus


async def _insert_call(session_factory, **overrides) -> Call:
    overrides.setdefault("phone_number", "+1 (555) 000-0000")
    overrides.setdefault("status", CallStatus.in_progress)
    async with session_factory() as session:
        call = Call(**overrides)
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


# --- list / filter / search / sort surface (Task 2) -----------------------------------------


async def test_sql_injection_in_caller_name_filter_is_literal_not_executed(client, session_factory):
    await _insert_call(session_factory, caller_name="Alice")
    await _insert_call(session_factory, caller_name="Bob")

    # The classic tautology: if the term were concatenated into SQL, OR '1'='1 would return everyone.
    resp = await client.get("/api/calls", params={"caller_name": "' OR '1'='1"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0  # matched as a literal substring -> nobody, not everyone

    # A destructive payload: it is bound as a parameter, so the table is still here afterwards.
    drop = await client.get("/api/calls", params={"caller_name": "x'; DROP TABLE calls;--"})
    assert drop.status_code == 200
    assert (await client.get("/api/calls")).json()["total"] == 2  # table intact, rows queryable


async def test_like_wildcards_in_caller_name_cannot_broaden_the_match(client, session_factory):
    # If `_` were an unescaped LIKE wildcard, it would match any single character (every row). It is
    # escaped, so it only matches a literal underscore.
    underscore = await _insert_call(session_factory, caller_name="a_b")
    await _insert_call(session_factory, caller_name="axb")
    await _insert_call(session_factory, caller_name="ab")

    resp = await client.get("/api/calls", params={"caller_name": "_"})
    assert resp.status_code == 200
    assert {r["id"] for r in resp.json()["data"]} == {str(underscore.id)}


async def test_phone_filter_injection_is_neutralized_by_digit_normalization(
    client, session_factory
):
    row = await _insert_call(session_factory, phone_number="+1 (555) 201-4832")

    # No digits in the payload -> the phone filter degrades to "no filter"; nothing is executed.
    resp = await client.get("/api/calls", params={"phone": "'; DROP TABLE calls;--"})
    assert resp.status_code == 200
    assert any(r["id"] == str(row.id) for r in resp.json()["data"])
    assert (await client.get("/api/calls")).json()["total"] == 1  # table untouched


async def test_page_size_is_capped_to_prevent_bulk_extraction(client):
    # An attacker cannot pull the whole table in one request; the page size is bounded.
    assert (await client.get("/api/calls", params={"page_size": 100_000})).status_code == 422
    assert (await client.get("/api/calls", params={"page_size": 0})).status_code == 422


async def test_no_hostile_list_query_param_yields_a_500(client, session_factory):
    # The invariant: every hostile filter/sort/paging input is either handled safely (200) or
    # rejected at the boundary (422) — never a 500 — and the table survives all of them.
    await _insert_call(session_factory, caller_name="Alice")
    hostile = [
        {"caller_name": "Robert'); DROP TABLE calls;--"},
        {"phone": "%' OR 1=1 --"},
        {"label": "Sales inquiry' OR '1'='1"},
        {"status": "success'--"},
        {"sort_by": "id; DROP TABLE calls"},
        {"sort_dir": "asc); DELETE FROM calls;--"},
        {"min_duration": "99999999999999999999999"},
        {"max_duration": "-1"},
        {"page": "99999999999999999999999"},
        {"page_size": "100000"},
    ]
    for params in hostile:
        resp = await client.get("/api/calls", params=params)
        assert resp.status_code in (200, 422), f"{params} -> {resp.status_code}"

    assert (await client.get("/api/calls")).json()["total"] == 1  # survived every attack
