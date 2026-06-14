"""Behavioral tests for Task 2 — Advanced Filtering & Search.

Real ASGI app + real SQLite, no mocks. Each test seeds calls with controlled attributes and
asserts the list endpoint filters/sorts/counts correctly. The headline test here is the
``label`` regression: the column stores the enum *member name* (``sales_inquiry``) while the API
speaks the *value* (``"Sales inquiry"``) — a naive ``label == value`` filter returns 0 rows. We
lock the correct behavior in.
"""

import uuid

from sqlalchemy import text

from app.modules.calls.schema import Call, CallLabel, CallStatus


async def _insert(
    session_factory,
    *,
    id=None,
    phone_number="+1 (555) 000-0000",
    caller_name=None,
    duration_seconds=None,
    status=CallStatus.success,
    label=None,
    created_at=None,
) -> Call:
    async with session_factory() as session:
        call = Call(
            phone_number=phone_number,
            caller_name=caller_name,
            duration_seconds=duration_seconds,
            status=status,
            label=label,
        )
        if id is not None:
            call.id = id
        if created_at is not None:
            call.created_at = created_at
            call.started_at = created_at
            call.updated_at = created_at
        session.add(call)
        await session.commit()
        await session.refresh(call)
        return call


def _ids(body) -> set[str]:
    return {row["id"] for row in body["data"]}


# --- caller_name partial / case-insensitive -------------------------------------------------


async def test_caller_name_is_partial_and_case_insensitive(client, session_factory):
    target = await _insert(session_factory, caller_name="María García")
    await _insert(session_factory, caller_name="Derek Owens")

    resp = await client.get("/api/calls", params={"caller_name": "garc"})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(target.id)}


async def test_empty_caller_name_is_ignored_not_a_filter(client, session_factory):
    a = await _insert(session_factory, caller_name="Someone")
    b = await _insert(session_factory, caller_name=None)

    resp = await client.get("/api/calls", params={"caller_name": ""})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(a.id), str(b.id)}  # blank term matches everything


async def test_caller_name_escapes_like_wildcards(client, session_factory):
    literal = await _insert(session_factory, caller_name="50% discount desk")
    await _insert(session_factory, caller_name="no special chars here")

    # A bare '%' must be treated as a literal, not "match anything".
    resp = await client.get("/api/calls", params={"caller_name": "%"})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(literal.id)}


# --- phone partial, digit-normalized --------------------------------------------------------


async def test_phone_search_ignores_formatting(client, session_factory):
    target = await _insert(session_factory, phone_number="+1 (555) 201-4832")
    await _insert(session_factory, phone_number="+44 20 7946 0812")

    # User types raw digits with no separators -> still matches the formatted stored number.
    resp = await client.get("/api/calls", params={"phone": "5552014832"})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(target.id)}


async def test_phone_partial_substring_matches(client, session_factory):
    target = await _insert(session_factory, phone_number="+1 (555) 201-4832")
    await _insert(session_factory, phone_number="+44 20 7946 0812")

    resp = await client.get("/api/calls", params={"phone": "201"})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(target.id)}


# --- label exact match: the value/name regression -------------------------------------------


async def test_label_filter_matches_by_enum_and_returns_rows(client, session_factory):
    """The endpoint accepts the label *value*, returns the right non-empty set, and serializes the
    value back. (This alone does NOT prove the value/name handling — see the raw-compare test below,
    where the trap actually bites.)"""
    a = await _insert(session_factory, label=CallLabel.sales_inquiry)
    b = await _insert(session_factory, label=CallLabel.sales_inquiry)
    await _insert(session_factory, label=CallLabel.support)
    await _insert(session_factory, label=None)

    resp = await client.get("/api/calls", params={"label": "Sales inquiry"})
    assert resp.status_code == 200
    got = _ids(resp.json())
    assert got == {str(a.id), str(b.id)}
    assert all(row["label"] == "Sales inquiry" for row in resp.json()["data"])


