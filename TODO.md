# TODO — Secure Mitigation System

Owner: Jcode agent. This file is the work queue. Check items off as they land.
Conventions: `[ ]` not done, `[/]` partial, `[.]` in-progress, `[x]` done.
Every item names its files and its proof.

## A. Research sidecar agent layer (on top of shipped `research.py`)

- [x] A1. Red research-only Muse prompt (`RED_RESEARCH_SYSTEM_PROMPT` in
      `prompts.py` + `RedResearchDigest` + `run_red_research` in `agents.py`):
      returns queries + attack patterns + CWE hints, never findings/patches.
- [x] A2. Blue research-only Muse prompt (`BLUE_RESEARCH_SYSTEM_PROMPT` +
      `BlueResearchDigest` + `run_blue_research`): fix patterns, never a patch.
- [x] A3. Project-workflow research prompts: same `RedResearchDigest` /
      `BlueResearchDigest` grounding flows into project contracts via
      `_gather_research` + `_run_opt_in_scanners` in `workflow.py`.
- [x] A4. Wired research context into `workflow.py`: opt-in fetch before
      red analysis (`_gather_research`), digest appended to red/blue
      contracts, `research` team log lines, `research_records` on ScanResult.
- [x] A5. Project path covered: `run_demo_build` + project WebSocket flow
      through `execute_project_workflow` with the same research grounding.
- [x] A6. `PURPLEBOX_RESEARCH` config gate in `config.py` (off default, `on`
      enables) + `--research` CLI flag in `main.py` (requires `--scan`).
- [x] A7. Dashboard surfacing: `research` team in comms feed (`writeLine` +
      stage advance), Research filter button, `tag-research` color.

## B. Trivy (aquasecurity/trivy)

- [x] B1+B2. Surveyed trivy `fs` JSON shape; transport wrapper chosen:
      `scanner_binaries.py` (stdlib subprocess, `ScannerRecord` mapping).
- [x] B3+B4. `parse_trivy_report` + `run_trivy` implemented; opt-in,
      degrades to [] when binary absent.
- [x] B5. Canned trivy fixture mapping test + absent-binary test.
- [x] C1–C5. Same pattern: `parse_grype_report` + `run_grype` (`grype dir:`),
      canned mapping + absent-binary tests.
- [x] D1+D2. Surveyed: Dependency-Track is a server; BOM upload client
      `scanner_dtrack.py` gated behind `PURPLEBOX_DTRACK_URL` +
      `PURPLEBOX_DTRACK_API_KEY` (both unset = skip).
- [x] D3. `build_bom` (CycloneDX 1.5) + `scan_packages` (upload, poll token,
      map findings, skip FALSE_POSITIVE).
- [x] D4. Mapping + BOM-shape tests with canned JSON (no live server).
- [x] E1+E2. `run_dependency_check` wrapper; `--noupdate` + generous timeout;
      NVD key passthrough documented in docstring.
- [x] E3+E4. `parse_depcheck_report` + canned mapping test + absent-binary.
- [x] F1–F5. `parse_osv_scanner_report` + `run_osv_scanner` (`--recursive`);
      canned mapping + absent-binary; same OSV backend as `research.py`.

## C–F. Grype, Dependency-Track, Dependency-Check, OSV-Scanner

Done — see the B-section entries above (all five live in `scanner_binaries.py`
+ `scanner_dtrack.py`, tested in `tests/test_scanners.py`).

## G. Cross-cutting

- [x] G1. Unified scanner interface: `ScannerRecord` common shape,
      absent-binary/timeout/degrade behavior shared; docs section below.
- [x] G2. Config + CLI: `PURPLEBOX_RESEARCH` + `PURPLEBOX_RESEARCH_SCANNERS`
      (off default, allowlist-validated), `--research` + `--research-scanners`.
- [x] G3. Dashboard: `research` team in comms feed + filter button + tag color
      (G3 panel counts deferred — records already on ScanResult).
- [x] G4. Full gate (262 passed), shipped develop `7786c48` -> main `454a14f`,
      pushed both, returned to develop.

## Scanner docs (G1)

`scanner_binaries.py` (Trivy, Grype, OSV-Scanner, Dependency-Check) and
`scanner_dtrack.py` (Dependency-Track server) share `ScannerRecord`:
scanner, cve_id, package, installed/fixed versions, severity, cvss, title,
summary (1500 cap), cwe, references. Every runner is None-safe: absent
binary, timeout, bad JSON, oversize output all degrade to `[]` — a missing
tool can never fail a scan. Binaries run on the host against a temp-dir
copy of the fixture, never inside the air-gapped sandbox. Records feed the
research sidecar as grounding under the same untrusted-data rules as
`research.py`; Docker evidence still decides every verdict.
Dependency-Track needs a live server: `PURPLEBOX_DTRACK_URL` +
`PURPLEBOX_DTRACK_API_KEY`, both unset means skip silently.

