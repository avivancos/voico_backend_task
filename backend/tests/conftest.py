"""Test harness: real SQLite (in-memory, StaticPool), real ASGI app, no mocks.

Each test gets a fresh schema built from the SQLModel metadata. The app's DB dependency is
overridden to use the per-test engine, and the app runs through its real lifespan via
``asgi-lifespan`` so background wiring is exercised the same way as in production.
"""

import os
from datetime import timedelta

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Run tests on pure defaults: disable the .env source BEFORE the app (and its Settings singleton) is
# imported below, so a developer's local backend/.env can never change a test outcome. CI already
# ships no .env; this makes local runs match it.
os.environ.setdefault("ENV_FILE", "")

import app.database.models  # noqa: E402, F401  (registers all ORM models on SQLModel.metadata)
from app.core.time import now_utc  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.calls.router import get_session  # noqa: E402
from app.modules.calls.schema import Call, CallStatus  # noqa: E402


@pytest_asyncio.fixture
async def engine():
    """A throwaway in-memory SQLite engine with the full schema created."""
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
def make_call(session_factory):
    """Insert a Call with sensible defaults and return it. Override any column via keyword; use
    ``minutes_ago`` (relative to ``now``, default the app clock) to place ``started_at``/``created_at``
    in the past. Replaces the per-file insert helpers so every test seeds calls the same way."""

    async def _make(*, minutes_ago=None, now=None, **overrides) -> Call:
        fields: dict = {"phone_number": "+1 (555) 000-0000", "status": CallStatus.success}
        fields.update(overrides)
        if minutes_ago is not None:
            timestamp = (now if now is not None else now_utc()) - timedelta(minutes=minutes_ago)
            fields.setdefault("started_at", timestamp)
            fields.setdefault("created_at", timestamp)
        async with session_factory() as session:
            call = Call(**fields)
            session.add(call)
            await session.commit()
            await session.refresh(call)
            return call

    return _make


@pytest_asyncio.fixture
async def client(engine, session_factory):
    """An httpx client wired to the real ASGI app, backed by the per-test engine."""

    async def _override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def count_queries(engine):
    """Count SQL statements executed on the engine — used to prove the absence of N+1 queries."""
    counter = {"n": 0}
    sync_engine = engine.sync_engine

    def _on_exec(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    event.listen(sync_engine, "before_cursor_execute", _on_exec)
    yield counter
    event.remove(sync_engine, "before_cursor_execute", _on_exec)
