# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
# Slice F recon: Meta Model API docs vs repo transport, prompt scope, pricing.
# READ-ONLY findings (2026-11-04, branch feature/slice-f-recon). No behavior changed.
# Live docs read this session: pricing-rate-limits, quickstart, models,
# api-reference, reasoning, structured-output, error-handling, authentication,
# protocols (choosing-an-API), protocols/chat-completions.

## 1. /chat/completions endpoint: streaming, parallelism, batch

Transport under test: `library/core/agents.py` `MetaMuseClient._request`
(ll.282-467) — one `httpx` non-streaming POST to `chat/completions` per
red/blue call, `response_format: {type: json_schema}` (ll.310-316), full body
buffered via `_read_capped` (1 MiB cap, ll.318-326), retry ladder
`RETRY_MAX_ATTEMPTS=4` (ll.165-171) on transient `(429, 502, 503, 504)`.

### 1a. Streaming (SSE) — SUPPORTED by API, NOT USED by transport (confirmed)

- Live doc: `protocols/chat-completions` section "Streaming": set
  `stream: true` in the JSON body; with raw HTTP also send
  `Accept: text/event-stream` and read `data: ` SSE lines until `[DONE]`
  (SDK: `stream=True`, iterate `chunk.choices[0].delta.content`).
- Same page: streaming "sidesteps the server-side non-streaming time limit"
  (non-streaming overlong run -> HTTP 504 `gateway_timeout`; streaming is
  exempt). Error-handling page adds mid-stream terminal events
  (`response.failed`, `error` with codes incl. `server_shutting_down`).
- Verdict vs repo: capability CONFIRMED on the endpoint, DELIBERATELY
  UNUSED by `_request` (no `stream` key in `_body`, ll.265-280). The name
  `client.stream` (l.329) is only httpx's response-reading API, not SSE.
  This is a coherent choice (schema-validated single JSON object per call),
  but the 504-avoidance benefit is left on the table for the longest
  generations (reasoning-heavy blue passes near the 300 s timeout).
- Exact wire record: `POST {base}/chat/completions`
  (`base` default `https://api.meta.ai/v1`),
  headers `Authorization: Bearer $MODEL_API_KEY` (+ `Content-Type:
  application/json`; `Accept: text/event-stream` only when streaming),
  body flags of interest: `model`, `messages[]` (roles user/assistant/
  developer/system/tool), `reasoning_effort`, `response_format`
  (`type: json_schema` + `json_schema: {name, schema}`), `max_tokens`
  (deprecated alias, still accepted) / `max_completion_tokens`,
  `temperature` (0-2), `top_p` ((0,1]), `stream` (bool), `n` (only 1;
  `n > 1` -> 400), `seed` (deprecated best-effort), `logprobs` (400 on
  Muse Spark), `prompt_cache_key` / `prompt_cache_retention`
  (`in_memory`|`24h`), `safety_identifier`, `tools`/`tool_choice`.
  NOT on this endpoint: `background`, `text.format`, `store`,
  `previous_response_id`, `include: [reasoning.encrypted_content]`,
  `reasoning.summary`, web-search grounding (`web_search_options` -> 400;
  Responses-only tool), `frequency_penalty`/`presence_penalty`
  (unsupported), `stop` (400 on reasoning models), `modalities`, `audio`.

### 1b. Parallel requests — NO server-side batch fan-out; limits are per-team RPM/TPM

- Live docs list NO batch endpoint for text models. "Parallelism" on this
  API = concurrent plain requests against per-team, per-model budgets
  (pricing-rate-limits page): RPM 3000 / TPM 4,000,000 for
  muse-wonder-1.0, muse-spark-1.3/1.2/1.1; contributor variants
  (`-contributor`) RPM 150 / TPM 3,000,000; limits are per TEAM (every key
  on the team shares one bucket), each model has its own bucket.
  Additional headers on token-based responses: `x-ratelimit-limit-tokens`,
  `x-ratelimit-remaining-tokens`, `x-ratelimit-limit-requests`,
  `x-ratelimit-remaining-requests` (read before reacting to 429).