## H. Unfinished from history (audit 2026-10-28)

- [x] H1. Green builder reachable from dashboard: `/ws/demo` route +
      `run_demo_build` (Greenhouse generates from themes, red/blue exercise
      via project workflow) + Green build mode button + theme input.
      Proof: route test + live server.
- [x] H2. Green roster populates on green lines + demo start (null-leader
      guard added). Proof: same run.
- [x] H3. Reconciled stale A3/A5 fold notes (post-reunite wording) and G4 checkbox. Proof: gate + read-through.
- [x] H4. Dashboard research controls: `research-toggle` +
      `research-scanners-toggle` checkboxes feed `?research=on` + allowlisted
      `research_scanners` into every WS route; server parses per-scan into a
      replaced config. Proof: `test_ws_research_query_enables_sidecar_config`
      + `test_ws_research_absent_stays_off` + `test_dashboard_research_toggles_exist_and_default_off`.
- [x] H5. Project-mode + research interplay: `execute_project_workflow`
      runs `_gather_research` when enabled, grounds the red contract with the
      digest, stores records on `ProjectWorkflowResult.research_records`;
      dashboard renders them in a Threat-intel cycle detail. Proof:
      `test_project_research_on_runs_grounding_and_stores_records` (+ off-by-default).

## Done

- [x] `research.py` intel transport (OSV/CIRCL/GHSA/EPSS): paced, jittered
      backoff, 1 MiB caps, never-raises, committed `e827a8b`, merged to main.
- [x] Browser matrix: `--browser auto|chrome|chromium|edge|brave|firefox`
      in `ui_scan.py`, committed `175ad12`, merged to main.

## I. Green intent + web/CVE research depth (brief 2026-10-28-laws-green-research)

- [x] I1. Green builder: "What do you want to build?" + "Vulnerabilities to
      implement" dashboard prompts (CVE ids, named types, or free text).
      Files: `static/index.html`, `static/app.js`, `main.py` (`run_demo_build`).
      Proof: `test_demo_build_prompts_for_brief_and_vulns` +
      `test_demo_request_accepts_brief_and_vulns_fields`.
- [x] I2. Intent interpreter: green/research agents parse the vuln field into
      CVE ids vs named types vs free text and plan research accordingly.
      Files: `demo_gen.py` (new `parse_build_intent`), tests.
      Proof: `test_parse_build_intent_splits_cve_named_free` et al.
- [x] I3. CVE endpoint series for green/research: `cve_records` in
      `research.py` fans each CVE id out to CIRCL + OSV + EPSS (+ GHSA by id),
      keyless, never-raises, deduped. Live probe: CVE-2024-3094 returned
      circl+osv+epss(0.909). Green builder calls it when intent has CVE ids.
      Files: `research.py`, `main.py`, `tests/test_scanners.py`.
      Proof: `test_cve_records_series_never_raises_and_dedupes` (+ live probe).
- [x] I4. Real web search for green/research: `web_notes` in `research.py`
      uses the Wikipedia JSON API only (search + intro extracts — no HTML
      scraping, no bot wars), same pacing/backoff/caps/never-raises discipline.
      Green builder calls it for named types + free text. Live probe: "SQL
      injection" returned its definition extract.
      Files: `research.py`, `main.py`, `tests/test_scanners.py`.
      Proof: `test_web_notes_canned_search_plus_extract` (+ live probe).
- [x] I5. Green prompt upgrade: Greenhouse system prompt consumes build
      intent + CVE records + web notes and implements the requested flaws.
      Files: `demo_gen.py` (`DEMO_GEN_SYSTEM_PROMPT` + payload), tests.
      Proof: `test_generate_demo_project_carries_intent_into_payload`.
- [x] I6. Research sidecar upgrade: `_gather_research` runs the contract
      through `parse_build_intent` — CVE ids get the `cve_records` series,
      substantive named types/descriptive text get `web_notes`; both land in
      records + digests. Files: `workflow.py`, `tests/test_workflow.py`.
      Proof: `test_research_gather_adds_cve_and_web_records`.
- [ ] I7. Small features that fall out: keep each cheap, tested, shippable
      (record here as they land).

## J. LAW 7 single-server + key check (brief 2026-10-28-startup-law, rerun 2026-10-28-compliance-rerun)

