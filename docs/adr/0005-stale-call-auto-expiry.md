# ADR-0005 — Stale call auto-expiry

- **Status:** Accepted
- **Date:** 2026-06-14
- **Task:** Task 3 — Stale Call Auto-Expiry

## Context
Calls move to `success`/`failed` via the webhook (Task 4). A call whose closing webhook never arrives
would sit in `in_progress` forever. Task 3 adds a background job that, while the server is up, sweeps
those stragglers to `failed`. The decisions worth recording: where the logic lives so it stays
testable, how the sweep is expressed (batch vs row-by-row), what exactly it changes, how it stays
idempotent, and how the scheduler behaves at boot, on failure, and under tests.

## Decision
- **One injectable, set-based sweep.** `CallRepository.expire_stale(now, threshold_minutes)` issues a
  single `UPDATE calls SET status='failed', updated_at=:now WHERE status='in_progress' AND started_at <
  :cutoff` (run on the session's Core connection), where `cutoff = now - threshold`. It returns the
  affected row count. No per-row loop — the cost is one round-trip regardless of how many rows match,
  proven by a statement-count test.
- **Strict threshold.** "in_progress for **more than** 30 minutes" → `started_at < now - threshold`
  (strict `<`): a call exactly at the threshold is not yet expired. Tested at the 29/31-minute boundary.
- **Only `status` and `updated_at` change.** `updated_at` is set to the sweep's `now` (the single
  writer-set-timestamp convention from ADR-0002). `ended_at` is deliberately left `NULL`: the call never
  actually ended — we only gave up on it — so fabricating an end time would be dishonest. `started_at`
  and the transcript are untouched.
- **Idempotent by construction.** The `WHERE status='in_progress'` clause means a second sweep changes
  nothing (the rows are now `failed`). Already-terminal calls are never re-failed, however old. Both are
  tested.
- **The clock is injected.** The repository/service/`run_expiry_once` take `now` explicitly (defaulting
  to `app/core/time.py:now_utc`), so every test pins time — no `sleep`, no wall-clock flakiness.
- **`run_expiry_once` owns its session and commits.** Background jobs are not requests, so they bypass
  the router's `@session_manager`: `run_expiry_once` opens its own session, runs the sweep, commits, and
  logs the count ("marked N call(s) failed").
- **Scheduler in the app lifespan, sleep-first.** A `lifespan` task loops `sleep(interval)` → sweep,
  forever, cancelled on shutdown. Sleeping *before* the first sweep means booting the app never triggers
  an immediate run, which also keeps the test suite (which boots the app via its lifespan) from ever
  running a real sweep. A failed sweep is logged and the loop continues — one bad run must not stop the
  scheduler.
- **Env-tunable, no code edits to test.** `EXPIRY_INTERVAL_MINUTES` (10) and `EXPIRY_THRESHOLD_MINUTES`
  (30) live in `app/core/config.py` and `.env.example`. They are floats, so a value like `0.1` exercises
  the job in seconds.
- **No schema change.** Expiry reuses the existing `status`/`updated_at` columns, so there is no new
  column and no migration.

## Alternatives considered
- **Row-by-row: load in_progress calls, set each, save.** Rejected: N statements and a race window per
  row; the set-based UPDATE is one atomic statement.
- **A new `expired_at` column to distinguish auto-failed from webhook-failed.** Rejected for this task:
  the requirement is just `failed`, nothing reads such a flag yet, and an auto-expired call (no
  transcript) is already distinguishable and won't be AI-enriched in Task 4. Add it with a migration if
  a product need appears.
- **External scheduler (cron / APScheduler / Celery beat).** Rejected: the requirement is "while the
  server is up"; an in-process asyncio loop needs no extra service or broker and is trivially testable.
- **Sweep on boot, then every interval.** Rejected: a boot sweep would fire inside every test's lifespan
  and force-fail seed data; sleeping first is both correct (give the app a grace period) and test-safe.

## Consequences
- Calls cannot get stuck in `in_progress` indefinitely; the sweep is bounded, atomic, and idempotent.
- The interval/threshold are tunable from the environment, so the behavior can be demoed in seconds.
- Because `updated_at` is writer-set and `ended_at` stays NULL, an auto-expired call is recognizable
  (failed, no `ended_at`, no transcript) — useful when Task 4's webhook later reconciles late arrivals.

## What we deliberately did NOT do
- No retry/reopen logic, no per-call configurable timeout, no notification on expiry — out of scope.
- No persistence of "why" a call failed beyond `status` — the webhook path and the expiry path both land
  on `failed`; distinguishing them is a future `expired_at`/`failure_reason` decision, not this task's.
