# ADR-0000 — Engineering method: verification-first, TDD, contract-enforced

- **Status:** Accepted
- **Date:** 2026-06-13
- **Task:** Task 0 — Foundations

## Context
Correctness and engineering judgment are the bar for this project, including a live walkthrough of
the code. Confidence in any change must come from evidence that can be re-run on demand, not from
prose.

## Decision
Adopt a verification-first method:

- A single engineering contract for all contributors: [`/AGENTS.md`](../../AGENTS.md).
- TDD for behavioral logic (🔴 red → 🟢 green → 🔵 refactor).
- Zero mocks: real SQLite (WAL) and recorded fixtures for external services behind small protocols.
- Independent review of every change before it lands (correctness, security, test quality).
- One ADR per decision, including deliberate non-goals.
- CI runs the whole suite in a container; the app boots from an empty database via Docker.

## Alternatives considered
- **Code-after / manual testing only** — rejected: produces claims that cannot be re-verified.
- **Ad-hoc structure with no written contract** — rejected: inconsistent layering and review
  quality across changes.

## Consequences
- Higher up-front cost: Task 0 builds the harness, Docker, and CI before any feature — in exchange
  for fast, trustworthy iteration and a result that holds up under a live walkthrough.
- Every later task has a clear gate: red → green → refactor + ADR + OpenAPI docs + review.

## What we deliberately did NOT do
- No bespoke test framework and no heavyweight infra (Redis, Kubernetes). The harness is plain
  `pytest` / `vitest` + Docker Compose. Upgrade paths are recorded in the relevant per-task ADRs.
