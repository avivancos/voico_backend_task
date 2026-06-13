#!/bin/sh
set -e

echo "[entrypoint] applying migrations..."
alembic upgrade head

echo "[entrypoint] seeding sample data (idempotent)..."
python scripts/seed.py || echo "[entrypoint] seed skipped"

echo "[entrypoint] starting API on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
