# Session lessons — competition-lockdown closeout (2026-11-01/02)

Mechanical notes for the next session. Exact paths, symbols, commands, knobs.
Read this before touching the scan loop, Docker lifecycle, MCP busy paths, or the gate.

## 1. Gate (LAW 5)

- Command: `python3 .jcode/tools/dev.py check` (pytest + `ruff check` + `ruff format --check` + compileall + `node --check static/app.js` + fixture app.js + `test_harness.py` + `main.py --list-targets`).
- Baseline this session: 1030 passed + 1 skipped, All checks passed (final pre-merge run; one earlier run showed `1 failed, 1029 passed` with no FAILED block captured, then two consecutive full greens — treat as flake, re-run before touching code).
- After touching top-level imports: run `ruff check` until 3 consecutive greens (import-sort fix can flip-flop; merge duplicate `from x import (...)` blocks by hand).
- Browser proof needs the project venv: `.venv/bin/python .jcode/tools/ui_scan.py <target> --offline --browser firefox|chrome` (system python lacks `websockets`; Chrome needs `.venv/bin/python`, Firefox works on either). Dashboard shots go to explicit `--shot PATH`; default `reports/ui-*.json/png` in-repo are stale Oct-28 artifacts, not fresh evidence.

## 2. Scan loop (the money path)

- Entry: `execute_purple_workflow` (`library/workflows/workflow.py:323`) → `execute_sweep_scan` (`library/workflows/sweep.py:302`) for multi-pass; binary via `execute_binary_sweep`; projects via `execute_project_workflow` (`library/workflows/project_workflow.py:1212`).
- Verdict: ternary oracle — probe exit 0 = boundary reached (→ blue patch), 1 = holds, 2/other = inconclusive → `SandboxError`, never a fix (`workflow.py:440/517`, sweep `sweep.py:418`, binary `binary_sweep.py:263-310`, project fates at `project_workflow.py:1813-1831`).
- `verified` requires receipt + `cleanup_ok` (`ScanResult.success`, `workflow.py:320`).
- `cleanup_ok` starts True and flips False ONLY if `close()` raises — a run can report `cleanup=True` while daemon-side stragglers still show `Up` (see §3).
- `vault_committed` (`workflow.py:317`) records post-verified vault commit success; RED-only partial commit is a valid standalone state (no transaction).

## 3. Docker lifecycle (where the bodies are)

- One `DockerSandboxManager` per scan, `session_id = uuid4().hex`; tracked lists `containers/networks/images`; `close()` (`docker_manager.py:910`) removes reversed-containers → networks → images, prides itself idempotent, raises `SandboxError` with the session label on persistent failure.
- `replace_target` (`docker_manager.py:466`) and `replace_binary_harness` (`:608`): `keep_tracked=True` on transient `DockerException` so `close()` retries the reap; `NotFound`/clean still untrack.
- `_runtime` (`:396`) appends BEFORE `start()`; start failure stays tracked by design. Verifier containers self-remove in `run_isolated_verifier` finally (`:478+`).
- **Intermittent survivors are daemon-side, not a tracking bug**: instrumented 1/2/4-fixture runs all showed `tracked=1 net=1` at `close()` and converged; survivors appear across sequential runs with `cleanup_ok=True`. Never add more tracking — re-run `main.py --cleanup` (label-filtered `remove_stale_resources`) after proof batches. Session label is the ONLY valid attribution: `docker ps -a --filter label=purplebox.session=<id>` (wall clocks skew ~1h between shell and daemon — never correlate by time).
- Base images carry baked `purplebox.base=true`, inherited by session containers — filter operators on `purplebox.session`, never `purplebox.base` (ARCHITECTURE.md isolation note, F-05).
- Pre-existing residue reconciler: `main.py --cleanup` (removed 19+6 this session, verified 0/0).

## 4. Concurrency (busy contract)

- One global `asyncio.Lock` per app instance (`scan_lock`, `main.py:665`); single-server model (LAW 7 — one server owns the port).
- Atomic pattern on all 3 admission paths (WS `run_socket` ~:800, MCP scan branch ~:1233, MCP snippet branch ~:1372): re-check `locked()` immediately before `acquire()` with no awaits between (atomic in one event-loop step); loser gets `busy`+1013 (WS) or `-32001` (MCP). The old check-then-gap-then-acquire let two callers serialize instead of refusing (F-02, proven old `['A:ran','B:ran']` vs new `['A:ran','B:busy']`).
- `blocking()` (`library/shared/sms_async.py`) joins in-flight Docker via shield, then propagates cancel; `CancelledError` is `BaseException` (bypasses `except Exception`), so `finally` cleanup runs on cancel.

## 5. Config & secrets

- `load_config()` (`library/core/config.py:153`) reads ONLY: `META_MUSE_API_KEY/BASE_URL/RED_MODEL/BLUE_MODEL/TIMEOUT_SECONDS/MAX_TOKENS/REASONING_EFFORT`, `PURPLEBOX_RESEARCH/_SCANNERS`, `PURPLEBOX_VERIFIER_TIMEOUT_SECONDS`, `PURPLEBOX_INFERENCE_MODE`. Everything else (images, mem, cpu, network, docker-timeout, max-source-bytes) is validated but NOT env-settable — pinned dataclass defaults by design (audit refuted the "dead knobs" claim; only unknown-scanner swallowing was real and is fixed: unknown names now reach `validate()` → `ConfigurationError`).
- `.env` is git-ignored, owner-only 0600; `main.py` never loads it (zero dotenv refs — key lands via shell export; same for `serve_up`). Health reports `api_key_configured` presence, never the key.
- Profiles: model pairs in `library/core/profiles.py` (`apply_profile`, unknown → `ProfileError`); scan knobs in `library/core/scan_profiles.py`. `custom` preserves server models.

## 6. Provenance-critical details

- Symbol renames that break tests: `main.py` uses `SNIPPET_LANGUAGE_BY_SUFFIX as _SNIPPET_LANGUAGE_BY_SUFFIX` (canonical in `mcp_bridge.py`, C1); `tui.py` same. `vault_committed` on `ScanResult` survives redaction. `SCAN_REGISTRY_MAX_ENTRIES=128` FIFO (`mcp_bridge.py:85`). `KEV_CACHE_TTL_SECONDS=24h` (`research.py:370`).
- Test-file naming: `test_*_red.py` = LAW 9 lineage (failed first, then green). New this session: `test_config_dead_knobs_red`, `test_scan_surface_parity_red`, `test_ws_negatives_red`, `test_correctness_guards_red`, `test_correctness_parity_red`, `test_correctness_intake_red`, `test_correctness_lifecycle_red`, `test_resilience_remediation_red`, `test_recovery_convergence_red`, `test_sapre_assurance_red`, `test_guidance_subsystem_b_red`.
- Sub-agent spawn (D3): OMIT `model:` so the worker inherits this session's coordinator route; bare `model:"muse-spark-1.3-contributor"` is read as `claude:<id>` and refused (11 refusals 2026-11-01). Swarm infra itself is outside this repo — doc fix only.
- Live proofs this session: keyed chain `verified` ($0.19, receipt `e56cf5c2`); Chrome/Firefox cards with receipts + screenshots (`/tmp/chaos-*-proof.png`); project 2/2 PASS; SIGKILL drill converged; offline 4/4 `verified`.
