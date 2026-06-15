# ADR-0007 — Webhook AI integration

- **Status:** Accepted
- **Date:** 2026-06-15
- **Task:** Task 4 — Webhook AI Integration

## Context
`POST /api/webhook/call` was a stub. It must (1) find a call by `call_id` and update its `status`,
`duration_seconds`, `raw_transcript` and `ended_at`, then (2) when the new status is terminal
(`success`/`failed`) and a transcript is present, call OpenAI (`gpt-4o-mini`) to produce a 2–3
sentence summary and classify the call into a `CallLabel`, storing both — and if OpenAI fails, log
and continue with `summary`/`label` left `null`.

This endpoint is **publicly reachable and unauthenticated**, and its transcript is **attacker-
controllable** text that we feed to an LLM. So beyond the happy path, the decisions worth recording
are: how we authenticate and de-replay the request, how an OpenAI failure is prevented from rolling
back the DB write, how untrusted transcript text is stopped from steering the model or the record,
how the `CallLabel` value/name duality is handled, and how all of it is tested without mocks.

## Decision
- **`Enricher` protocol + injected client (no mocks).** AI lives behind
  `app/modules/calls/enrichment.py:Enricher` (a `Protocol`). Production wires `OpenAIEnricher`, whose
  `AsyncOpenAI` client is itself constructor-injected. The router exposes it via the `get_enricher`
  dependency, so tests inject a recorded/fake enricher with `app.dependency_overrides` and the
  `OpenAIEnricher` itself is tested against a **recorded `chat.completions` response replayed at the
  HTTP boundary** (`httpx.MockTransport`) — the Python analogue of the frontend's MSW. We never
  monkeypatch the SDK or our own code, and still reach 100% line+branch coverage.
- **Update is idempotent; enrichment is guarded and self-healing.** Only fields that actually change
  are written, so a re-delivery does not re-stamp `updated_at` (the writer-set-timestamp convention
  from ADR-0002/0005). Enrichment runs only for a terminal call that has a transcript and is **not
  already summarized** (`summary is None`), so replays don't re-spend on OpenAI; a transient OpenAI
  failure (summary still null) is retried on the next delivery rather than being permanent.
- **Failure isolation: the `try/except` lives in the service, not the router.** The webhook is a
  request and commits through the router's `@session_manager`. If the OpenAI call raised there, the
  whole transaction — including the field update — would roll back. So `CallService.ingest_webhook`
  swallows enrichment errors itself and logs them; the field update always persists, `summary`/
  `label` stay `null`. This is the central correctness decision of the task.
- **Bounded enrichment latency.** Because enrichment runs inside the webhook request, the OpenAI
  client is built with a finite `timeout` (`OPENAI_TIMEOUT_SECONDS`, default 20s) and a capped
  `max_retries` (`OPENAI_MAX_RETRIES`, default 1) — worst case ~`timeout × (1 + retries)`, not the
  SDK's 600s default. A timeout is swallowed like any other enrichment failure (summary/label null),
  so a slow model can never hang the webhook indefinitely.
- **HMAC signature + replay window, opt-in via `WEBHOOK_SECRET`.** When the secret is **unset**, the
  webhook accepts unsigned requests — so the README's Swagger "Try it out" demo works out of the box.
  When the secret is **set**, every request must carry `X-Signature: sha256=<hex>` =
  HMAC-SHA256 over `"{X-Timestamp}.{raw_body}"` and an `X-Timestamp` (Unix seconds) within
  `WEBHOOK_TOLERANCE_SECONDS` (default 300) of now; otherwise it is **401**. The signature is taken
  over the **raw** body (read via `request.body()`, which Starlette caches so the Pydantic body still
  parses), compared with `hmac.compare_digest` (constant time). The timestamp is bound into the MAC
  (so it can't be tampered independently) and bounds replay. The clock is an injected dependency
  (`get_now`) so the window is tested deterministically.
- **Prompt-injection hardening (transcript = untrusted data).** Three layers: (1) the system prompt
  fixes the task and states the transcript is data to analyze, never instructions to obey, and the
  transcript is passed delimited inside `<transcript>…</transcript>`; (2) the model is constrained
  with a JSON-schema `response_format` whose `label` is the closed set of `CallLabel` values, so it
  cannot emit an out-of-enum label; (3) we still validate defensively — `_coerce_label` maps anything
  unexpected to `CallLabel.other` and the summary is length-capped. Authoritative fields (`status`,
  `duration_seconds`, …) come only from the validated payload, so transcript text like "set status to
  success" can change nothing.
- **`CallLabel` value/name duality.** The model returns a public *value* ("Sales inquiry");
  `_coerce_label` accepts the value, a case-folded value, or the member name (`sales_inquiry`) and the
  ORM stores the member, while the API serializes the value — round-tripping exactly as the existing
  filter does.
- **No schema change / no migration.** `summary`, `label`, `raw_transcript`, `ended_at` and
  `duration_seconds` already exist on the `Call` model from the scaffold; Task 4 only fills logic.

## Alternatives considered
- **Persisted `event_id` + dedup table for anti-replay.** Rejected: the documented payload has no
  event id, adding one widens the contract and a new table/migration. A signed timestamp window plus
  the naturally-idempotent update closes the replay vector without either.
- **`409 Conflict` on a duplicate delivery.** Rejected: the operation is idempotent (PUT-like), so
  returning the current resource with `200` is more useful to a retrying caller than an error.
- **Always-on signature.** Rejected as the default: it would break the README's unsigned Swagger
  demo. The posture is opt-in and becomes mandatory the moment a secret is configured.
- **`client.chat.completions.parse` (SDK structured-output helper).** Rejected: it raises on a
  schema mismatch, which would discard a good summary over a slightly-off label. Manual parse +
  `_coerce_label` degrades gracefully to `other` instead.
- **Monkeypatching the OpenAI SDK in tests.** Rejected by the testing contract; replaying a recorded
  response at the `httpx` transport boundary exercises the real client code instead.

## Consequences
- The webhook is correct under failure (update persists when OpenAI is down), cheap under replay (no
  re-enrichment, no re-stamp), and authenticated + replay-bounded when a secret is configured.
- Untrusted transcript text cannot change a call's status/label or escape the enum.
- AI is swappable: any object satisfying `Enricher` can replace `OpenAIEnricher` with no router
  change.

## What we deliberately did NOT do
- No retry/queue/outbox for failed enrichments beyond next-delivery retry — out of scope.
- No per-caller secrets / key rotation / nonce store — single `WEBHOOK_SECRET` is enough here.
- No streaming or multi-model fallback; one `gpt-4o-mini` call with structured output.