async def test_label_endpoint_is_not_a_raw_value_compare(client, session_factory):
    """The trap, where it actually bites: the column stores the member *name* (``sales_inquiry``),
    so a naive ``WHERE label = 'Sales inquiry'`` (the *value*) matches zero rows. Prove the endpoint
    does NOT do that — it returns the rows that the raw value-string query misses."""
    a = await _insert(session_factory, label=CallLabel.sales_inquiry)
    b = await _insert(session_factory, label=CallLabel.sales_inquiry)

    sql = text("SELECT count(*) FROM calls WHERE label = :v")
    async with session_factory() as session:
        conn = await session.connection()
        raw_by_value = (await conn.execute(sql, {"v": "Sales inquiry"})).scalar_one()
        raw_by_name = (await conn.execute(sql, {"v": "sales_inquiry"})).scalar_one()
    assert raw_by_value == 0, "stored representation is the member name, not the value"
    assert raw_by_name == 2

    resp = await client.get("/api/calls", params={"label": "Sales inquiry"})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {
        str(a.id),
        str(b.id),
    }  # endpoint finds what the value-compare can't


async def test_invalid_label_is_422(client):
    resp = await client.get("/api/calls", params={"label": "Nonexistent"})
    assert resp.status_code == 422


async def test_label_filter_member_name_form_is_rejected(client, session_factory):
    # The stored representation ('sales_inquiry') is NOT the API contract; only the value is.
    await _insert(session_factory, label=CallLabel.sales_inquiry)
    resp = await client.get("/api/calls", params={"label": "sales_inquiry"})
    assert resp.status_code == 422


# --- duration range -------------------------------------------------------------------------


async def test_duration_min_max_range(client, session_factory):
    short = await _insert(session_factory, duration_seconds=30)
    mid = await _insert(session_factory, duration_seconds=120)
    long = await _insert(session_factory, duration_seconds=600)
    await _insert(session_factory, duration_seconds=None)  # NULL excluded from a range

    resp = await client.get("/api/calls", params={"min_duration": 60, "max_duration": 300})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(mid.id)}

    resp = await client.get("/api/calls", params={"min_duration": 60})
    assert _ids(resp.json()) == {str(mid.id), str(long.id)}

    resp = await client.get("/api/calls", params={"max_duration": 60})
    assert _ids(resp.json()) == {str(short.id)}


async def test_min_duration_greater_than_max_is_422(client):
    resp = await client.get("/api/calls", params={"min_duration": 500, "max_duration": 100})
    assert resp.status_code == 422


async def test_negative_duration_is_422(client):
    resp = await client.get("/api/calls", params={"min_duration": -1})
    assert resp.status_code == 422


# --- combining filters (AND) ----------------------------------------------------------------


async def test_filters_are_anded_together(client, session_factory):
    match = await _insert(
        session_factory,
        caller_name="García López",
        status=CallStatus.success,
        label=CallLabel.support,
    )
    await _insert(
        session_factory,
        caller_name="García López",
        status=CallStatus.failed,
        label=CallLabel.support,
    )  # wrong status
    await _insert(
        session_factory,
        caller_name="Other Person",
        status=CallStatus.success,
        label=CallLabel.support,
    )  # wrong name

    resp = await client.get(
        "/api/calls",
        params={"caller_name": "garcía", "status": "success", "label": "Support"},
    )
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(match.id)}


# --- sorting --------------------------------------------------------------------------------


async def test_sort_by_duration_asc_and_desc(client, session_factory):
    a = await _insert(session_factory, duration_seconds=30)
    b = await _insert(session_factory, duration_seconds=120)
    c = await _insert(session_factory, duration_seconds=600)

    resp = await client.get("/api/calls", params={"sort_by": "duration_seconds", "sort_dir": "asc"})
    order = [row["id"] for row in resp.json()["data"] if row["duration_seconds"] is not None]
    assert order == [str(a.id), str(b.id), str(c.id)]

    resp = await client.get(
        "/api/calls", params={"sort_by": "duration_seconds", "sort_dir": "desc"}
    )
    order = [row["id"] for row in resp.json()["data"] if row["duration_seconds"] is not None]
    assert order == [str(c.id), str(b.id), str(a.id)]


