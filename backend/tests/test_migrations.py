"""Migrations are reversible and faithful to the model — verified against a real SQLite file.

A migration that only ``upgrade``s is half-built: it cannot be rolled back in production. These tests
hold the chain to a higher bar than "upgrade exits 0":

- the full up→down→up roundtrip reproduces a **byte-identical schema** (not just a zero exit code);
- **every** migration is reversible **in isolation** (down one step, up one step), so a single broken
  ``downgrade`` can't hide behind a working neighbor;
- ``downgrade base`` actually removes the schema (a no-op downgrade would pass a naive roundtrip);
- the migrated schema has **no autogenerate drift** against the SQLModel metadata (``alembic check``),
  i.e. columns, types, indexes and constraints all match the model — the check that catches a model
  column added without a migration, which builds fine via ``create_all`` yet is absent on a real DB.

All of this runs Alembic in a subprocess against a throwaway SQLite file, exactly as production boots.
"""

import os
import sqlite3
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


def _revision_count(db_url: str) -> int:
    """Number of migrations in the chain (each `alembic history` line is one revision edge)."""
    hist = _alembic("history", db_url=db_url)
    assert hist.returncode == 0, hist.stderr
    return sum(1 for line in hist.stdout.splitlines() if "->" in line)


def _schema_snapshot(db_file: Path) -> list[tuple[str, str, str]]:
    """Canonical DDL of every app table and index (excludes SQLite internals + alembic_version)."""
    conn = sqlite3.connect(db_file)
    try:
        return conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' AND name != 'alembic_version' "
            "ORDER BY type, name"
        ).fetchall()
    finally:
        conn.close()


def test_full_schema_roundtrip_is_identical(tmp_path):
    db_file = tmp_path / "roundtrip.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    assert _alembic("upgrade", "head", db_url=db_url).returncode == 0
    before = _schema_snapshot(db_file)
    assert any(name == "calls" for _type, name, _sql in before), "upgrade head must create `calls`"

    down = _alembic("downgrade", "base", db_url=db_url)
    assert down.returncode == 0, down.stderr
    # A real downgrade removes the schema; a no-op downgrade would slip through a naive roundtrip.
    assert all(name != "calls" for _type, name, _sql in _schema_snapshot(db_file)), (
        "downgrade base must drop `calls`"
    )

    assert _alembic("upgrade", "head", db_url=db_url).returncode == 0
    after = _schema_snapshot(db_file)

    assert before == after, f"schema changed across a down/up roundtrip:\n{before}\n!=\n{after}"


def test_each_migration_is_individually_reversible(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'stepwise.sqlite3'}"
    steps = _revision_count(db_url)
    assert steps >= 1

    assert _alembic("upgrade", "head", db_url=db_url).returncode == 0
    # Walk down one revision at a time: every single `downgrade` must succeed on its own.
    for i in range(steps):
        down = _alembic("downgrade", "-1", db_url=db_url)
        assert down.returncode == 0, f"downgrade step {i} failed: {down.stderr}"
    # ...and back up one revision at a time.
    for i in range(steps):
        up = _alembic("upgrade", "+1", db_url=db_url)
        assert up.returncode == 0, f"upgrade step {i} failed: {up.stderr}"


def test_no_autogenerate_drift_against_model(tmp_path):
    """`alembic check` must find nothing to generate — the migrated DB equals the SQLModel metadata
    (columns, types, indexes, constraints), the strongest 'migrations match the model' guarantee."""
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'drift.sqlite3'}"
    assert _alembic("upgrade", "head", db_url=db_url).returncode == 0

    check = _alembic("check", db_url=db_url)
    assert check.returncode == 0, (
        f"autogenerate drift between migrations and model:\n{check.stdout}\n{check.stderr}"
    )


def test_migrations_produce_the_model_schema(tmp_path):
    """The migrated ``calls`` column SET matches the SQLModel columns — with a crisp diff message.

    Complements ``alembic check`` (which also covers types/indexes) by naming exactly which column
    drifted: the failure mode where a model column is added with no migration builds fine via
    ``create_all`` yet is ABSENT on a freshly migrated database.
    """
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
