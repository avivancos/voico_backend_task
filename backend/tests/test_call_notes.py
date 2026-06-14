"""Task 1 — Call Notes: PATCH /api/calls/{id}/notes behavior against a real DB (no mocks).

The endpoint body is *required but nullable*: an absent ``notes`` key is a 422, while an explicit
``null`` (or blank/whitespace) clears the field. Notes are normalized (NFC + stripped) and every
successful write bumps ``updated_at``.
"""

import unicodedata
import uuid
from datetime import datetime

import pytest

from app.modules.calls.schema import Call, CallStatus

pytestmark = pytest.mark.integration


async def test_set_notes_strips_and_persists(client, make_call):
    call = await make_call()
    resp = await client.patch(
        f"/api/calls/{call.id}/notes", json={"notes": "  Follow up next week  "}
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Follow up next week"

    # Survives a re-read (actually committed, not just echoed back).
    got = await client.get(f"/api/calls/{call.id}")
    assert got.json()["notes"] == "Follow up next week"


async def test_set_notes_normalizes_to_nfc(client, make_call):
    call = await make_call()
    decomposed = "Café meeting"  # "e" + combining acute accent
    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": decomposed})
    assert resp.status_code == 200
    assert resp.json()["notes"] == unicodedata.normalize("NFC", decomposed) == "Café meeting"


async def test_clear_notes_with_explicit_null(client, make_call):
    call = await make_call(notes="something")
    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": None})
    assert resp.status_code == 200
    assert resp.json()["notes"] is None


async def test_blank_notes_normalize_to_null(client, make_call):
    call = await make_call(notes="something")
    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": "   "})
    assert resp.status_code == 200
    assert resp.json()["notes"] is None


async def test_missing_notes_field_is_422(client, make_call):
    call = await make_call()
    resp = await client.patch(f"/api/calls/{call.id}/notes", json={})
    assert resp.status_code == 422


async def test_notes_at_max_length_ok_but_over_is_422(client, make_call):
    call = await make_call()
    ok = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": "x" * 2000})
    assert ok.status_code == 200
    over = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": "x" * 2001})
    assert over.status_code == 422


async def test_patch_unknown_call_is_404(client):
    resp = await client.patch(f"/api/calls/{uuid.uuid4()}/notes", json={"notes": "hi"})
    assert resp.status_code == 404


async def test_setting_notes_advances_updated_at(client, make_call):
    old = datetime(2000, 1, 1, 0, 0, 0)
    call = await make_call(started_at=old, created_at=old, updated_at=old)
    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": "touch"})
    assert resp.status_code == 200
    assert datetime.fromisoformat(resp.json()["updated_at"]) > old


async def test_notes_present_in_list_payload(client, make_call):
    await make_call(notes="visible in list")
    resp = await client.get("/api/calls")
    assert resp.status_code == 200
    assert any(row.get("notes") == "visible in list" for row in resp.json()["data"])


async def test_setting_identical_note_is_noop_and_does_not_bump_updated_at(client, make_call):
    # A save that doesn't actually change the (normalized) note must NOT re-stamp updated_at.
    old = datetime(2000, 1, 1, 0, 0, 0)
    call = await make_call(notes="keep me", started_at=old, created_at=old, updated_at=old)
    # Same note, only differing by surrounding whitespace -> normalizes equal -> no-op.
    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": "  keep me  "})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "keep me"
    assert datetime.fromisoformat(resp.json()["updated_at"]) == old


async def test_notes_write_is_column_scoped_and_survives_concurrent_update(tmp_path):
    """Our notes write must touch ONLY notes + updated_at, so it cannot clobber a concurrent write
    to other columns (e.g. the Task 4 webhook setting status + summary).

    The discriminating assertion inspects the actual SQL our service emits and requires that the
    UPDATE writing ``notes`` names neither ``status`` nor ``summary`` — a full-row-write regression
    in ``update_notes``/``repository.update`` would fail it. We also confirm the concurrent write
    survives end-to-end. The write goes through the REAL service, not a hand-rolled session.
    This test intentionally builds its own file-backed WAL engine, so it does not use ``make_call``.
    (``updated_at`` is a shared last-writer-wins column and is intentionally not asserted.)
    """
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import SQLModel, select
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.core.time import now_utc
    from app.modules.calls.repository import CallRepository
    from app.modules.calls.service import CallService

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'concur.sqlite3'}",
        connect_args={"check_same_thread": False},
    )

    update_statements: list[str] = []

    @event.listens_for(engine.sync_engine, "connect")
    def _wal(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE"):
            update_statements.append(statement)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    new_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with new_session() as s:
        seed = Call(phone_number="+1 (555) 000-0000", status=CallStatus.in_progress)
        s.add(seed)
        await s.commit()
        await s.refresh(seed)
        cid = seed.id

    # A concurrent writer sets other columns (as the webhook would) and commits first.
    async with new_session() as sb:
        b = (await sb.exec(select(Call).where(Call.id == cid))).one()
        b.status = CallStatus.success
        b.summary = "enriched by webhook"
        b.updated_at = now_utc()
        await sb.commit()

    # Our service writes the note through its real code path.
    async with new_session() as sa:
        await CallService(CallRepository(sa)).update_notes(cid, "agent annotation")
        await sa.commit()

    # Discriminating: the UPDATE that wrote `notes` named ONLY notes/updated_at, never status/summary.
    notes_updates = [s for s in update_statements if "notes" in s.lower()]
    assert notes_updates, "expected an UPDATE writing notes"
    assert all("status" not in s.lower() and "summary" not in s.lower() for s in notes_updates), (
        f"notes write was not column-scoped: {notes_updates}"
    )

    # End-to-end: the concurrent status/summary write survived alongside the note.
    async with new_session() as s:
        final = (await s.exec(select(Call).where(Call.id == cid))).one()
        assert final.notes == "agent annotation"
        assert final.status == CallStatus.success
        assert final.summary == "enriched by webhook"

    await engine.dispose()
