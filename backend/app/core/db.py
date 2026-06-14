import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

# The enrichment-queue claim relies on UPDATE ... RETURNING, which requires SQLite >= 3.35.
if tuple(int(part) for part in sqlite3.sqlite_version.split(".")) < (3, 35):
    raise RuntimeError(f"SQLite >= 3.35 is required (found {sqlite3.sqlite_version}).")


def _unicode_lower(value: str | None) -> str | None:
    return value.lower() if value is not None else None


@event.listens_for(Engine, "connect")
def _register_sqlite_functions(dbapi_connection, connection_record):
    """Override SQLite's built-in ``lower()`` with a Unicode-aware one.

    Case-insensitive search compiles to ``lower(col) LIKE lower(?)``, and SQLite's native ``lower()``
    folds ASCII only — so an uppercase accented name (``MARÍA``) would silently fail to match its
    lowercase form. Python's ``str.lower`` folds Unicode. Registered on the ``Engine`` class (not a
    single engine) so the app, the test harness, and any tooling all get identical semantics.
    """
    if hasattr(dbapi_connection, "create_function"):
        dbapi_connection.create_function("lower", 1, _unicode_lower, deterministic=True)


engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Enable WAL + a busy timeout so the API and the background worker can write concurrently."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async_session = sessionmaker(  # type: ignore[call-overload]
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
