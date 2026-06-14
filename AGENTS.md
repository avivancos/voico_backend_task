# AGENTS.md — Engineering Contract

> Single source of truth for any contributor (human or AI agent) to this repository.
> Tool-specific files (`CLAUDE.md`, `.cursor/rules`, …) redirect here.

## Mission

Implement the Voico Calls Dashboard features at production grade. Every change is
contract-enforced, test-driven, reviewed, and documented. The bar is a submission that is correct,
secure, and defensible line-by-line — not just "works on my machine".

## Architecture (respect it — denoted from the existing codebase)

- **Modular monolith**: `app/modules/<domain>/{schema,router,repository,service,tasks}.py`.
- **Layering** (strict, one direction):
  - `router` — HTTP surface: validation, dependency injection, status codes. No business logic.
  - `service` — orchestration / use-cases.
  - `repository` — all DB access. No business rules.
  - `schema` — SQLModel table models + Pydantic request/response models.
- **Transactions**: the `@session_manager` decorator commits on success / rolls back on error **at
  the router level**. Services and repositories use `session.flush()` / `refresh()` and **never**
  call `commit()`. Background jobs own their own session and commit explicitly.
- **Async everywhere** (FastAPI + SQLModel async + aiosqlite).
- **Config** via `pydantic-settings` (`app/core/config.py`), environment-driven.
- **Migrations**: Alembic (async env). Every schema change ships a **reversible** migration.
- **Time**: one helper `app/core/time.py:now_utc()` (naive UTC). No `datetime.utcnow()`.

## Definition of Done (hard gates — a change is DONE only when ALL pass)

- [ ] `ruff check` + `ruff format --check` + `mypy` clean.
- [ ] Tests written **first** (TDD) and green: backend `pytest`, frontend `vitest`.
- [ ] CI green: lint + type + test + `docker compose --profile test`.
- [ ] App boots from an **empty** database via `docker compose up` (migrations on start). Never
      rely on a committed `db.sqlite3`.
- [ ] One ADR under `docs/adr/`.
- [ ] New/changed endpoints documented in OpenAPI (summary, description, tags, examples, error
      `responses`).

## Testing contract (non-negotiable)

- **TDD-first**: 🔴 red (failing behavioral test) → 🟢 green (minimal impl) → 🔵 refactor.
- **Zero mocks** of our own code or external dependencies. OpenAI is exercised through an
  `Enricher` protocol with a **recorded fixture** — never by monkeypatching the SDK. SQLite runs
  for real (WAL) in tests.
- **100% line + branch coverage is non-negotiable, achieved *without mocks*.** The backend gate is
  `--cov-fail-under=100` (CI-enforced); reaching it by faking collaborators is forbidden — cover real
  code paths with real tests (real SQLite, real ASGI). The only admissible exclusions are
  `# pragma: no cover` on genuinely-unreachable bootstrap guards (e.g. an "impossible" version check),
  each with a one-line justification — never to paper over untested logic. Note: measuring the async
  request path requires `concurrency = ["thread", "greenlet"]` in coverage config (SQLAlchemy's async
  layer runs through greenlets), else covered code falsely reports as uncovered.
- On the **frontend**, "no mocks of our own code" means the network boundary is mocked with **MSW**
  (the real `api.ts`/axios runs), never `vi.mock` of our own modules for the API layer; component
  tests keep a realistic coverage floor.
- **Inject the clock** (`now`) and any seeds — no `sleep`, no nondeterminism.
- Cover error branches (4xx/5xx, null, invalid enum), not only the happy path.
- Every feature ships **≥1 negative test** that a naive implementation would fail (concurrency,
  idempotency, injection, boundary).
- TDD scope: *first* for behavioral/domain logic; pragmatic (test-after/smoke) for pure infra
  (Docker/CI) and presentational UI.

## Invariants

**Architecture** — no logic in routers; no commits in services/repos; typed request/response
schemas (never a raw `dict`); dynamic sort is whitelisted via an enum (no string interpolation
into SQL).

**Security** — no secrets in images, logs, or git (only `.env.example` is committed); CORS is an
explicit env allowlist, never `*` + credentials; the webhook is validated, idempotent, and
HMAC-signed when a signing secret is configured.

**Public vs internal** — the public `CallResponse` is a closed model; internal columns
(queue/lease/attempts/error/hash, audit timestamps) are never serialized and never sortable.

## Workflow

Spec-driven, one task at a time: 🔴 write the failing test → 🟢 minimal implementation → 🔵
refactor → gates green → review → ADR + OpenAPI docs → **ask the human for the commit message** →
commit. One ADR per task; small, scoped commits.
