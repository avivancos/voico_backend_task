# ADR-0003 — Call notes

- **Status:** Accepted
- **Date:** 2026-06-13
- **Task:** Task 1 — Call Notes

## Context
Calls had no way to be annotated. Task 1 adds a free-text note that a user edits inline from the call
detail drawer. The questions worth deciding: the column shape and migration, the request contract for
"set vs clear", normalization, how the note relates to the public response, and how the UI applies the
edit without feeling laggy.

## Decision
- **Schema.** A nullable `notes TEXT` column on `calls`. **No index** — it is free text that is never
  filtered or sorted on, so an index would only cost writes. Migration `0002` is additive and nullable
  (a plain `ADD COLUMN` on upgrade; a batch `drop_column` on downgrade so SQLite can rebuild the table),
  and is exercised by the upgrade→downgrade→upgrade roundtrip test.
- **Request contract — required but nullable.** `PATCH /api/calls/{id}/notes` takes
  `UpdateCallNotesRequest{ notes: Optional[str] }` with the key **required** (an empty body `{}` is a
  422) but the value nullable. `{"notes": null}` (or a blank/whitespace string) **clears** the note;
  `{"notes": "..."}` sets it. The 2000-character cap is enforced by the request model (over-length → 422).
- **Normalization in the service.** Notes are Unicode-NFC-normalized and trimmed; `null`/empty/
  whitespace-only collapse to SQL `NULL`. So "no note" has exactly one representation.
- **`updated_at` is bumped by the writer.** The column has no DB-level `onupdate`; the notes writer sets
  `updated_at = now_utc()` explicitly (the single-clock convention from ADR-0002). Each future writer
  does the same.
- **Public field.** `notes` is added to the closed `CallResponse` (and therefore to the list payload —
  a cheap scalar, no N+1) and to the leak-guard's `PUBLIC_FIELDS`, so the contract test stays exact.
- **Frontend — optimistic with rollback.** The drawer shows the new note immediately, then reconciles
  with the server response and patches the calls-list cache; on failure it rolls back to the previous
  value and surfaces an error. The optimism/rollback lives in the submit handler (not React Query
  lifecycle callbacks) so the mutation's rejection is always awaited and handled.

## Alternatives considered
- **Optional body (`{}` means "no change").** Rejected: it makes "clear the note" impossible to express
  distinctly from "leave unchanged". Required-but-nullable gives both with no extra verb.
- **SQLModel `Field(max_length=...)` on a table model for the cap.** Rejected: length is a request
  concern; enforcing it on the Pydantic request model guarantees a 422 regardless of the DB type.
- **DB `onupdate=now` for `updated_at`.** Rejected: it hides the write and behaves inconsistently across
  bulk updates; explicit writer-set timestamps are predictable and testable with an injected clock.
- **Indexing `notes` / full-text search.** Rejected for this task: notes are not a query axis. If search
  over notes is ever needed, SQLite FTS5 is the upgrade path.

## Consequences
- Setting and clearing notes are both first-class and unambiguous; "no note" is always `NULL`.
- The note rides along in the existing list/detail responses with no extra query.
- Because `updated_at` is writer-set, any new mutation must remember to bump it — enforced by review and
  covered by a test that asserts the timestamp advances on a notes write.

## What we deliberately did NOT do
- No notes history/audit trail, no per-user attribution, no rich text — a single free-text field is the
  requirement. Multi-author history would be a separate table and ADR if the product needs it.