async def test_invalid_sort_field_is_422(client):
    # Whitelisted enum: internal/non-existent columns are rejected, never interpolated into SQL.
    for bad in ["raw_transcript", "notes", "id", "1; DROP TABLE calls", "summary"]:
        resp = await client.get("/api/calls", params={"sort_by": bad})
        assert resp.status_code == 422, f"{bad!r} -> {resp.status_code}"


async def test_sort_is_stable_across_pages_with_tiebreaker(client, session_factory):
    # All rows share the same primary sort key (status), so the `id` tiebreaker alone decides the
    # order. We give the rows explicit ids and insert them in a SHUFFLED order, so storage/insertion
    # order differs from id order. Then the only way the pages come back in id order is the
    # tiebreaker — drop it and this test fails (insertion order != id order).
    ids = [uuid.UUID(int=n) for n in range(1, 11)]
    insertion_order = [ids[i] for i in (7, 2, 9, 0, 5, 3, 8, 1, 6, 4)]  # not sorted
    for call_id in insertion_order:
        await _insert(session_factory, id=call_id, status=CallStatus.success, duration_seconds=100)

    pages = []
    for page in (1, 2):
        resp = await client.get(
            "/api/calls",
            params={"sort_by": "status", "sort_dir": "asc", "page": page, "page_size": 5},
        )
        assert resp.status_code == 200
        pages.append([row["id"] for row in resp.json()["data"]])

    assert set(pages[0]) & set(pages[1]) == set()  # disjoint: no row on both pages
    expected = [str(i) for i in ids]  # id-ascending == the tiebreaker order
    assert pages[0] + pages[1] == expected  # exact order, not just the union


# --- counts + N+1 ---------------------------------------------------------------------------


async def test_counts_reflect_non_status_filters_broken_down_by_status(client, session_factory):
    await _insert(session_factory, caller_name="García A", status=CallStatus.success)
    await _insert(session_factory, caller_name="García B", status=CallStatus.success)
    await _insert(session_factory, caller_name="García C", status=CallStatus.failed)
    await _insert(session_factory, caller_name="Unrelated", status=CallStatus.success)

    resp = await client.get("/api/calls", params={"caller_name": "garcía"})
    body = resp.json()
    assert body["counts"] == {"in_progress": 0, "success": 2, "failed": 1}
    assert body["total"] == 3  # all García rows, every status


async def test_total_respects_status_filter_counts_do_not(client, session_factory):
    await _insert(session_factory, caller_name="García A", status=CallStatus.success)
    await _insert(session_factory, caller_name="García B", status=CallStatus.failed)

    resp = await client.get("/api/calls", params={"caller_name": "garcía", "status": "success"})
    body = resp.json()
    # counts ignore the status tab (so the tabs can show what's available); total respects it.
    assert body["counts"] == {"in_progress": 0, "success": 1, "failed": 1}
    assert body["total"] == 1
    assert all(row["status"] == "success" for row in body["data"])


async def test_list_query_count_is_independent_of_row_count(client, session_factory, count_queries):
    # No N+1: the number of SQL statements for a list call must not grow with the number of rows.
    await _insert(session_factory, caller_name="A")
    before = count_queries["n"]
    await client.get("/api/calls")
    small = count_queries["n"] - before

    for i in range(30):
        await _insert(session_factory, caller_name=f"bulk {i}")
    before = count_queries["n"]
    await client.get("/api/calls")
    large = count_queries["n"] - before

    assert small == large, f"query count grew with rows: {small} -> {large} (N+1)"
    assert large <= 3, f"expected a bounded number of queries, got {large}"


