# System Architecture Index — Secure Mitigation System v0.14.0

> Map-reduce audit, 2026-11-02 (`feature/architecture-index`). Eight partition
> auditors (core, workflows, intel+shared, services+tags, surfaces, webui+scripts,
> sandbox+targets+showcase, tests+docs+tools) reported per-partition artifacts;
> every claim below is traceable to a file + symbol verified on this tree.
> LAW 4: no exploit material, no secrets, no prompt text reproduced.

The loop in one paragraph: a red-team Muse agent reads a target and writes a
probe that tries to cross an input boundary; the probe runs in a locked-down
Docker container (exit 0 = reached, 1 = held, 2 = inconclusive); a blue-team
Muse agent writes a ≤60-line fix; trusted normal-input checks re-run on both
original and fixed code. Only a 0→1 flip with unchanged normal behavior is
`verified`, with a `VerdictReceipt` (fix SHA-256 + exact Docker exits).

## Core Systems

### `library/core/` — engine room: Muse transport, prompts, Docker, guards, config

- **Responsibility:** everything the verdict rests on — model calls, sandbox
  lifecycle, patch validation, pricing, profiles, fixture registry. Upstream:
  `PurpleBoxConfig` env. Downstream: all six workflows, CLI/TUI/Web/MCP.
- **`agents.py` — `MetaMuseClient`**
  - `run_red_team_analysis` / `run_blue_team_sanitizer`: red/blue inference
    with bounded 2-try retry, jittered backoff (`_retry_delay_seconds`,
    `_parse_retry_after`), `json_schema` wire, LAW-4 redaction.
  - Models: `RedTeamFinding`, `BlueTeamPatch`, `RedResearchDigest`,
    `BlueResearchDigest`; `_schema_for`, `_extract_json_object`;
    `CallUsage` cost accounting per call.
  - Red default `muse-spark-1.3-contributor`, blue `muse-wonder-1.0`;
    `meta-models/muse-spark-open(-1026)` accepted with provisional pricing.
- **`docker_manager.py` — `DockerSandboxManager`** (36 defs): per-session
  containers/snapshots/networks, `network_mode="none"`, non-root, capped
  CPU/RAM/PIDs, read-only roots; `get_archive` tar streaming (never `docker cp`
  on tmpfs); deterministic cleanup even on cancel/disconnect.
- **`config.py` — `PurpleBoxConfig`**: `red_team_model`, `blue_team_model`,
  `meta_base_url` (api.meta.ai + `.baseten.co`/`.modal.run` suffixes),
  `validate()` regex (`muse-spark/wonder` + `meta-models/muse-spark-open`);
  `load_config()` from env; `inference_mode` local/hosted gate.
- **`prompts.py`**: 7 system prompts — `RED_TEAM`, `BLUE_TEAM`,
  `RED_RESEARCH`/`BLUE_RESEARCH` (research-only sidecars), `RED_DEEP_SWEEP`
  (pass 2), `RED_THREAT_ACTOR` (pass 3), `RED_CHAIN` (pass 4); Greenhouse
  builder prompt lives in `demo_gen.py`.
- **`patches.py`**: ≤60-line guard, protected-line enforcement, exact
  allowlists; `checks.py`: trusted normal-input regression gates.
- **`registry.py`**: 5 fixtures (`node_query_sink`, `node_chain_link`,
  `php_command_sink`, `mysql_insecure_conf`, `binary_argv_echo`) with CWE,
  entry, sink, fix metadata; `scan_profiles.py` (extra_light→heavy cycles);
  `profiles.py` (economy/balanced/quality model splits);
  `pricing.py` per-token table incl. provisional spark-open rows.
- **`project_models.py` — `ProjectSpec`** (frozen pydantic): local `Path`
  (symlink-guard), image/command/test_command/contract, cycles 1–20,
  agents 1–12, context budgets; scan-profile derivation.
- **`personas.py`**: voice-safe chatter lines (220-char server-built);
  `version.py`: `APP_VERSION` single source (0.14.0).

### `library/workflows/` — the six verification loops

- **Responsibility:** orchestrate red→probe→Docker→blue→re-verify per target
  shape; emit granular progress; fail closed. Upstream: core transport +
  sandbox + intel. Downstream: `cli_runner`, sockets, TUI dispatch.
- **`workflow.py` — `execute_purple_workflow`**: single-finding loop
  (compress → vault recall → baseline → one red/blue cycle → regression +
  re-probe → receipt); `ScanResult`, `VerdictReceipt`,
  `build_verdict_receipt`, `redact_fixture_result_for_user`.
- **`sweep.py` — `execute_sweep_scan`**: 5-pass ladder (standard → deep →
  threat-actor → chain → coverage); `SweepScanResult`, `ChainLink`, vault-status
  classification, unified 2-link chain probes (`_chain_link_probes`).
