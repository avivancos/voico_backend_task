# ADR-0002 — CORS and runtime security baseline

- **Status:** Accepted
- **Date:** 2026-06-13
- **Task:** Task 0 — Foundations

## Context
The scaffold ships `CORSMiddleware` with `allow_origins=["*"]` **together with**
`allow_credentials=True`. That combination is invalid per the CORS spec — browsers reject a wildcard
`Access-Control-Allow-Origin` on credentialed requests — and is an over-permissive default. The app
has no authentication and uses no cookies.

## Decision
- CORS origins are an explicit, env-configurable allow-list (`ALLOWED_ORIGINS`, default
  `http://localhost:5173`); never `*`.
- `allow_credentials=False` (no auth → not needed), which also removes the invalid wildcard +
  credentials combination.
- Methods and headers are scoped to what the app uses (`GET, POST, PATCH, OPTIONS`; `Content-Type`,
  `X-Signature`).
- Runtime DB baseline established here for later tasks: SQLite runs in **WAL** mode with a busy
  timeout (so the API and the Task 4 background worker can write concurrently), and a startup guard
  asserts **SQLite >= 3.35** (required for the `RETURNING` claim in Task 4).
- A single `now_utc()` helper (naive UTC) replaces the deprecated `datetime.utcnow()`.

## Alternatives considered
- **Keep `allow_credentials=True` with an explicit allow-list** — valid, but unnecessary without
  auth and a larger surface. Revisit only if cookie auth is added.
- **Reflect-any-origin regex** — rejected as effectively a wildcard.

## Consequences
- Cross-origin requests work from the configured frontend; unknown origins are rejected (covered by
  a preflight test).
- Pointing at a real frontend domain is a one-line env change.

## What we deliberately did NOT do
- No auth, rate limiting, or webhook signature yet — webhook HMAC signing lands with Task 4; rate
  limiting is out of scope for this exercise.