- `n > 1` (server-side parallel sampling) is explicitly rejected (HTTP
  400): "Only n=1 is supported". Tool-call parallelism mentioned in the
  model pages (Wonder "delegates to sub-agents, calls tools in parallel")
  is model-internal agentic behavior, not a request flag the harness can set.
- Verdict vs repo: repo issues strictly SEQUENTIAL `_request` calls (one
  red, then blue, per cycle; sweeps are sequential passes) — never near
  the 3000/150 RPM ceilings in normal scans. The transport's `Retry-After`
  honor + capped backoff (ll.359-367) matches the documented retry
  strategy (exponential backoff + jitter, honor `Retry-After`). No change
  needed; parallel fan-out would only matter for throughput work the
  harness does not do.

### 1c. Batch APIs — NONE for text models (confirmed absent)

- The API reference resource list is exhaustive for this surface:
  Responses (`POST /v1/responses` + retrieve/delete/cancel/count tokens),
  Chat Completions (`POST /v1/chat/completions`), Messages
  (`POST /v1/messages`), Files, Models (`GET /v1/models`), Status
  (`GET /v1/status`), Images, Voice. There is NO `/v1/batches`,
  bulk-submit, or file-based batch queue for Muse text models. The only
  async shape is `background: true` on the RESPONSES API (600 submissions/
  min/team; body cap 1 MiB) — Chat Completions has no equivalent flag.
- Verdict vs repo: nothing to adopt. Any future throughput work stays
  client-side concurrency under the RPM/TPM budgets above.

### 1d. Adjacent flags the transport deliberately differs on (traps recorded)

- `temperature: 0.1` is sent when no `reasoning_effort` is set
  (agents.py l.279); live docs tune Muse Spark at default 1.0 ("performs
  best there ... prefer clearer instructions over lowering temperature").
  Scaffold choice is intentional determinism for schema-valid JSON; keep.
- Body uses deprecated `max_tokens` (l.274); live docs: still accepted
  alias for `max_completion_tokens`. Keep (compat), note drift.
- `system` role used for prompts (l.271); live docs: `system` accepted
  for OpenAI compat, merged at same level as `developer`; "Prefer
  developer". Behaviorally equivalent; keep `system` (compat), note drift.
- `reasoning_effort` values accepted by config (`minimal..max`, config.py
  l.147) vs doc table (`none/minimal/low/medium/high/xhigh`): live
  reasoning page documents `max` for muse-wonder-1.0 and muse-spark-1.3
  but NOT for `muse-spark-1.3-contributor` (returns 400 territory with
  max). The repo default red model IS the contributor variant — setting
  effort `max` on the default red model risks HTTP 400. Pinned by test.

## 2. Prompt audit: generic-cybersecurity posture (report only, no rewrites)

Audited all 8 prompts in `library/core/prompts.py` (254 lines).

VERDICT: genuinely generic-cybersecurity, not input-sanitization-only.
Evidence: 5 red sweep prompts cover distinct postures — standard
input-boundary (RED_TEAM_SYSTEM_PROMPT l.4), deep edge-case/type-coercion/
encoding-layer sweep (RED_DEEP_SWEEP_SYSTEM_PROMPT l.84), threat-actor
logic-abuse sweep (RED_THREAT_ACTOR_SYSTEM_PROMPT l.118), multi-step chain
sweep requiring two DISPARATE classes fused in one payload with a literal
`# --- Link B ---` marker (RED_CHAIN_SYSTEM_PROMPT ll.153-201), and a
coverage sweep over five classes the boundary passes miss — SECRETS,
DEPENDENCIES, CRYPTO, AUTH, CONFIG (RED_COVERAGE_SWEEP_SYSTEM_PROMPT
ll.203-254, probe shapes per class ll.209-233 + LAW 4 no-echo rule
ll.214-216). Blue prompt authorizes the full generic fix vocabulary
(validation, casting, allowlists, escaping, parameterization, config
hardening, ll.39-40).

Remaining narrow assumptions (report only — DO NOT rewrite per brief):

1. prompts.py:4,84 — role noun "input-boundary auditor" on the two main
   red prompts (deep/threat/chain/coverage prompts already use broader
   nouns: "deep-sweep", "threat-actor sweep", "chain-sweep", "coverage").
2. prompts.py:20-21,104-105,139-140,194-195 — verdict noun "the specific
   unsanitized boundary" (coverage prompt ll.250-251 already uses the
   generic "the class-specific weakness ... observed live").
