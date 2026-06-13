import sqlite3

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

# The enrichment-queue claim relies on UPDATE ... RETURNING, which requires SQLite >= 3.35.
if tuple(int(part) for part in sqlite3.sqlite_version.split(".")) < (3, 35):
    raise RuntimeError(f"SQLite >= 3.35 is required (found {sqlite3.sqlite_version}).")

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