- **`deep_scan.py`**: edge/encoding/coercion/truncation handling for pass 2.
- **`project_workflow.py` — `execute_project_workflow`**: up-to-20
  evidence-gated cycles on a local project; `ProjectWorkflowInput`,
  `ExecutionEvidence`, `SnapshotVerification`, mutation/property/repeat
  gates, `CycleReceipt`, `ProjectSandbox` protocol, consent enforcement.
- **`binary_sweep.py`**: ELF/Mach-O/PE path (`file`/`strings`/`readelf`,
  `reject:` rules) — binary analog of patch verification.
- **`cve_workflow.py`**: CVE triage with reachability scoring, KEV/EPSS
  topping, NVD + offline modes.

### `library/intel/` — keyless threat intel (grounding only, never verdicts)

- **Responsibility:** pace-capped, size-capped host-only fetches (OSV, CIRCL,
  GitHub Advisory, EPSS, KEV, NVD); research sidecars return queries +
  patterns, never findings. Docker evidence alone decides verdicts.
- **`research.py`**: `ResearchRecord`, `osv_lookup`, `circl_lookup`,
  `ghsa_lookup_by_cve/search`, `epss_score`, `kev_lookup`, `cve_records`,
  `web_notes`, `research_for_sink`, `intel_for_demo` (Greenhouse grounding).
- **`intel_search.py`**: `nvd_search/lookup`, `summarize_nvd_record/search`,
  `osv_lookup_by_cve`.
- **`scanner_binaries.py`**: Trivy/Grype/OSV-Scanner/Dependency-Check
  runners + report parsers → `ScannerRecord`; `available()` guards.
- **`scanner_dtrack.py`**: Dependency-Track BOM build + submission
  (`build_bom`, `configured`).
- **`sms_vault.py` — encrypted memory**: `VaultStore`
  (Fernet blobs, `load_or_create_key`, `encrypt_blob/decrypt_blob`,
  `fingerprint_source`, namespaced records, `query_vault`); prior-patch
  replay cuts fresh investigations to one retry cycle.

## User Interfaces

### Entry surfaces — `main.py` + `tui.py` + `sms_cli.py` + `modules/` shim

- **Responsibility:** five synced surfaces (CLI, TUI, Web UI, MCP, Python
  library) per LAW 8 — no orphaned backend. Upstream: workflows + services.
- **`main.py`** (62 defs): `build_parser` (flags `--scan/--sweep-passes/--project/--binary-target/--ai-demo/--build-brief/--ingest-repo/--commit-hash/--cve-scan/--mcp-snippet/--serve/--port/--observability-mode/...`);
  `cli_runner` (ingest→`_ingest_repo_to_project` staging clone→project path);
  `run_demo_build` + `ai_demo_runner` (Greenhouse); `execute_mcp_snippet_scan`;
  `mcp_stdio_runner`; `binary_sweep_runner`; `write_run_report`
  (0600/0700 perms); FastAPI app — `GET /api/health` (only health route),
  `GET /api/targets`, `POST /mcp` (6 tools), websockets
  `/ws/combat/{target}` `/ws/project` `/ws/demo` `/ws/binary`
  `/ws/system` (explicit fail-closed invalid stub, proposed endpoint).
- **`tui.py`** (42 defs): 8 modes
  (`fixture/sweep/mcp/binary/project/ingest/demo/cve`), `TuiState`,
  `render_panes`, `apply_action`/`parse_key`, `queue_emit`/`drain_queue`,
  LAW-4 `redact_event_text`, `_dispatch_core` per-mode backends,
  `_project_spec_from_state`, `_ingest_repo_to_project` clone path in ingest.
- **`sms_cli.py`**: non-interactive presentation — tables/JSON for scan
  reports (`capabilities_text`, config load/merge, color, `Spinner`).
- **`modules/`**: alias shim (`modules.x.y` → canonical `library.x.y`).

### `web/` dashboard v3 + `scripts/` drivers

- **Responsibility:** cinematic presenter + console + setup switches + replay
  rig; stdlib HUD drivers. Served at `/web/*`; no inline styles (CSP
  `default-src 'self'`).
- Pages: `index.html` (Start), `demo-setup.html`/`prod-setup.html`
  switches, `demo.html` (cinematic presenter: `demo.js` — SpiderGraph,
  StageBar, CommsFeed, Terminal, HexStream, narrator captions),
  `console.html` (live radial map + scoreboard), `visualizer.html`.