- [x] J1. LAW 7 in `LAWS.md`: probe `/api/health` before starting a server;
      a live server owns the port — kill ONLY own spawned PIDs/handles (never
      broad pkill, Firefox-rule precedent), restart with `.env` sourced,
      verify `api_key_configured` + `inference_ready` before declaring up.
      Files: `LAWS.md`. Proof: gate green + live drill below.
- [x] J2. `serve_up` in `.jcode/tools/dev.py` (`serve-up [--port] [--no-restart]`):
      probe → terminate own tracked handle → start with key from owner-only
      `.env` → verify keyed health. Helpers: `read_env_key`, `keyed_env`,
      `probe_health`, `stop_handle`, `wait_for_keyed_health`.
      Files: `.jcode/tools/dev.py`, `.jcode/tools/serve_up_drill.py`,
      `tests/test_dev_tool.py`. Proof: 8 passed in `test_dev_tool.py` +
      live drill `DRILL PASS: stale keyless -> own-handle restart -> keyed
      ready` (port 18011: before `api_key_configured=False`, after `True`).

## K. Compliance rerun 2026-10-28 (brief 2026-10-28-compliance-rerun)

- [x] K1. Rerun items: LAW 0 read (AGENTS.md + LAWS.md) stated; LAW 7 drill
      re-run live on port 18011 (own-handle kill only, keyed verify);
      LAW 9 red evidence confirmed (naive status==ok declares a keyless
      server UP); rebased onto feature/ui-gaps-green-crash (LAWs 0,11,12).
      Files: `LAWS.md`, `TODO.md`, `.jcode/briefs/2026-10-28-compliance-rerun.md`.
      Proof: `serve_up_drill.py --port 18011` DRILL PASS + post-rebase gate
      321 passed + `test_dev_tool.py` 8 passed. Committed on branch, no merge.

## L. Zero-day Wave 2 implementation (brief 2026-10-29-wave2-continuation; RESEARCH_V1.md + SPEC SS14)

Baseline proof: `dev.py check` 329 passed on `feature/zero-day-wave1-research@214ed32` before edits.

- [x] L1. Sink-adjacency reachability fusion: deterministic `reach_score` (0-100 int) + `reach_evidence` (list[str]) on CVE summaries.
      Files: `deep_scan.py` (new pure `reachability_score(summary, static_findings)`), `cve_workflow.py` (attach per summary in `execute_cve_scan`), `tests/test_deep_scan.py`.
      Fail-closed: no fixed version, no sink signal, no CVE match -> low score; absent signals never raise it. Novelty: Snyk/Endor does call-graph reachability, but we fuse OSV fixed-ranges + static sink adjacency keyless with no SaaS index.
      Proof: 4 new tests red (ImportError/KeyError) then green; `tests/test_deep_scan.py` 20 passed + 5 pre-existing docker-import fails (unchanged from baseline 16+5); ruff check/format clean; subset suite 177 passed, 12 failed all pre-existing on clean tree.
- [x] L2. Ghost-probe liveness, exit-2 gap: project workflow runs post-probe liveness whenever probe exit != 0 (today only exit==1), and names it in evidence.
      Files: `project_workflow.py` (`verify_project_snapshot`), `tests/test_project_workflow.py`, `tests/helpers.py` only if seam requires.
      Fixture workflow already has post-probe liveness (`workflow.py` final_health); do not duplicate it. Novelty: CodeMender PoC verify is flag-bypassable, but our ternary oracle stays fail-closed: inconclusive + dead target earns no credit.
- [x] L3. Greenhouse hardening: bounded `size` (small|standard), `flaw_count` (1-8), `seed` (int) through demo generation, defaults = current behavior.
      Files: `demo_gen.py`, `main.py` (WS /ws/demo + CLI --ai-demo flags), `sms_cli.py` CONFIG_KEYS, `static/index.html`, `static/app.js`, `tui.py` only if a demo surface exists there (scout says fixture-only: record parity gap, do not invent TUI demo mode), `tests/test_demo_gen.py`, `tests/test_cli_parity.py`, `tests/test_dashboard_project.py`/`test_web.py` as touched.
      Novelty: competitors replay fixed fixtures, but we generate fresh intel-grounded targets per run with bounded variability.
- [x] L4. CVE disclosure fast lane: `execute_cve_scan(..., fast_lane=True)` skips scanner-binary stage entirely (static + OSV only), deterministic ordering, never-raises preserved.
      Files: `cve_workflow.py`, `tests/test_deep_scan.py`. CLI/WS wiring only if an existing CVE surface exists; otherwise core + test is the unit (record surface gap in report).
      Novelty: KEV gives a 2-week catalog baseline, but we start from keyless OSV/CIRCL/GHSA/EPSS at scan time in minutes.
