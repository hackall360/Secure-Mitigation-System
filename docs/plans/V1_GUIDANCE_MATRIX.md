# V1.0.0 Guidance State Matrix — live telemetry ledger

> LAW 2 source: `.jcode/briefs/2026-10-30-v1-guidance-directive.md`.
> Baseline (2026-10-29 21:30 -0700): `python3 .jcode/tools/dev.py check` GREEN —
> 557 passed. Branch: `feature/v1-guidance-matrix`.
> Latest Gate 1 (2026-10-29 21:53 -0700): **599 passed**, ruff clean/format
> clean, harness PASS, `--list-targets` OK (4 entries incl. binary_argv_echo).
> Gate 2 live Docker: `dev.py offline-scan` 3/3 verified (pre=0/post=1,
> cleanup clean); vault recall proven KNOWN_ARCHETYPE post-commit;
> `--mcp` STDIO 5-tool handshake proven; `--version` 0.7.0;
> `--list-targets` 4 entries.
> Gate 3 browser: `ui_scan.py node_query_sink --offline` Chrome + Firefox
> both render the result card (pre 0/1, regression passed, cleanup clean);
> `fact-compression` + `fact-vault` + `sweep-passes` IDs confirmed in DOM.
> Invariants held: air-gapped sandbox untouched; fail-closed; session cleanup.

## Subsystem A — Dynamic Context Compression Engine

- Where It Is ($S_{current}$): `ScanUsage`/`CallUsage` token+cost accounting in
  `modules/core/pricing.py`; per-call usage rendered in `static/app.js`
  (`usage-tokens`); `RED_SUMMARY_SYSTEM_PROMPT` evidence compressor in
  `modules/services/project_agents.py:73`. No middleware, no dedup/pruning
  pass, no persisted dictionary, no raw/compressed/saved/ratio fields.
- Where It Isn't ($\Delta$): `modules/shared/sms_compress.py` middleware with
  `compress_context()` (structural dedup + semantic pruning + token-budget
  prioritization, sink/flow sentence preservation); persisted stats/dictionary
  (`~/.cache` or repo-local state dir); `CompressionStats`
  (raw/compressed/saved/ratio) on `ScanResult`/`SweepScanResult`/receipts;
  CLI JSON + TUI + Web UI badges.
- Corrective Action Vector:
  1. RED test `tests/test_compression.py` (pre/post token counts, sink preservation).
  2. `modules/shared/sms_compress.py` implementation (stdlib only).
  3. Wire into `workflow.py` + `sweep.py` + `agents.py` call path; attach stats.
  4. Surface: `--scan` JSON facts, TUI facts, dashboard badge + report JSON.
  5. Gate 1 + Gate 2 + Gate 3.
- Verification Gate Status: `[ ] UNVERIFIED`

## Subsystem B — Role-Separated Encrypted Threat & Mitigation Vault

- Where It Is ($S_{current}$): nothing — no vault module, no key handling, no
  fingerprinting. `grep -ril vault` returns zero source hits.
- Where It Isn't ($\Delta$): `modules/intel/sms_vault.py` — three namespaces
  (RED/BLUE/GREEN), at-rest encryption with stdlib-only authenticated scheme
  (AES-GCM needs `cryptography`; venv lacks it → use HMAC-chained XOR-stream
  via `hashlib.sha256` in CTR-like construction? NO — wrong primitive.
  Decision: add `cryptography` to requirements + regenerate lock via dev.py,
  then use Fernet/AES-GCM; key file 0600, never committed/logged), sink
  fingerprint → KNOWN_ARCHETYPE/NOVEL_SURFACE query, commit-back on verified,
  `sms_query_vault_stats` redacted telemetry.
- Corrective Action Vector:
  1. RED test `tests/test_vault.py` (round-trip, namespaces, wrong-key failure, redaction).
  2. Dependency addition + `modules/intel/sms_vault.py`.
  3. Wire query into `workflow.py` pre-red + commit-back on verified; stats tool.
  4. Surface in CLI/TUI/UI badge.
  5. Gates 1–3.
- Verification Gate Status: `[ ] UNVERIFIED`

## Subsystem C — Three-Pass Comprehensive Pentester Sweep

