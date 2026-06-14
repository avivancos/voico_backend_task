# ADR-0004 — Advanced filtering & search

- **Status:** Accepted
- **Date:** 2026-06-14
- **Task:** Task 2 — Advanced Filtering & Search

## Context
`GET /api/calls` only filtered by status. Task 2 adds combinable filters (partial caller name, partial
phone, exact label, duration range), whitelisted column sorting, and keeps the status counts the
dashboard shows. The decisions worth recording: how `label` is matched (it has a value/name mismatch
that silently returns zero rows if done naively), how sorting stays injection-proof, how text/phone
matching behaves, and how the counts are computed without an N+1.

## Decision
- **`label` is matched by the enum, never by a raw string.** The column stores the enum **member name**
  (`sales_inquiry`), while the public API speaks the enum **value** (`"Sales inquiry"`). Verified
  empirically: the runtime column type is SQLAlchemy `Enum`, so `Call.label == CallLabel.sales_inquiry`
  compiles to `label = 'sales_inquiry'` and matches what is stored. The query param is typed
  `Optional[CallLabel]`, so FastAPI accepts the value, the ORM binds the name, and an unknown label is a
  422. The contract is **symmetric**: the response returns `"Sales inquiry"` and the filter accepts
  `"Sales inquiry"` — the frontend round-trips a row's `label` with no translation. A regression test
  asserts the filter returns the right non-empty set (the naive `== value` bug would return 0 rows).
- **Sorting is whitelisted via an enum.** `sort_by` is a closed `CallSortField`; the repository maps it
  to an ORM column through a total dict, so the sort column is **never** built from arbitrary input
  (no string interpolation into SQL). `sort_dir` is `{asc, desc}`. Default is `created_at desc`, and a
  stable `id` tiebreaker is always appended so equal sort keys never reorder across pages, and the
  primary sort is `NULLS LAST` so rows missing the sort value go to the bottom deterministically across
  backends. Internal/audit columns (`raw_transcript`, `notes`, the Task-4 queue columns) are
  deliberately not in the whitelist.
- **Text matching escapes LIKE metacharacters.** `caller_name` uses case-insensitive `ILIKE %term%`
  with `%`, `_` and `\` escaped, so a user typing `%` matches a literal percent, not "everything".
  A blank/whitespace-only term degrades to "no filter" (it is stripped first).
- **Case-insensitivity is Unicode-aware.** `ILIKE` compiles to `lower(col) LIKE lower(?)`, and
  SQLite's built-in `lower()` folds **ASCII only** — so `MARÍA` would silently miss the seeded
  `María García`. We register a Unicode-aware `lower()` SQLite function (Python `str.lower`) on the
  `Engine` connect event, so the app and the test harness share identical folding. A regression test
  stores `GARCÍA`/`María García` and queries the opposite case.
- **Phone search is digit-normalized on both sides.** The stored number and the query are reduced to
  bare digits, so `5552014832` matches `+1 (555) 201-4832`. A non-digit-only term degrades to "no phone
  filter" rather than matching nothing surprisingly.
- **Duration range, NULL-aware.** `min_duration`/`max_duration` are inclusive bounds (`>= / <=`); rows
  with a NULL duration are naturally excluded from a bounded range. An inverted range
  (`min > max`) is a 422 (a cross-field check the declarative validators can't express), and negative
  bounds are rejected by `ge=0`.
- **Integer inputs are bounded so a 4xx never degrades to a 5xx.** An oversized `min/max_duration` or
  `page` would overflow the driver's 64-bit integer (or the computed `OFFSET`) and surface as a 500.
  Sane caps (`le=86400` on durations, `le=1_000_000` on `page`) reject such input with 422 at the HTTP
  boundary, before it reaches the database. Tests pin the oversized→422 behavior.
- **Counts in a single `GROUP BY` (kills the scaffold N+1).** The scaffold issued four COUNT queries.
  One `SELECT status, COUNT(*) ... GROUP BY status` over the **content filters** (everything except
  `status`) yields `counts`; `total` is derived from it. So `counts` ignores the status tab — the tabs
  stay informative as you switch between them — while `total` and the returned page **do** respect
  `status`. A test asserts the statement count for a list call is constant regardless of row count.
- **Indexes (`migration 0003`).** Additive, reversible indexes on `caller_name`, `duration_seconds`,
  `label` and `created_at` (status/phone were already indexed). The model declares the same
  `index=True`, so model and migration agree; the roundtrip and drift tests keep them honest. At ~100
  seed rows these are not yet necessary — they keep the new access patterns O(log n) as data grows.
- **Frontend.** Filters live in the URL query string as the single source of truth, so state is
  shareable and survives reload/back. Each active filter renders as a removable chip; column headers are
  clickable to cycle sort direction (one active sort); text inputs are debounced so the API request
  tracks the filters in real time without a request per keystroke.

## Alternatives considered
- **Filter `label` by `.value` string / a separate name-keyed param.** Rejected: comparing the raw value
  against the column returns 0 rows, and a name-keyed param would be asymmetric with the response. Typing
  the param as the enum is correct and keeps the value/name duality inside the ORM where it belongs.
- **`getattr(Call, sort_by)` for dynamic sort.** Rejected: it would expose internal columns and invites
  injection/attribute mistakes. An explicit whitelist is the security and clarity win.
- **Counts that ignore all filters (scaffold behavior) or that also respect status.** Rejected the first
  (the cards would ignore an active search); rejected the second (switching status tabs would make the
  other tabs' availability invisible). Filter-aware-except-status is the most useful and is one query.
- **Component state (not URL) for filters.** Rejected: the URL as source of truth makes filters
  shareable and reload-safe and removes a duplicate state source.

## Consequences
- All filters are optional and AND-combine; the label filter is provably non-empty against real seed data.
- Sorting cannot be used to reach non-public columns or to inject SQL; pagination is deterministic.
- The list endpoint runs a bounded number of queries (aggregate + page) irrespective of table size.
- New sortable/filterable columns must be added to the whitelist/inputs deliberately — a safe default.

## What we deliberately did NOT do
- No full-text search, fuzzy matching, or relevance ranking — exact/partial/range is the requirement.
- No cursor pagination — offset pagination with a stable tiebreaker is correct at this scale; cursors are
  the upgrade path if deep pagination over large data becomes a need.
