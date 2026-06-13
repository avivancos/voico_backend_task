# ADR-0001 — Docker, Compose, and CI foundations

- **Status:** Accepted
- **Date:** 2026-06-13
- **Task:** Task 0 — Foundations

## Context
The scaffold ships no reproducible run environment, no continuous integration, and no test harness.
"Works on my machine" is not enough: the reviewer must be able to run the app and the tests with one
command, and every change must be gated automatically.

## Decision
- **Docker images.** Backend is a multi-stage image (deps resolved with `uv`, runtime as a non-root
  user, `HEALTHCHECK` on `/health`). Its entrypoint runs `alembic upgrade head` then an idempotent
  seed, so the app **boots from an empty database** and never depends on a committed `db.sqlite3`.
  Frontend is built and served as static files by nginx (SPA fallback).
- **Compose.** `compose.yaml` runs backend + frontend; secrets are never inline (`OPENAI_API_KEY`
  comes from the environment, `./backend/.env` is optional). A `test` profile runs the backend and
  frontend suites inside the images (the sanctioned test runner).
- **CI.** GitHub Actions runs three jobs on every push/PR: backend (`ruff` + `ruff format --check` +
  `mypy` + `pytest` + OpenAPI-snapshot-up-to-date), frontend (`eslint` + `tsc`/build + `vitest`), and
  docker (the `test` profile + a boot-from-empty-DB smoke).
- **Pinned runtime.** Python is pinned to 3.12 (matching the image and tooling targets); `greenlet`
  is declared explicitly rather than relying on a platform-conditional transitive dependency.
- **OpenAPI as an artifact.** `docs/api/openapi.json` is exported from the app and diff-checked in CI
  so the documented contract cannot silently drift from the code.

## Alternatives considered
- **Local-only dev (no Docker).** Rejected: not reproducible; hides "boots from zero" bugs.
- **A running database service (Postgres) in Compose.** Rejected for this exercise: SQLite is the
  chosen store; a broker/DB service would add deployment weight with no benefit here.

## Consequences
- One command (`docker compose up`) brings up a working, seeded stack; one command (`make test` /
  `docker compose --profile test`) runs every suite the same way locally and in CI.
- Fixing the scaffold's broken ESLint setup (no flat config) makes the frontend lint gate real.

## What we deliberately did NOT do
- No production orchestration (Kubernetes), no image registry/publish step, no multi-arch builds —
  out of scope for a take-home. The Compose + CI setup is the upgrade path's starting point.