- Where It Is ($S_{current}$): `modules/workflows/sweep.py` (319 lines:
  standard/deep/threat_actor passes, `SweepPassResult`/`SweepScanResult`,
  full red→probe→blue→regression→re-probe per pass);
  `modules/workflows/binary_sweep.py` (308 lines, same for binaries);
  `--sweep-passes` CLI flag (`main.py:1609`); `tests/test_sweep_passes.py`
  (258 lines); dashboard sweep rendering (`static/app.js:885`).
- Where It Isn't ($\Delta$): verify pass-3 prompt synthesis quality
  (threat-actor zero-day prompt in `modules/core/prompts.py`), dashboard
  pass-indicator element + TUI pass display, sweep metrics in report JSON.
  Likely small delta — confirm by reading + targeted tests.
- Corrective Action Vector:
  1. Audit prompts + UI pass indicator coverage; add RED tests for gaps.
  2. Fill gaps (prompt hardening, UI/TUI pass badges, report fields).
  3. Gates 1–3.
- Verification Gate Status: `[ ] UNVERIFIED`

## Subsystem D — Compiled Binary RE, Triage & Binary Patching

- Where It Is ($S_{current}$): `modules/services/binary_intake.py` (89 lines:
  ELF/Mach-O/PE magic validation, 8 MiB cap, contract);
  `modules/workflows/binary_sweep.py`; Dockerfile.binary; `/ws/binary`;
  `tests/test_binary_intake.py` (252 lines).
- Where It Isn't ($\Delta$): (a) in-sandbox structural telemetry extractor
  (symbol tables/disassembly/syscalls — via container-side script, host never
  executes); (b) Blue binary mitigation artifact path (harness-enforced rules /
  wrapper shim within size guards); (c) deterministic compiled binary fixture
  in `targets/` + registry entry runnable from `--scan`/`--tui`/Web UI.
- Corrective Action Vector:
  1. RED tests: telemetry extractor shape, mitigation artifact guards, fixture presence.
  2. `targets/binary_argv_echo/` C fixture (gcc available) + registry entry.
  3. Sandbox-side telemetry script + mitigation artifact synthesis.
  4. Wire `--scan`/`--tui`/dashboard fixture select.
  5. Live Docker proof + Gates 1–3.
- Verification Gate Status: `[ ] UNVERIFIED`

## Subsystem E — Library API + MCP Server

- Where It Is ($S_{current}$): `modules/services/mcp_bridge.py` (230 lines:
  `submit_code_snippet` only); `POST /mcp` JSON-RPC Streamable HTTP
  (`main.py:715`); `tests/test_mcp_server.py` (236 lines); `--mcp-snippet`
  CLI; `sms_cli.py` formatting helpers.
- Where It Isn't ($\Delta$): (a) documented first-class library entrypoint
  (`sms` package API: `scan_source`, `scan_binary`, `query_vault_stats`,
  `verify_receipt` returning Pydantic receipts); (b) MCP tools
  `sms_scan_source`, `sms_scan_binary`, `sms_query_vault_stats`,
  `sms_verify_receipt` on both `--mcp` STDIO and `/mcp` HTTP/SSE transports.
- Corrective Action Vector:
  1. RED tests for library API + 4 MCP tools (mocked Docker loop).
  2. `sms_api.py` (or `modules/services/sms_api.py`) + MCP tool registration.
  3. `--mcp` STDIO transport in `main.py`.
  4. Docs + Gates 1–3.
- Verification Gate Status: `[ ] UNVERIFIED`

## Subsystem F — Presentation, README Refactor, 3-Minute Demo

- Where It Is ($S_{current}$): `README.md` (hackathon edition, 0.6.0 badges,
  5-min demo); `docs/ARCHITECTURE.md` (241 lines); dashboard with
  modes/sweep/binary/mcp; TUI parity shipped (0.6.0).
- Where It Isn't ($\Delta$): executive-hook README rewrite (Mermaid V1
  architecture, Muse 90% note, spark/wonder economics, differentiation
  table, 3-min demo Parts 1+2); Web UI + TUI badges (pass indicator, vault
  recall, compression savings, binary fixture option); version bump per LAW 12.
- Corrective Action Vector:
  1. README rewrite + ARCHITECTURE backfill; dashboard/TUI badge wiring.
  2. Old-vs-new browser mapping (LAW 11) + `ui_scan.py` extension.
  3. LAW 12 bump + Gates 1–3.
- Verification Gate Status: `[ ] UNVERIFIED`

## Execution order (sequential, gates after each)

A → B → C → D → E → F. Regression halts forward progress (doctrine §0.4).
TODO states live in TODO.md section I.
