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

## How to verify a change

- `make test` and the `docker compose --profile test` run are green.
- CI is green on the pushed branch.
- The relevant ADR explains the decision and its trade-offs.
- New/changed endpoints are documented in OpenAPI (`/docs`) and the `docs/api/openapi.json`
  snapshot is regenerated.