3. prompts.py:34 — blue role noun "input sanitizer" (body ll.39-49 is
   generic; noun is narrower than the authorized vocabulary).
4. prompts.py:30-31,114-115,149-150,199-200 (red x4) + 48-49 (blue) —
   MySQL `/my.cnf` three-directive carve-outs (bind-address/local-infile/
   secure-file-priv) embedded in every red/blue prompt. Fixture-specific
   escape hatch inside ostensibly generic prompts; only MySQL gets one
   (no Postgres/SQLite/Mongo equivalent).
5. prompts.py:39-40 — blue authorized-vocabulary list has no explicit
   authN/authZ-permission-check, crypto-primitive, or secrets-removal
   wording (coverage prompt hunts those classes red-side; blue close-out
   wording stays sanitization-framed).
6. prompts.py:41 — "Prefer an exact allowlist" steers even crypto/auth
   findings toward allowlist framing.
7. Research prompts (ll.52-82) are correctly scope-free (patterns + CWE
   hints + queries only, never payloads) — no narrow assumptions found.

## 3. Pricing / rate limits vs `library/core/pricing.py`

Live source: `pricing-rate-limits` page (read 2026-11-04). pricing.py header
cites the same page (read 2026-10-28). Comparison per 1M tokens
(cached input / input / output USD):

| model | pricing.py | live docs | match |
|---|---|---|---|
| muse-wonder-1.0 | 0.20 / 4.00 / 20.00 | Standard 0.20 / 4.00 / 20.00; Contributor N/A | EXACT |
| muse-spark-1.3/1.2/1.1 (standard) | 0.15 / 1.25 / 4.25 | Standard 0.15 / 1.25 / 4.25 | EXACT |
| muse-spark-1.3-contributor / -1.2-contributor | 0.002 / 0.10 / 0.20 | Contributor 0.002 / 0.10 / 0.20 | EXACT |
| meta-models/muse-spark-open(-1026) | 0.006 / 0.30 / 0.60 | NO partner rate card (open-weight; not served by api.meta.ai) | PROVISIONAL (flagged in code + docs/OPEN_WEIGHT.md; unchanged) |

Rate limits (live, per team per model): standard text models 3000 RPM /
4,000,000 TPM; contributor variants 150 RPM / 3,000,000 TPM; background
Responses submissions 600/min/team. Web-search grounding surcharge
($2.50/1K queries) exists but the harness never invokes web_search
(Chat Completions would 400 it) — no accounting gap. Reasoning tokens
billed as output (live + pricing.py agree). No drift on any priced row.

## 4. Files touched (this worktree only; no behavior changes)

- `docs/plans/SLICE_F_RECON.md` (this file) — findings.
- `tests/test_slice_f_recon_pins.py` (new) — 9 doc-claim pins (stream flag
  absent, sequential transport, pricing exactness, provisional open rows,
  rate-limit constants documented, max-effort contributor trap, deprecated
  max_tokens alias, system-role compat, prompt noun inventory).
- `docs/TRAPS.md` — 2 appended entries (SSE-name trap, max-effort
  contributor trap). No other source files touched.

## 5. What remains / follow-ups (NOT done — out of read-only scope)

- Optional transport follow-ups (needs behavior-change brief, NOT this
  slice): consider `Accept: text/event-stream` + `stream: true` path for
  the longest blue generations (504 avoidance); consider `developer` role
  and `max_completion_tokens` rename; consider per-call `prompt_cache_key`.
- Optional prompt follow-ups (needs rewrite brief): nouns in items 1-3
  above; MySQL carve-out generalization; blue vocabulary extension.
- Provisional open-weight rates still await a partner (Baseten/Modal) card.
- Live keyed proof of any of the above was out of scope (keyless recon).
