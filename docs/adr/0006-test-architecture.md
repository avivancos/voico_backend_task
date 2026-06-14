# ADR-0006 — Test architecture

- **Status:** Accepted
- **Date:** 2026-06-14
- **Task:** Cross-cutting — testing strategy

## Context
The suites had grown organically: four near-identical insert helpers, no tests for the scheduler
loop/lifespan (only the one-shot sweep), an unused `hypothesis` dependency, the frontend mocking our
own `api.ts` (a mock of our own code), and no coverage gate. This ADR fixes the harness as a whole so
correctness is *proven*, not asserted by spot checks.

## Decision
- **No mocks, ever, of our own code.** Backend tests run the real ASGI app against real SQLite
  (in-memory `StaticPool`, dependency-overridden session); the OpenAI call (Task 4) will sit behind an
  `Enricher` protocol with a recorded fixture. On the frontend the **network boundary** is faked with
  **MSW** so the real `api.ts`/axios (base-URL composition + param serialization + parsing) runs —
  `vi.mock` of our own modules is only used for component-level UI units, never the API layer.
- **100% backend coverage (line + branch), CI-enforced** via `--cov-fail-under=100`. Reaching it by
  faking collaborators is forbidden — only real code paths count. The few admissible exclusions are
  `# pragma: no cover` on genuinely unreachable bootstrap guards (an "impossible" SQLite-version check;
  the file-engine WAL hook that never fires under the in-memory test engine), each justified inline.
  Measuring the async request path requires **`concurrency = ["thread", "greenlet"]`** in coverage
  config: SQLAlchemy's async layer runs through greenlets, so without it request-handler code executes
  *untraced* and falsely reports as uncovered (this silently hid `repository.list_calls`).
- **One shared `make_call` fixture** (full Call defaults + `minutes_ago`/`now`) replaces the four
  per-file insert helpers; the frontend has a matching `makeCall`/`pageOf`/`renderWithProviders` in
  `src/test-utils.tsx`.
- **The scheduler is testable by dependency injection, not monkeypatching.** `expiry_scheduler` takes
  `session_factory`, `interval_seconds`, `threshold_minutes`, and an injectable `run_once`; the lifespan
  wires the real ones at the composition root. Tests drive the loop with a fake `run_once` + a tiny
  interval, covering lifespan start/cancel, cadence, failure-resilience, **and the sleep-first boot
  grace** — without touching module globals.
- **Property-based tests (Hypothesis) over pure functions only.** The LIKE-escaper, phone-digit
  normalizer, and an extracted `is_expired` predicate are exhaustively checked. DB-backed property
  tests are deliberately excluded (the async function-scoped fixture × `@given` friction outweighs the
  marginal value; the example-based DB tests already cover those paths).
- **Marker taxonomy** (`unit/integration/security/property/contract`) with `--strict-markers`, so any
  subset runs on its own and a typo fails fast.
- **Frontend coverage gate** (`@vitest/coverage-v8`, lines/statements ≥90, branches ≥85, functions
  ≥85 — functions sits lower because of inline UI callbacks).

## Alternatives considered
- **Monkeypatch module globals to test the loop** (what the strongest competitor does): rejected — DI
  is cleaner, tests the *real* lifespan wiring, and needs no global mutation.
- **DB-backed Hypothesis via the async client:** rejected — `@given` + a function-scoped async fixture
  triggers HealthCheck/state-leak; pure-only keeps it deterministic and friction-free.
- **Mutation testing as a CI gate:** rejected — too slow/flaky to block CI. Kept as an optional
  `make mutate` (scoped to `app/modules/calls/`) with a baseline score recorded in ENGINEERING.md.
- **`fast-check` for the URL round-trip:** rejected — `callsUrlState.test.ts` already encodes that
  property; a property lib for one round-trip is not worth the dependency.
- **A lower coverage bar (e.g. 90%):** rejected for the backend — 100% is reachable honestly here and
  it forces error branches (404s, rollbacks, the session guard) to be exercised, not assumed.

## Consequences
- Every backend line/branch is exercised by a real test; regressions that drop coverage fail CI.
- The scheduler loop, lifespan lifecycle, and failure handling are verified — closing the one gap where
  a competitor's tests were broader than ours.
- The real `api.ts` is exercised end-to-end (params + parsing) instead of being mocked away.
- New tests inherit one factory and one render helper; the four duplicated insert helpers are gone.

## What we deliberately did NOT do
- No DB-backed Hypothesis, no `fast-check`, no mutation gate in CI, no `vi.mock` of our own API layer.
- Frontend functions coverage is gated at 85% (not 100%) — inline UI callbacks make 100% UI-function
  coverage uneconomical; the meaningful logic (services, hooks, URL state, table/page behavior) is at
  or near 100%.