- `js/`: `core/` (handoff, lenses, palette incl. `STAGE_META`
  sandbox/baseline/analysis/probe/patch/regression/cleanup, version),
  `engine/` (graph, kit, layout, lens, loop, render-*),
  `model/` (extract, parse-source/binary/system, topo-builder/profiles/showcase),
  `options/` (compile, form, schema incl. `proposed` system endpoint),
  `pages/` (console, demo, setup-demo), `stream/` (`scenario.js` —
  fixture VOCAB + timed `BEATS` 1:1 with `docs/DEMO_SCRIPT.md`),
  `ui/` hud components; `css/` tokens/forms/pages; `tools/`.
- **`scripts/demo_driver.py`**: beat-file machine driver
  (`--dry-run/--live/--check-beats`), doc↔BEATS 1:1 guard, no audio render.
- **`scripts/mcp_client_demo.py`**: stdlib urllib HUD driver for
  `submit_code_snippet` POST /mcp.

## Database / Persistence

- **Encrypted vault** (`library/intel/sms_vault.py`): the only database —
  file-backed Fernet store under `PURPLEBOX_VAULT_DIR`, key file 0600,
  namespaced (`KNOWN_ARCHETYPE`/`NOVEL_SURFACE`/…), content-fingerprinted
  IDs, recall stats via `sms_query_vault_stats`. No SQL, no server.
- **Run reports** (`main.write_run_report`): per-run dirs with `report.json`
  (0600) + markdown summary + `candidate.patch`; `logs/<signal>/<aspect>.jsonl`
  observability (stdlib-only, dev ~10x).
- **`.env`**: owner-only key store, never committed, never loaded by the app
  (exported by `dev.py serve-up` / keyed paths).

## Integrations

### `library/services/` + `library/tags.py` — product services + audit hooks

- **`demo_gen.py` — Greenhouse builder**: `generate_demo_project`
  (Muse authors a novel vulnerable service from intel summaries) +
  `materialize_demo_project`; `BuildIntent`/`DemoProjectFiles`; snapshot-safe
  stdlib-only output. Upstream: MCP/CLI/demo routes. Downstream: red/blue loop.
- **`repo_intake.py`**: `RepoIntakeSpec` (https + 40-hex validation),
  `intake_repo_to_snapshot`, `_clone_in_staging` (non-started container,
  argv-list git exec, `get_archive` tar, .git strip, 2000-file/8MB caps),
  `detect_runtime` (package.json/requirements/composer/Makefile).
- **`projects.py`**: `ProjectSpec` intake from state/args; **`project_agents.py`**:
  red/blue/green agent runners; **`binary_intake.py`**: `validate_binary_blob/file`
  (ELF/Mach-O/PE, size caps); **`binary_telemetry.py`**: binary scan metrics.
- **`mcp_bridge.py`**: 6 tools (`submit_code_snippet`, `sms_scan_source`,
  `sms_scan_binary`, `sms_query_vault_stats`, `sms_verify_receipt`,
  `sms_scan_status`) with input/output schemas, `handle_mcp_request`
  JSON-RPC, scan-status registry.
- **`sms_api.py`**: `scan_source`/`verify_receipt` Python library entry;
  **`chatter.py`**: persona-voiced safe summaries; **`telemetry_hub.py`**:
  live event bus; **`tags.py`**: 128/128 feature-tag → surface bindings
  (`check_registry`, enforced by `dev.py tags` + gate).

### `library/shared/` — cross-cutting stdlib utilities

- **`sms_observability.py`**: `log`/`trace`/`record_metric`, per-aspect JSONL,
  LAW-4 redaction, `_summary.json`, `config.observability_mode`.
- **`sms_compress.py`**: context dedup + prune + token budgets;
  **`sms_budget.py`**: payload size guards; **`sms_http.py`**: bounded
  retries (`_clamp_tries/_max_bytes`); **`sms_records.py`**: verdict record
  shapes; **`sms_redact.py`**: report redaction; **`sms_scan_parse.py`**:
  scanner output normalization; **`sms_text.py`**, **`sms_async.py`**:
  text/async helpers.

## Execution Sandboxes, Fixtures & Showcase

### `docker/` — air-gapped sandbox images + in-sandbox harnesses

- Three images from pinned `python:3.12-alpine3.22` digest: `Dockerfile.target`
  (nodejs 22.23.4 + php84, non-root 10001), `Dockerfile.verifier` (stdlib
  only + `runner.py`), `Dockerfile.binary` (`file`/`binutils`/`xxd`,
  static reversing only, no compilers/network).
- **`runner.py`** (29 lines): runs `/verifier/verify.py`, maps
  `SystemExit(0/1/2)` verbatim, everything else → 2.
- **`binary_harness.py`** (106 lines): `127.0.0.1:8080` argv/stdin harness
  with `reject:` mitigation rules, 5 s timeout, 16-arg/4KB caps.
