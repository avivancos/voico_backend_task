# Engineering Methodology

How this project is built. The full contract lives in [`/AGENTS.md`](../AGENTS.md); this document
explains the *why* and how to verify the result.

## Principles

1. **Verification-first.** Confidence comes from green, real tests and a green CI — not from prose.
   A claim in the docs is backed by a committed test, or it is not made.
2. **TDD.** Behavioral changes start with a failing test (🔴), then the minimal implementation to
   pass it (🟢), then refactor (🔵).
3. **No mocks.** External dependencies are tested for real: SQLite in WAL mode, OpenAI through an
   `Enricher` protocol backed by a recorded fixture. See
   [`AGENTS.md` → Testing contract](../AGENTS.md#testing-contract-non-negotiable).
4. **Decisions are recorded.** Every non-trivial decision gets an ADR under [`adr/`](./adr) —
   including what we deliberately did *not* build.
5. **Reviewed and owned.** Every change lands under the contracts in `AGENTS.md` and passes
   independent review (correctness, security, test quality); every line is owned and defensible.

## How to run

```bash
docker compose up           # app from an EMPTY db (migrations on start) → API :8000, UI :5173
make test                   # full suite in the sanctioned container (compose --profile test)
make lint type              # ruff + mypy (backend) + eslint + tsc (frontend)
```

## Test architecture

No mocks of our own code (see [ADR-0006](adr/0006-test-architecture.md)). Backend: real ASGI + real
SQLite. Frontend: the network boundary is faked with **MSW**, so the real `api.ts` runs.

- **Coverage is gated.** Backend `--cov-fail-under=100` (line + branch); frontend v8 thresholds
  (lines/statements ≥90, branches/functions ≥85). The backend config sets
  `concurrency = ["thread", "greenlet"]` — required to measure the async/greenlet request path.
- **Markers** (`unit`, `integration`, `security`, `property`, `contract`) run subsets, e.g.
  `uv --directory backend run pytest -m security`. `--strict-markers` rejects typos.
- **Shared factories:** one `make_call` fixture (backend) and `makeCall`/`pageOf`/`renderWithProviders`
  in `frontend/src/test-utils.tsx` — no per-file copies.
- **Property tests** (Hypothesis) cover the pure helpers (`_escape_like`, `_phone_digits`, `is_expired`).
- **Mutation testing** is informational, not a gate: `make mutate` runs `mutmut` over
  `app/modules/calls/`. Baseline score: _run `make mutate` and record the killed/total here._

## How to verify a change

- `make test` and the `docker compose --profile test` run are green.
- CI is green on the pushed branch.
- The relevant ADR explains the decision and its trade-offs.
- New/changed endpoints are documented in OpenAPI (`/docs`) and the `docs/api/openapi.json`
  snapshot is regenerated.