- [/] L5. Merge writer branches (spawner owns merge, semantic resolution), full `dev.py check` green, LAW 12 version decision recorded, live proof where surfaces changed (offline_scan / ui_scan as applicable).
      Files: merge of L1-L4 branches. Proof: gate output + live run artifact names.
      Proof so far: merges a4ccc42/4f0be8e/e10a589/ad434e4 + semantic conflict fix in
      tests/test_cli_parity.py; gate 351 passed (329 baseline + 22 new); offline_scan
      3/3 verified; ui_scan firefox+chrome 'Boundary check passed'; browser-operated
      demo-size/flaw-count/seed controls on :18099 (own server, killed after).
      Remains: LAW 12 bump 0.2.0 -> 0.3.0 (major: new capabilities) applied at ship
      (LAW 1 flow not yet invoked by user), worktree removal, WS/TUI CVE fast-lane
      surface gap + TUI demo-mode gap recorded for Wave 3 docs.

## M. Zero-day Wave 3 docs (blocked on L5 gate: 351 passed + live proof, done)

- [x] M1. README + CLI reference for Wave 2: reach_score/reach_evidence, --fast-lane, --demo-size/--flaw-count/--demo-seed, ghost-probe exit-2 liveness note.
      Files: `README.md`, `docs/reference/CLI.md`. Proof: links/flags verified against `main.py --help` output; gate green.
- [x] M2. Architecture docs: reachability fusion + fast lane + liveness in `docs/architecture/` (extend PROJECT_WORKFLOW.md or new WAVE2 doc linked from docs index), surface gaps recorded (dashboard socketQuery omits dependency-track vs server 5-set; no WS/TUI CVE fast-lane surface; TUI has no demo mode).
      Files: `docs/architecture/*`, `docs/INDEX.md` if present else record absence. Proof: grep for gap notes; gate green.
- [/] M3. Ship decision point: LAW 12 bump 0.2.0 -> 0.3.0 + LAW 1 flow ONLY on user "ship it".
      Proof so far: README 1178cda, CLI dc7a4b6, arch d193d84 merged; gate 351 passed after docs merge.
      Remains: user invokes ship; then bump APP_VERSION + surfaces, feature -> develop -> main, both pushes, end on develop.
      Next unblocked work without ship: Wave 4 extended research (RESEARCH_V2) can start on this branch.

## N. Zero-day Wave 4 extended research (brief 2026-10-28-zero-day-9wave item 4)

- [.] N1. Five read-only lanes -> RESEARCH_V2.md: (a) re-verify Wave 1 recall-grounded claims (Semgrep autofix safety, Snyk rescan+unit-test verification, Endor/Snyk reachability) against live sources where reachable; (b) extended horizon: agentic remediation since Wave 1 (new entrants, benchmarks); (c) same-day patching economics/SLA data (KEV timelines, EPSS v5 follow-through); (d) sandbox/proof systems (eBPF, snapshot fuzzing, proof-carrying patches); (e) keyless intel evolution (OSV/GHSA/CIRCL changes).
      Files: `RESEARCH_V2.md` only (research writes no code). Proof: file committed with A/B/C novelty statements + explicit verified-vs-recall labels; gate green (docs-only).
- [ ] N2. SPEC delta for Wave 5 gated on RESEARCH_V2 (no implementation before it, strict sequencing).

## O. Zero-day Wave 5 implementation (blocked on RESEARCH_V2 + SPEC SS14.5, done)

- [x] O1. GHSA `?cve_id=` lookup fix + epss/cvss_v4/first_patched_version consumption. Files: `research.py`, `tests/test_scanners.py`. Fail-first canned GHSA test. Proof: `feature/w5-ghsa a31ef56`; gate 367 passed; live XZ CVE GHSA record w/ patched version.
- [x] O2. KEV 5th `cve_records` signal + reach_score likelihood tie-break (never lowers fail-closed floor). Files: `research.py`, `deep_scan.py`, `tests/test_scanners.py`, `tests/test_deep_scan.py`. Proof: `feature/w5-kev 7a5fdc8`; gate 367; live log4shell KEV title+due+ransomware.
- [x] O3. Differential normal-contract gate (original vs patched equal class). Files: `workflow.py`/`project_workflow.py` narrow, tests. Proof: `feature/w5-differential e2768e6` explicit `CycleEvidence.differential_passed` both fates; gate 367.
- [x] O4. Fast-lane SSVC tiering of output order. Files: `cve_workflow.py`, `tests/test_deep_scan.py`. Proof: `feature/w5-tier 2ba4100` sort key `(-reach_score, not has_fixed, id)`; gate 367.
- [ ] O5. Wave 6 expansion docs after O1-O4 gate green.