- Invariants: `network_mode="none"`, no host mounts, internal networks,
  per-session cleanup (`--cleanup`, disconnect teardown).

### `targets/` — five deterministic fixtures

- **`node_query_sink`** (`app.js` 34 lines): `GET /search?q=` →
  string-built `db.query()` (CWE-89) via `new Function` sink.
- **`node_chain_link`** (`app.js` 52 lines): Link A role-grant
  (`grant=reviewer` → reviewer) gates Link B dynamic expression — chain
  sweep target.
- **`php_command_sink`** (`index.php` 9 lines): `GET /?host=` →
  `shell_exec` argv concat (CWE-78).
- **`mysql_insecure_conf`** (`my.cnf` 9 lines): `bind-address 0.0.0.0`,
  `local-infile 1`, empty `secure-file-priv` (CWE-1188) — config audit,
  no DB started.
- **`binary_argv_echo`** (`echo.c` 22 lines + compiled ELF): unbounded
  argv reflection (CWE-134); contract: short alnum echoes, overlong/metachar
  must be rejected.

### `video-demo/` — standalone showcase rig (zero product wiring)

- **`TTSServer/`**: ChatTTS narration booth — `server.py` (:8002
  `/healthz /speak /render`, lazy torch/ChatTTS, narrator seed 6420 @ t0.3),
  `client.py` (`--render` → 24 kHz WAV), `booth.py` (pass/fail voice TUI),
  `sample_voices.py`, `start/stop.sh`. Standalone by README disclaimer.
- **`desktop-capture/`**: clean-room C PipeWire node (`deskcap/`,
  I420 1920×1080@60) + `gamescope/launch_sandbox.sh` (nested wayland-99 →
  wf-recorder → deskcap) + `pipewire/` isolated null-sink scripts.
- **`music-generation/`**: DawDreamer/Faust DSP factory (fixture venv,
  dawdreamer 0.9.0) — 9 scores; FINAL = 180.0 s cinematic bed
  (peak 0.8913); `GUIDANCE_MATRIX.md` all `[x]`.
- **`render_demo.sh`**: 6-phase provision/capture/mux provisioner with
  `--check` (starts nothing; `bash -n` clean); NEVER executed per policy.

## Verification, Docs & Tooling

### `tests/` — 129 RED-first files, gate 1085 green

- Families: `test_*_red.py` (failing-first contracts: ingest, intake,
  pricing, beats, demo-driver, render-demo, transport bounds, inf-overflow,
  booth, capture, mcp, ws), workflow/contract pins
  (`test_webui_v3_contract`, `test_tags`, `test_config_agents`,
  `test_project_entrypoints` incl. flake-hardened disconnect test),
  unit suites per module, `test_docs_presentation.py` (README/ARCHITECTURE
  claims pinned, incl. Node.js prerequisite + hackathon section).
- Gate (`dev.py check`): tags 128/128 → pytest → ruff check+format →
  compileall → `node --check` → `test_harness.py` → `--list-targets`.

### `docs/` — knowledge corpus

- `ARCHITECTURE.md` (dense specs), `SPEC.md` (canonical), `TAGS.md`,
  `HOW_IT_WORKS.md` (plain-language loop), `TECHNICAL_BREAKDOWN.md`,
  `SYSTEM_ARCHITECTURE_INDEX.md` (this file), `DEMO_SCRIPT.md` (7 beats,
  ≤180.0 s, narration stems), `OPEN_WEIGHT.md` (spark-open payload),
  `LOAD_TABLE.md` (measured timings + `/ws/system` stay-stub decision),
  `TRAPS.md` (wrong-assumption log), `reference/` (CLI/DASHBOARD/MODULES/…),
  `guides/` (WORKFLOWS/DEVELOPMENT/OBSERVABILITY), `plans/` + `research/`
  + `architecture/` (waves), `SESSION_LESSONS.md`, `VULN_TAXONOMY.md`.
- `HACKATHON_RUBRIC_LEDGER.md` (root): Run #1 7.06 baseline → Run #2 7.71.

### `.jcode/tools/` — dev harness

- `dev.py`: `setup` (uv/locked-hash or stdlib venv, `.env` template),
  `check` (full gate), `images`/`rebuild-images`/`docker-status`/`docker-test`,
  `doctor`, `offline-scan` (keyless 3-fixture proof), `quickstart`
  (±`--keyed` live chain), `serve/serve-up` (LAW 7 single-server),
  `smoke` (key-free health + assets), `tags`, `lock`.
- `offline_scan.py`, `project_scan.py`, `ui_scan.py` (+ `--offline`),
  `v3_live_e2e.py`, `v3_ui_proof.py`, `gate3_matrix.py`,
  `project_ui_scan.py`, `serve_up_drill.py`, browser/design-metric tools.
