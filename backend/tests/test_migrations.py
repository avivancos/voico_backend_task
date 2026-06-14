"""Migrations must be reversible: upgrade -> downgrade -> upgrade against a real SQLite file."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic(*args: str, db_url: str) -> subprocess.CompletedProcess:
    """Run Alembic via the running interpreter so it never depends on PATH."""
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_migration_roundtrip_is_reversible(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'roundtrip.sqlite3'}"

    up = _alembic("upgrade", "head", db_url=db_url)
    assert up.returncode == 0, up.stderr

    down = _alembic("downgrade", "base", db_url=db_url)
    assert down.returncode == 0, down.stderr

    up_again = _alembic("upgrade", "head", db_url=db_url)
    assert up_again.returncode == 0, up_again.stderr


def test_migrations_produce_the_model_schema(tmp_path):
    """A real ``alembic upgrade head`` must produce a ``calls`` table whose column SET matches the
    columns the SQLModel model declares (compared by name; not types/nullability).

    The fast harness builds the schema with ``metadata.create_all`` (from the models); this checks
    the migration chain agrees on which columns exist. It catches the class of bug where a model
    column is added with no migration: it builds fine via ``create_all`` (and passes the rest of
    the suite) yet is ABSENT on a fresh migrated database — the failure that silently breaks the
    notes feature on a clean DB.
    """
    import sqlite3

    from app.modules.calls.schema import Call

    db_file = tmp_path / "schema.sqlite3"
    up = _alembic("upgrade", "head", db_url=f"sqlite+aiosqlite:///{db_file}")
    assert up.returncode == 0, up.stderr

    conn = sqlite3.connect(db_file)
    try:
        migrated = {row[1] for row in conn.execute("PRAGMA table_info(calls)")}
    finally:
        conn.close()

    expected = set(Call.__table__.columns.keys())
    assert migrated == expected, (
        f"migration/model drift — only in migration: {sorted(migrated - expected)}; "
        f"only in model (missing a migration!): {sorted(expected - migrated)}"
    )
