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