# --- pagination interplay -------------------------------------------------------------------


async def test_pagination_with_filter_applied(client, session_factory):
    for i in range(25):
        await _insert(session_factory, caller_name=f"García {i:02d}", duration_seconds=i)

    resp = await client.get(
        "/api/calls",
        params={
            "caller_name": "garcía",
            "sort_by": "duration_seconds",
            "sort_dir": "asc",
            "page": 2,
            "page_size": 10,
        },
    )
    body = resp.json()
    assert body["total"] == 25
    assert body["total_pages"] == 3
    assert body["page"] == 2
    durations = [row["duration_seconds"] for row in body["data"]]
    assert durations == list(range(10, 20))  # second page of the ascending sort


# --- hardening: case folding, boundaries, bounded inputs ------------------------------------


async def test_caller_name_search_is_unicode_case_insensitive(client, session_factory):
    # SQLite's built-in lower() folds ASCII only; we register a Unicode-aware lower() so an
    # uppercase accented name matches its lowercase query and vice versa (real seed: "María García").
    upper = await _insert(session_factory, caller_name="GARCÍA")
    mixed = await _insert(session_factory, caller_name="María García")
    await _insert(session_factory, caller_name="Derek Owens")

    resp = await client.get("/api/calls", params={"caller_name": "garcía"})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(upper.id), str(mixed.id)}

    resp = await client.get("/api/calls", params={"caller_name": "MARÍA"})
    assert _ids(resp.json()) == {str(mixed.id)}


async def test_whitespace_only_caller_name_is_ignored(client, session_factory):
    a = await _insert(session_factory, caller_name="Someone")
    b = await _insert(session_factory, caller_name=None)

    resp = await client.get("/api/calls", params={"caller_name": "   "})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(a.id), str(b.id)}  # blanks degrade to "no filter", not 0 rows


async def test_non_digit_phone_term_is_ignored(client, session_factory):
    a = await _insert(session_factory, phone_number="+1 (555) 201-4832")
    b = await _insert(session_factory, phone_number="+44 20 7946 0812")

    resp = await client.get("/api/calls", params={"phone": "abc"})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(a.id), str(b.id)}  # nothing to match on -> filter skipped


async def test_duration_equal_bound_is_inclusive(client, session_factory):
    exact = await _insert(session_factory, duration_seconds=120)
    await _insert(session_factory, duration_seconds=119)
    await _insert(session_factory, duration_seconds=121)

    resp = await client.get("/api/calls", params={"min_duration": 120, "max_duration": 120})
    assert resp.status_code == 200
    assert _ids(resp.json()) == {str(exact.id)}  # >= and <= are inclusive at the single point


async def test_oversized_duration_is_422_not_500(client):
    # A value beyond the DB integer range must be rejected at the boundary, never reach the driver.
    for params in ({"min_duration": 10**30}, {"max_duration": 2**63}):
        resp = await client.get("/api/calls", params=params)
        assert resp.status_code == 422, f"{params} -> {resp.status_code}"


async def test_oversized_page_is_422_not_500(client):
    # A huge page would overflow OFFSET = (page-1)*page_size; bounded so it 422s instead of 500s.
    resp = await client.get("/api/calls", params={"page": 10**18, "page_size": 100})
    assert resp.status_code == 422


async def test_sort_places_nulls_last_in_both_directions(client, session_factory):
    has_value = await _insert(session_factory, duration_seconds=100)
    no_value = await _insert(session_factory, duration_seconds=None)

    for direction in ("asc", "desc"):
        resp = await client.get(
            "/api/calls", params={"sort_by": "duration_seconds", "sort_dir": direction}
        )
        order = [row["id"] for row in resp.json()["data"]]
        assert order == [str(has_value.id), str(no_value.id)], f"NULL not last for {direction}"
