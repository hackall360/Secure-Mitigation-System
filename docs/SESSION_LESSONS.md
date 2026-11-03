# Session lessons — competition-lockdown closeout (2026-11-01/02)

Mechanical notes for the next session. Exact paths, symbols, commands, knobs.
Read this before touching the scan loop, Docker lifecycle, MCP busy paths, or the gate.

## 1. Gate (LAW 5)

- Command: `python3 scripts/dev/dev.py check` (pytest + `ruff check` + `ruff format --check` + compileall + `node --check static/app.js` + fixture app.js + `test_harness.py` + `main.py --list-targets`).
- Baseline this session: 1030 passed + 1 skipped, All checks passed (final pre-merge run; one earlier run showed `1 failed, 1029 passed` with no FAILED block captured, then two consecutive full greens — treat as flake, re-run before touching code).
- After touching top-level imports: run `ruff check` until 3 consecutive greens (import-sort fix can flip-flop; merge duplicate `from x import (...)` blocks by hand).
- Browser proof needs the project venv: `.venv/bin/python scripts/dev/ui_scan.py <target> --offline --browser firefox|chrome` (system python lacks `websockets`; Chrome needs `.venv/bin/python`, Firefox works on either). Dashboard shots go to explicit `--shot PATH`; default `reports/ui-*.json/png` in-repo are stale Oct-28 artifacts, not fresh evidence.

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
- Sub-agent spawn (D3): OMIT `model:` so the worker inherits this session's coordinator route; a bare `model:"muse-spark-1.3-contributor"` is read as a different-provider request and refused (11 refusals 2026-11-01). Swarm infra itself is outside this repo — doc fix only.
- Live proofs this session: keyed chain `verified` ($0.19, receipt `e56cf5c2`); Chrome/Firefox cards with receipts + screenshots (`/tmp/chaos-*-proof.png`); project 2/2 PASS; SIGKILL drill converged; offline 4/4 `verified`.

## 7. Session arc 2026-11-02 → 11-03 (rubric audit, maximization waves, verification sweep, doc rig)

- **Rubric ledger** (`HACKATHON_RUBRIC_LEDGER.md`, root): Run #1 7.06/10 baseline (Stage 1 PASS, Upper Quartile) → Run #2 7.71 (+0.65: intake clone, spark-open, beats, driver, render, README, load-table) → Run #3 7.96 (+0.25: narration toggle, `--auto` schedule, assets). No video recorded/rendered anywhere (ban honored; `render_demo.sh` proven via `bash -n` + `--check` only). Scoring is evidence-anchored (LAW 4): open-weight config-only → 1.25 not 2.5, showcase standalone → partial credit, 4D capped without live run-through.
- **Gates this arc**: 1063+2 (sweep close) → 1084 → 1085 (bare-metal README fix) → 1303+2 (236-trap sweep) → 1315+2 (swarm W1-W3). Full gate = `python3 scripts/dev/dev.py check`. Flake `test_project_disconnect_...` eradicated (`except BaseException` + `finally` double-set, 30 s event wait + busy deadline-poll; 50/50 isolated). Pre-existing format dirt (`demo_driver.py`, `test_render_demo_red.py`) was ruff 0.16.7→0.17.3 drift — whitespace-only sync, tests re-green, never stack product work on it without noting.
- **New symbols**: `_ingest_repo_to_project` (`main.py:2030`, cloned-tree → 0700 stage → `detect_runtime` → `ProjectSpec`; TUI reuses via `main_mod`); `demo_driver.py --auto` (machine schedule `[{t, stage, stem, narration}]`, STAGE_META-validated, drift fail-closed); narration toggle (`demo.js` `narrationToggle`, defaults OFF, `/api/narration/<stem>` graceful-404); `docs/ASSETS.md` + `web/assets/` (title-card/thumbnail SVG, `onerror` fallback); `docs/DEMO_SCRIPT.md` 7 beats ≤180 s (BEATS 1:1 in `scenario.js`, test-pinned); `docs/OPEN_WEIGHT.md` (spark-open payload, provisional pricing); `docs/LOAD_TABLE.md` (measured timings + `/ws/system` stay-stub decision); `docs/SYSTEM_ARCHITECTURE_INDEX.md` (map-reduce, 8 partitions); `VERIFICATION_MATRIX.md` (14 partitions, per-file hashes, [ST]/[SL] log); `SWARM_WAVE_MATRIX.md` (wave ledger).
- **Tooling**: `scripts/dev/verify_cov.py` (stdlib `sys.monitoring` line coverage — no pytest-cov per LAW 10F; tracer is repo-path-bound, run from checkout root; `find library tests -name '*.pyc' -delete` after ANY in-place mutant experiment — stale bytecode shadows reverts, see TRAPS 2026-11-02 entry). Coverage honesty: line-cov for pure units; live Muse/Docker/browser stay gate-verified (`offline_scan`/`project_scan`/`ui_scan`), never line-covered; no 100%-everywhere claim.
- **Bare-metal proof** (TRAPS 2026-11-02): `git archive HEAD | docker exec tar -x` into `python:3.12-slim` + `dev.py setup` (stdlib fallback, 40 s) → imports OK → 5 fixtures → tags 128/128 → smoke 6/6 → 68 unit green. `--network none` breaks pip by design (air-gap covers the sandbox, not `pip install`). Slim has no `node` — README now lists Node.js (test-pinned).
- **Spawn discipline that kept failing**: writers kept editing the shared checkout instead of their worktree (4 violations this arc). Fix that worked: create the worktree FIRST, move the stray file into it, DM the agent the exact path. Verify with `git status` (shared tree) + `git -C <wt> status` before merging. Never `git stash` to inspect merged work (round-trip risk — verify with `git diff` instead).
- **README show-don't-tell refactor** (directive 2026-11-03T00:14Z, separate branch): 11-section blueprint + 4 gates (clarity, empirical truth+links, rubric coverage, legal/tests). Status at doc time: briefed, not started — do NOT conflate with this doc-only ship.
