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
- [/] I7. Small features that fall out: keep each cheap, tested, shippable
      (record here as they land). Standing bucket, closes per-item: landed so far per I/L/O/Q/R sections; nothing open at 2026-10-29 finish-up.

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
- [x] L5. Merge writer branches (spawner owns merge, semantic resolution), full `dev.py check` green, LAW 12 version decision recorded, live proof where surfaces changed (offline_scan / ui_scan as applicable).
      Files: merge of L1-L4 branches. Proof: gate output + live run artifact names.
      Proof so far: merges a4ccc42/4f0be8e/e10a589/ad434e4 + semantic conflict fix in
      tests/test_cli_parity.py; gate 351 passed (329 baseline + 22 new); offline_scan
      3/3 verified; ui_scan firefox+chrome 'Boundary check passed'; browser-operated
      demo-size/flaw-count/seed controls on :18099 (own server, killed after).
      Closed 2026-10-29: all wt-w2-* worktrees removed (none remain); WS/TUI CVE fast-lane
      surface gap + TUI demo-mode gap recorded in docs/architecture/WAVE2.md (Wave 3 docs M2).
      LAW 12 bump 0.2.0 -> 0.3.0 stays deferred to ship; tracked only by M3.

## M. Zero-day Wave 3 docs (blocked on L5 gate: 351 passed + live proof, done)

- [x] M1. README + CLI reference for Wave 2: reach_score/reach_evidence, --fast-lane, --demo-size/--flaw-count/--demo-seed, ghost-probe exit-2 liveness note.
      Files: `README.md`, `docs/reference/CLI.md`. Proof: links/flags verified against `main.py --help` output; gate green.
- [x] M2. Architecture docs: reachability fusion + fast lane + liveness in `docs/architecture/` (extend PROJECT_WORKFLOW.md or new WAVE2 doc linked from docs index), surface gaps recorded (dashboard socketQuery omits dependency-track vs server 5-set; no WS/TUI CVE fast-lane surface; TUI has no demo mode).
      Files: `docs/architecture/*`, `docs/INDEX.md` if present else record absence. Proof: grep for gap notes; gate green.
- [x] M3. Ship invoked 2026-10-29: LAW 12 major bump 0.3.0 -> 0.4.0 (new capabilities: receipts, guard rationale, fast-lane topping, mutation probes, freshness/EUVD, templates, blueprint items 1-8, Wave 5 re-run); LAW 1 flow feature -> develop -> main, both pushed, end develop. Proof: ship commit message + gate 493 + live Docker proof.
      Proof so far: README 1178cda, CLI dc7a4b6, arch d193d84 merged; gate 351 passed after docs merge.
      Remains: user invokes ship; then bump APP_VERSION + surfaces, feature -> develop -> main, both pushes, end on develop.
      Next unblocked work without ship: Wave 4 extended research (RESEARCH_V2) can start on this branch.

## N. Zero-day Wave 4 extended research (brief 2026-10-28-zero-day-9wave item 4)

- [x] N1. Five read-only lanes -> RESEARCH_V2.md: (a) re-verify Wave 1 recall-grounded claims (Semgrep autofix safety, Snyk rescan+unit-test verification, Endor/Snyk reachability) against live sources where reachable; (b) extended horizon: agentic remediation since Wave 1 (new entrants, benchmarks); (c) same-day patching economics/SLA data (KEV timelines, EPSS v5 follow-through); (d) sandbox/proof systems (eBPF, snapshot fuzzing, proof-carrying patches); (e) keyless intel evolution (OSV/GHSA/CIRCL changes).
      Files: `RESEARCH_V2.md` only (research writes no code). Proof: RESEARCH_V2.md 12ec542 + addendum f5e92cc; gate green (docs-only).
- [x] N2. SPEC delta for Wave 5 gated on RESEARCH_V2 (no implementation before it, strict sequencing). Proof: SPEC SS14.5 committed 3d37cfa before O1-O4 writers.

## O. Zero-day Wave 5 implementation (blocked on RESEARCH_V2 + SPEC SS14.5, done)

- [x] O1. GHSA `?cve_id=` lookup fix + epss/cvss_v4/first_patched_version consumption. Files: `research.py`, `tests/test_scanners.py`. Fail-first canned GHSA test. Proof: `feature/w5-ghsa a31ef56`; gate 367 passed; live XZ CVE GHSA record w/ patched version.
- [x] O2. KEV 5th `cve_records` signal + reach_score likelihood tie-break (never lowers fail-closed floor). Files: `research.py`, `deep_scan.py`, `tests/test_scanners.py`, `tests/test_deep_scan.py`. Proof: `feature/w5-kev 7a5fdc8`; gate 367; live log4shell KEV title+due+ransomware.
- [x] O3. Differential normal-contract gate (original vs patched equal class). Files: `workflow.py`/`project_workflow.py` narrow, tests. Proof: `feature/w5-differential e2768e6` explicit `CycleEvidence.differential_passed` both fates; gate 367.
- [x] O4. Fast-lane SSVC tiering of output order. Files: `cve_workflow.py`, `tests/test_deep_scan.py`. Proof: `feature/w5-tier 2ba4100` sort key `(-reach_score, not has_fixed, id)`; gate 367.
- [x] O5. Wave 6 expansion docs after O1-O4 gate green. Proof: merges `feature/w6-readme 8f297c6`, `w6-cli dd9545e`, `w6-arch a5caeff` (WAVE5.md); gate 367 passed.

## P. Zero-day Waves 7-9 (blocked on RESEARCH_V3, pending)

- [x] P1. Wave 7: RESEARCH_V3.md (freshness/compat defects + post-Wave-5 frontier), live-verified or labelled recall. Proof: RESEARCH_V3.md committed dd04172 with SPEC SS14.6.
- [x] P2. Wave 7 or 8 implementation gated on SPEC delta for V3 (strict sequencing, fail-first). Proof: sections Q/R landed under SPEC SS14.6/SS14.7.
- [x] P3. Wave 8 hardening: adversarial review of O1-O4 merges, edge tests. Proof: RESEARCH_V3 Lane A audit found dead KEV/EPSS tie-break; fixed Q1/Q2; LOW bundle R2; T1/T2 live-proof regression found+fixed.
- [x] P4. Wave 9 adventure: child features spun from proven Wave 5 mechanics only. Proof: property/metamorphic contract checks (R1, child of O3 differential gate) + shape split (T2); VEX/SARIF/mutation counts cut as parity/non-proof per RESEARCH_V3 Lane C.

## Q. Zero-day Wave 7 implementation (blocked on RESEARCH_V3 + SPEC SS14.6, done)

- [x] Q1. Wire `kev_listed`/`epss_percentile` through `cve_workflow` enrichment into `reachability_score`; fail-first through real producer path; evidence strings live. Files: `cve_workflow.py`, `tests/test_deep_scan.py`.
- [x] Q2. KEV per-process catalog cache in `research.kev_lookup`; fail-first cache test. Files: `research.py`, `tests/test_scanners.py`.
- [x] Q3. Wave 8: property/metamorphic checks + LOW bundle (after Q1/Q2 gate green). Proof: section R (R1/R2 merged, gate 392, live project_scan 2/2).
- [x] Q4. Wave 9: docs + adventure only if Q1-Q3 clean. Proof: R3 docs merged; adventure scoped to property-shape split (T2).

## R. Zero-day Wave 8 (blocked on RESEARCH_V3 Lane C + SPEC SS14.7, done)

- [x] R1. Property/metamorphic normal-contract checks wired into verification, recorded as evidence, fail-closed. Files: `checks.py` (`project_property_script`), `project_workflow.py` (`properties` + `property_gate_passed` in retain), `tests/test_property_checks.py` (13 tests). Proof: fail-first red (ImportError, gate-disabled rollback FAILED), standalone suite 385 passed. Opt-in: spec contract first line must name the fixture id (producer wiring done in `project_scan.py`).
- [x] R2. LOW bundle: research fetch caps, epss sanitizer reuse, intel_search CVE shape. Files: `research.py`, `intel_search.py`, `cve_workflow.py`, `tests/test_scanners.py`. Fail-first each (red 3 failed, green post-fix).
- [x] R3. Wave 9 docs after R1/R2 gate green. Proof: merges feature/w9-readme 1c8e414 + feature/w9-arch 6f69d59 (WAVE8.md + trap section); gate 392 passed. Adventure item cut per zero-day mandate: property-shape split was the shipped child feature of R1; nothing else cleared same-day-remediation bar.

## S. Root de-bloat 3-wave refactor (briefs 2026-10-28-root-debloat-3wave-refactor, 2026-10-29-repo-refactor-s1s3-unblock; branch feature/root-debloat-wave2-migration)

- [x] S1. Audit refresh on zero-day tree (baseline gate 392 passed pre-move): docs tree mapped (Moved shims at flat level, canonical content in architecture/guides/reference/decisions), 11 non-protected root .md classified (SPEC/GAP trio/RESEARCH trio -> categorized; AGENT.md/NOTE_E2E/VALIDATION.md -> archive; LICENSE.md kept at root), Wave 1 audit branch 39570ac verified to hold no domain-plan artifact (merge commit only), full internal import blast radius mapped (34 root .py + tests/tools/docker). Proof: brief 2026-10-29-repo-refactor-s1s3-unblock + this section.
- [x] S2. Migration via git mv (history preserved): 11 .md into docs/{SPEC at top, research/, audits/, archive/}; 30 .py into modules/{core,workflows,intel,services,shared} + __init__.py; root keeps main.py, sms_cli.py, tui.py, test_harness.py + protected AGENTS.md/LAWS.md/TODO.md/README.md/LICENSE.md. Proof: git status rename entries.
- [x] S3. Rewire + gate: all internal imports rewritten to modules.* (modules/tests/tools incl. 3 string-form seams: tui sys.modules, deep_scan source probe, web monkeypatch), BASE_DIR re-anchored to parents[2], isort config -> ["main","modules","test_harness","tui"], ruff --fix + format, gate 392 passed, offline_scan 3/3 verified, project_scan 2/2 retained, main.py --list-targets ok. Files: modules/**, main.py, tui.py, test_harness.py, tests/**, .jcode/tools/*.py, docs/index.md, README.md, docs/guides/DEVELOPMENT.md, docs/architecture/REPOSITORY.md, docs/archive/AGENT.md, pyproject.toml.

## T. Finish-up 2026-10-29 (brief 2026-10-29-finish-up)

- [x] T1. Wave 8 live-proof failure diagnosed: opt-in property script aliased project plain-text services to the fixture JSON-envelope script; properties exit 2 (JSONDecodeError) vetoed retain fail-closed. Evidence: reports/project-acceptance/project-acceptance.json cycle 1 properties exit_code 2, status rolled_back; standalone R1/R2 branch commits passed because neither had the merge-commit contract wiring.
- [x] T2. Fix fail-first: split property scripts by real response shape (node_query_sink JSON envelope; new project_lookup_text plain text; phantom node_eval_service removed; project_scan contract retargeted). Files: `checks.py`, `tests/test_property_checks.py`, `.jcode/tools/project_scan.py`. Proof: writer RED (exit 2 unknown fixture) then 50 passed; merged gate 392 passed; live `project_scan.py` PASS 2/2 cycles retained, properties exit 0 both cycles.
- [x] T3. Wave 9 docs merged (`1c8e414` README subsection, `6f69d59` WAVE8.md incl. property response-shape trap); TODO Q3/Q4/P1-P4/N1/N2/L5 closed with proof; gate 392 passed. I7 stays [/] standing bucket; M3 ship + S1-S3 de-bloat remain open by user gate, not omission.

## Dashboard design refresh (2026-10-29, Jcode)

- [x] Redesign `static/index.html`, `app.css`, and `app.js` as a responsive verification workspace (0.3.0). All 91 existing IDs and scan contracts preserved. Proof: `tests/test_dashboard_design.py` failed then passed; browser arrow-key test failed then passed; `dev.py check` green with 394 tests. Chrome + Firefox `ui_scan.py --offline --design-check` pass, including navigation, keyboard focus, all mode form bounds, and real Docker scans with cleanup. Before/after status, seven stages, facts, patch stats and model profile match. Evidence: `reports/ui-{before,after}-{chrome,firefox}.{json,png}`, width-suffixed screenshots, and `reports/ui-design-gate.txt`. Harness migration fix and verification procedure documented in `docs/guides/DEVELOPMENT.md`.

- [x] Measure dashboard outcomes against baseline `d7763fa` with `.jcode/tools/ui_design_metrics.py`: at 1440px and 390px, placeholder contrast improves 3.07:1 to 6.90:1, mode rows improve 2/3 to 1, keyboard-focusable logs improve 0 to 4, and rendered decorative animations fall 11 to 0. All assertions pass. Evidence: `reports/ui-design-metrics.json`; measurement scope and limitations documented in `docs/guides/DEVELOPMENT.md`. These usability outcomes supplement the passing real-browser scan matrix, not a claim of measured subjective preference.

## U. TUI parity gap closure (brief 2026-10-30-tui-parity; branch feature/tui-parity)

- [x] U1. Reader: entry-point contracts for mcp/binary/sweep/project/demo/cve (signatures, gating, consent rules, redactors). Read-only, no writes. Proof: report with file:line anchors.
- [x] U2. Writer A (`feature/tui-models`, worktree `/tmp/wt-tui-models`): TuiState mode/depth/fields + parse_key/apply_action + render_panes + footer/help; `tests/test_tui_modes.py` fail-first. Proof: probe 15/15 GREEN + modes 6/6 (commit 5f3a497); pre-existing test_tui.py 2-fail noted.
- [x] U3. Writer B (`feature/tui-dispatch`, worktree `/tmp/wt-tui-dispatch`): prompt helper + mode dispatch + `_curses_main` wiring + `run_plain` flags; `tests/test_tui_dispatch.py` + `tests/test_tui_plain.py` fail-first. Proof: 51 passed (probe 17 + dispatch 11 + plain 8 + test_tui 15), commits 6d76e85 + a6728c4.
- [x] U4. Spawner merge: merge both writer branches into `feature/tui-parity`, full `dev.py check` green, live TUI proof (plain sweep + binary), CLI/dashboard regression check. Proof: merges 270dc22 + d2b2a52; conflict unified TUI_MODES/MODE_ORDER; spawner fix honors sys.modules fakes so test_tui.py passes any order; 72/72 TUI files green; gate 557 passed + ruff clean; live Docker proofs: fixture + sweep + binary modes reached real Docker phases and failed closed on unreachable loopback Muse endpoint (no fallback provider contacted); docs MODULES.md + CLI.md TUI parity rows.
- [x] U5. Ship: TODO close-out, LAW 12 version decision (0.5.0 -> 0.6.0 major: TUI tri-surface parity — new modes/keys/flags), feature → develop → main on go-ahead. Proof: gate 557 + ruff clean; version consistent (APP_VERSION, README badge, MCP serverInfo, dashboard footer).

## Wave 9 swarm close (2026-10-29; blueprint ZERO_DAY_BLUEPRINT.md@cb79d4d)

- [x] W1. Wave 7 strategy: blueprint from 10 inward verdicts (frog/goat/lion/wolf/horse/koala/llama/mouse/otter/panda), panda SHIP/LABEL/CUT, 8-item Wave 8 build order. Files: `ZERO_DAY_BLUEPRINT.md`. Proof: commit `cb79d4d`.
- [x] W2. Wave 8 items 1-3 (goat/wolf): rank freshness, frozen-pool build-failure veto, exec-required liveness. Proof: merges `1e6fc05` + `ef26ff8` + `39c5851`; gate green.
- [x] W3. Wave 8 items 4-6 (koala): CycleReceipt ids + all-cycles export, GuardRationale linkage, `stale` token. Proof: merges `c2b70c3` + `61a2f59`; gate green.
- [x] W4. Wave 8 items 7-8 (horse/llama): repeat-stability net + image digest pin. Proof: merge `3a9c98c` (`6b7bdf9`); gate 479 passed.
- [x] W5. Executive architecture: `docs/architecture/ZERO_DAY.md` (verdicts, 8 items w/ file:line anchors, 394 -> 479 gate, offline_scan 3/3 + project_scan 2/2 live proof, honest gaps), linked from `docs/architecture/index.md` + `docs/index.md`. Proof: this section + gate 479.

## X. Hackathon expansion M1-M4 (brief 2026-10-29-expansion; branch feature/expansion-plan)

- [x] X1. M1 executive README + `docs/ARCHITECTURE.md`: verbatim hook, mermaid, quickstart + `--ai-demo`, ~90% Muse narrative, Why-Muse (Spark 1.3/Wonder 1.0, $150 pool vs self-host), ARCHITECTURE.md links; dense Wave/SPEC/isolation/config/map specs moved verbatim. Files: `README.md`, `docs/ARCHITECTURE.md`, `docs/index.md`, `tests/test_docs_presentation.py` (7 pass, was 5 RED). Proof: gate green; no spec content lost (marker inventory).
- [x] X2. M2 MCP `submit_code_snippet` over the red/blue Docker loop: POST /mcp Streamable HTTP JSON-RPC, language allowlist + 64 KiB cap, ephemeral snippet target reusing fixture runtime/baseline, VerdictReceipt + exit codes returned. Files: `modules/services/mcp_bridge.py`, `main.py` (route + executor + CLI `--mcp-snippet`), `tui.py`, `static/` (mode + form + POST client), `tests/test_mcp_server.py` (12 pass incl. WS/CLI/dashboard parity). Proof: live Docker pre=0/post=1 verified with receipt sha, 0 leftovers.
- [x] X3. M3 3-pass sweep (standard/deep/threat-actor): per-pass red prompts + `run_red_team_pass_analysis`, `execute_sweep_scan` never stops at first finding, blue cumulative patches, verified only when all passes hold. Files: `modules/workflows/sweep.py`, `modules/core/prompts.py`, `modules/core/agents.py`, `main.py` (CLI `--sweep-passes`, WS `?sweep_passes=`, redaction), `tui.py`, `static/` (selector + summaryEvidence), `tests/test_sweep_passes.py` (9 pass). Proof: live Docker 3-pass P1 pre=0/post=1 receipt-pinned, P2/P3 clear, verified, 0 leftovers.
- [x] X4. M4 binary 3-pass sweep via trusted harness: `docker/Dockerfile.binary` (pinned digest + locked file/binutils/xxd), `binary_harness.py` (bounded argv/stdin, 5s timeout, reject: rules), docker_manager binary staging/harness/profile methods, `binary_intake.py` (ELF/Mach-O/PE, 8 MiB), `binary_sweep.py` 3-pass loop with per-pass receipts. Files: + CLI `--binary-target`, WS `/ws/binary`, dashboard mode, TUI flag, `tests/test_binary_intake.py` (12 pass). Proof: live Docker static ELF P1 pre=0/post=1 receipt-pinned, P2/P3 clear, verified, 0 leftovers.
- [x] X5. Ship prep: `docs/ARCHITECTURE.md` M2-M4 sections, CLI/DASHBOARD reference rows, README pointers, LAW 11 browser proof (Chrome+Firefox offline Boundary check passed; new MCP/sweep/binary controls operated in Firefox via `.jcode/tools/browser_controls_check.py`), LAW 12 major bump 0.4.0 -> 0.5.0 (`APP_VERSION`, dashboard footer, README badge, MCP serverInfo, all parity-checked). Proof: `dev.py check` 531 passed.

## Y. V1.0.0 closed-loop guidance execution (brief 2026-10-30-v1-guidance-directive; branch feature/v1-guidance-matrix; ledger docs/plans/V1_GUIDANCE_MATRIX.md)

- [x] Y0. Phase 0 recon + matrix init: baseline gate 557 passed, brief filed, matrix created. Files: `docs/plans/V1_GUIDANCE_MATRIX.md`, `.jcode/briefs/2026-10-30-v1-guidance-directive.md`. Proof: ledger on disk; 557 passed gate (now 626 on develop).
- [x] Y1. Subsystem A compression engine: `modules/shared/sms_compress.py` (dedup + sink-preserve), CompressionStats on ScanResult/SweepScanResult, CLI/TUI/UI badges. Files: `modules/shared/sms_compress.py`, `modules/workflows/workflow.py`, `modules/workflows/sweep.py`, `tests/test_compression.py` (RED fail-first). Proof: gate 599+ green; compression facts rendered.
- [x] Y2. Subsystem B encrypted vault: `modules/intel/sms_vault.py` (RED/BLUE/GREEN namespaces, AES-GCM via cryptography, key 0600, fingerprint query, commit-back, redacted stats). Files: `modules/intel/sms_vault.py`, `tests/test_vault.py` (RED fail-first incl. wrong-key). Proof: vault recall + stats green.
- [x] Y3. Subsystem C sweep gap closure: prompt/UI/report audit + fill (pass indicator + metrics). Files: `modules/workflows/sweep.py`, `modules/core/prompts.py`, `static/app.js` (#pass-chip), `tests/test_sweep_passes.py`. Proof: 8 sweep tests + UI pass chip.
- [x] Y4. Subsystem D binary fixture + mitigation artifact: `targets/binary_argv_echo/` deterministic ELF fixture + registry + telemetry script + harness shim guards. Files: `targets/binary_argv_echo/`, `modules/core/registry.py`, `tests/test_binary_fixture.py`, `tests/test_binary_intake.py`. Proof: offline_scan + binary harness live; listed in --list-targets (4 entries).
- [x] Y5. Subsystem E library API + 4 MCP tools + --mcp STDIO: `modules/services/sms_api.py` (scan_source/scan_binary/query_vault_stats/verify_receipt) + POST /mcp + --mcp STDIO (5 tools) + sms_scan_source/sms_scan_binary/sms_query_vault_stats/sms_verify_receipt. Files: `modules/services/sms_api.py`, `modules/services/mcp_bridge.py`, `main.py` (--mcp), `tests/test_library_api.py`, `tests/test_mcp_server.py` (RED fail-first). Proof: 605-pass gate + --mcp STDIO 5-tool handshake + tests/test_mcp_server.py 14 passed.
- [x] Y6. Subsystem F README executive refactor + UI/TUI badges + 0.7.0 bump + LAW 11 browser matrix. Files: `README.md` (Mermaid V1, Muse 90%, spark/wonder economics, differentiation, 3-min demo), `docs/ARCHITECTURE.md`, `static/` (fact-compression/fact-vault/pass-chip), `tests/test_docs_presentation.py` (+2). Proof: 599-pass gate + ui_scan Chrome/Firefox cards verified + version 0.7.0 consistency; merged via feature/v1-guidance-matrix -> develop -> main (59fa3d9).
- [x] Y7. Ship: full gate green (626), live Docker proof (3/3 verified later), browser E2E (Chrome/Firefox cards), W1 telemetry added post-ship; feature -> develop -> main per LAW 1/5. Proof: Ship 59fa3d9 (0.7.0 major) + later 3b2396f gate 615 + TOML/JSON/CLI reference docs.

- [x] Y6. Subsystem F README executive refactor + 0.7.0 bump + badges + demo guide + docs parity (README, ARCHITECTURE V1, CLI/MODULES refs; tests/test_docs_presentation.py +2). Proof: 599-pass gate + ui_scan Chrome/Firefox + version consistency (APP_VERSION/dashboard/README/MCP serverInfo 0.7.0).
- [x] W1. binary_sweep compression+vault parity + source-path routing guards (tests 8 pass). Files: modules/workflows/binary_sweep.py, workflow.py, sweep.py, main.py socket guard, tests/test_binary_fixture.py.
- [x] W2. MCP HTTP live sms_scan_source/sms_scan_binary/sms_query_vault_stats + shared envelope + routing guards (tests/test_mcp_server.py +4). Proof: 605-pass gate + --mcp STDIO 5-tool handshake.
- [x] W3. ARCHITECTURE V1 section + CLI/MODULES reference rows. Proof: docs greps + 605-pass gate.

## W1 integration (brief 2026-10-30-rubric-reissue; branch feature/w1-proj-telemetry)

- [x] W1a. Project telemetry writer (worktree: own checkout, branch feature/w1-proj-telemetry): compression/vault_recall/vault_namespaces on ProjectWorkflowResult + once-per-run [phase compress]/[phase vault] logs. Proof: tests/test_project_telemetry.py 6 pass; branch tests 53/53; merged gate 615.
- [x] W1b. CLI rows writer (worktree /tmp/wt-w1-cli, branch feature/w1-cli-rows): sms_compress/vault/api rows in CLI.md + parity test. Proof: tests/test_cli_parity.py 41 pass; commit 579f68b.
- [x] W1c. UI pass writer (worktree /tmp/wt-w1-ui, branch feature/w1-ui-pass): #pass-chip live element + binary_argv_echo Binary-mode redirect. Proof: node --check OK, design tests 5 pass; commit a0fb70e.
- [x] W1d. Spawner merge: w1-cli-rows + w1-ui-pass into w1-proj-telemetry (no conflicts, disjoint scopes), full gate 615 passed, Gates 2 (offline-scan 3/3 verified) + 3 (ui_scan Chrome card, pass-chip in DOM).

## Z. UI guidance-matrix directive (brief 2026-10-30-ui-guidance-matrix; branch feature/ui-guidance-matrix; ledger docs/plans/GUIDANCE_MATRIX_UI.md)

- [x] Z0. Phase 0 recon + ledger: backend telemetry inventory + frontend gap audit. Files: `docs/plans/GUIDANCE_MATRIX_UI.md`, `.jcode/briefs/2026-10-30-ui-guidance-matrix.md`. Proof: ledger on disk; 2 sidecars (guppy/frontend, humpback/backend) on route-pinned `meta-muse:muse-spark-1.3-contributor`; baseline gate 615 passed.
- [x] Z1. RED tests fail-first: `tests/test_ui_guidance.py` 9 contracts. Proof: 8 failed/1 passed pre-change (functional absences), 9 passed post-change, no weakening.
- [x] ZA. Subsystem A split routes: `#/` landing + `#/demo` + `#/live` views, hash router + mode sync, shared core single-mounted. Files: `static/index.html`, `static/app.js` (`currentRoute/applyRoute/bootRoutes`). Proof: RED route tests green; CDP operate-proof (mode_after_live=project).
- [x] ZB. Subsystem B graph engine: `static/graph.js` SMSGraph canvas-2D force layout, team colors green/red/blue/purple + particles + freeze, timeline strip fallback. Files: `static/graph.js`, `static/index.html` (`#phase-graph` + script), `static/app.js` (stage/result feed). Proof: RED graph tests green; node --check OK; graph_fallback=false live with strip mounted.
- [x] ZC. Subsystem C HUD: `#scoreboard` (agents/vulns/patches/verified) + 7 capability toggles wired to existing surfaces + terminal semantics kept. Files: `static/index.html`, `static/app.js` (`renderScoreboard`, HUD wiring). Proof: RED HUD tests green; dashboard suites 39 passed; CDP toggle-flip PASS.
- [x] Z2. Full gate + live Docker + browser matrix + docs/version: `dev.py check` 624 passed, `offline_scan` 3/3 verified, `ui_scan` Chrome+Firefox cards, CDP operate-proof (routes, graph, toggles, terminal semantics), TRAPS entry added, `browser_controls_check.py` harness fixed (see T1), version 0.8.0 LAW 12 major. Files: `static/index.html`, `static/graph.js`, `static/app.js`, `tests/test_ui_guidance.py`, `docs/TRAPS.md`, `docs/plans/GUIDANCE_MATRIX_UI.md`. Proof: gate 624 + live DOM PASS + merged feature/ui-guidance-matrix -> develop (988f06d) -> main (406d23a) shipped as 0.8.0.

## AA. 30-wave ascendancy missile (brief 2026-10-30-ascendancy-missile; branch feature/30-wave-ascendancy; ledger .jcode/briefs/30_wave_matrix.md; target 9.20 -> 9.50+)

- [x] AA0. Wave 1 survey: 10 read-only agents (sweep arch, telemetry data, web UI, CLI/TUI, MCP surface, ingest reuse, test gate, receipt proof, prompt logic, version/health). Baseline `dev.py check` exit 0 pre-change. Files: `.jcode/briefs/2026-10-30-ascendancy-missile.md`, `.jcode/briefs/30_wave_matrix.md`. Proof: gate log exit 0; 10 reports on record.
- [ ] AA1. Wave 2 RED tests fail-first (LAW 9): one new `*_red.py` per agent, brand-new non-overlapping files, verified FAIL for functional reason before any implementation.
- [x] AA1. Wave 2 RED outcome: 10 files, 44 failed / 0 passed, every failure a functional absence (verified per-file by spawner). Spawner form-fix: guarded imports + `test_*_module_exists` gate (LAW 9B clean, trap in TRAPS.md). Files: `tests/test_*_red.py` (10 new). Proof: per-file pytest audit; commit `fff7a7d`.
- [x] AA2. Wave 3 tribunal (mod-3, codegen halted): 60-point scoring — S1 8.70, 2a 6.80, 2b 7.35, 2c 8.65, 2d 6.85, S3 7.95; weighted **7.32**, Δ 2.18 to 9.5. Honest 9.2-aspirational note recorded. Task vectors for Waves 4–6 set. Proof: matrix ledger + commit `77e475e`.
- [ ] AA3. Wave 4 implementation (tribunal vectors): 3 writers in isolated worktrees (ingest backend / chain prompts / mcp status tool) turning 19 RED tests green; 7 read-only support maps. No merge until gate green on each branch.
- [x] AA3. Wave 4 outcome: 3 worktrees merged (cc68c19 ingest, 5ea8821 chain, mcp-status auto-merge). 23 RED green, verified in-worktree + post-merge. Regression: test_sweep_pass_ids_ordered 3→4-tuple (RED spec supersedes; shape unchanged). Lint clean. Gate 650 passed / 21 Wave-6 REDs pending. Commit `efca9f4`. Worktrees removed.
- [ ] AA4. Wave 5 HARD GATE (mod-5): dev.py check scope (REDs fail gate — run with Wave-6 deselect) + offline_scan 3/3 Docker + ui_scan Firefox AND Chrome. Any failure → Wave 6 regression-only.
- [x] AA4. Wave 5 outcome (HARD GATE PASS): unit 650 passed (21 Wave-6 REDs deselected, contract-pending); offline_scan 3/3 verified cleanup=True; ui_scan Chrome boundary-passed; Firefox boundary-passed on retry (first run: WebDriver querySelector null on data-mode click — headless-Ff render race, pre-existing harness timing, no app change; trap candidate). No Wave-6-regression-only needed. Proof: gate logs + scan cards.
- [ ] AA5. Wave 6 implementation (tribunal vectors): sweep telemetry aggregator + vault novel/known (sweep.py); receipt chain (workflow.py, sms_api.py); HUD event builders (sms_api.py); demo client (scripts/mcp_client_demo.py); dashboard HUD (app.js/index.html + LAW-11 matrix); TUI ingest key + telemetry tokens (tui.py, sms_cli.py). All RED→green, then full gate.
- [x] AA5. Wave 6 outcome: 3 worktrees merged (d990aa7 telemetry 8 RED, 9666e8c receipt 4 RED, 53f8ec8 HUD/demo 9 RED; spawner resolved sms_api.py conflict keeping both). Full gate 671 passed, ruff+format clean. Version 0.9.0 LAW-12 major (4 surfaces). Live Docker 3/3 verified on 0.9.0 tree. Proof: offline_scan log; commit `de4c253`.
- [ ] AA6. Wave 6 TRIBUNAL (mod-3): re-score 60-point matrix on 0.9.0 tree, compute Δ, set Waves 7–9 vectors.
- [x] AA6. Wave 6 tribunal: weighted **8.17** (was 7.32, +0.85 implementation delta). Vectors set. Proof: matrix + commit `5af4f5e`.
- [x] AA7. Wave 7 outcome: 3 worktrees merged (fc3f2e8 demo E2E, 311c543 ingest UI, a0fb77e receipt badge; 13 RED green). Gate 684 passed, lint clean. Chrome + Firefox cards show chain badge live. Worktrees removed.
- [ ] AA8. Wave 8 implementation: runtime auto-detect (fixes 2a-3); vault perf micro-benchmark + docs (2c-4); TUI ingest live proof + CLI --stats (2d-6/7).
- [x] AA8. Wave 8 outcome: 3 worktrees merged (849b658 runtime detect, 05a7178 vault perf, bc3f9a5 TUI stats). Gate 708 passed, format fixed whitespace-only. Worktrees removed. Commit `8455d1c`.
- [ ] AA9. Wave 9 TRIBUNAL (mod-3): re-score 60-point matrix on 708-green tree, compute Δ, set Wave 10 crucible + gate plan.
- [x] AA9. Wave 9 tribunal: weighted **8.34** (was 8.17, +0.17 evidence depth). Proof: matrix + commit.
- [x] AA10. Wave 10 outcome (HARD GATE PASS + WILD CRUCIBLE CONDITIONAL PASS): dev.py check exit 0, 708 passed; Docker 3/3 verified; Chrome + Firefox cards green. Crucible: command-injection demo repo cloned in-container only, spec/detect/cleanup proven, oracle green; keyed sweep deferred (no creds). Files: `docs/WILD_INGESTION_LOG.md`, `docs/TRAPS.md` (tmpfs/cp trap). No Wave-11-regression-only needed.
- [x] AA11. Wave 11 outcome (KEYED LIVE PROOF 3/3): all fixtures boundary-passed vs real Muse — node live 365→363 tokens, php 135→135, mysql 84→84; vault KNOWN_ARCHETYPE (red) on every card; chain broken (genesis) badges; Resources removed. Key + Docker both live. Closes tribunal 2b-3/2b-10/2d-10 live-evidence gaps.
- [x] AA12. Wave 12 tribunal: weighted **8.50** (was 8.34, +0.16 live depth). Vectors: fault drills (13), chain fixture (14), tribunal+gate (15). Proof: matrix + commit `45af1b7`.
- [ ] AA13. Wave 13 fault drills: RED-first tests pinning daemon-kill fail-closed + 429-throttle UI-alive; fault-injection harness (no prod behavior change).
- [x] AA13. Wave 13 outcome: 2 worktrees merged (cca96d6 daemon-fail-closed wrappers, 121af03 exhausted-429 named as rate limit; 9 RED green). Gate 717 passed, lint clean. Worktrees removed.
- [ ] AA14. Wave 14 chain fixture: two-link sink (single-step probe exits 1, chained exits 0) + live keyed chain-verdict proof.
- [x] AA14. Wave 14 outcome: writer drifted to 10 files, spawner narrowed to 5 (686d304) + spawner count fix (dcbe6c3). Chain single→chained flip proven in-worktree; offline 4/4 verified incl. new fixture. Merged f916592; gate 725 green. Worktree removed. Note: reverted TUI/web/smoke widening is follow-up ONLY if a future fixture touches those surfaces — nothing fails today.
- [ ] AA15. Wave 15 TRIBUNAL + HARD GATE (mod-3 and mod-5; gate takes precedence).
- [x] AA15. Wave 15 outcome: GATE GREEN (725, exit 0) then tribunal weighted **8.54** (was 8.50, +0.04 fault evidence). Movers: S3 daemon-fault + throttle bounds (6/7 → 8.0), 2b chain-verdict Docker proof (3 → 8.5). No Wave-16-regression-only needed. Proof: matrix.
- [ ] AA16. Wave 16 keyed chain sweep: live Muse red→blue→verify flip on node_chain_link.
- [x] AA16. Wave 16 outcome: KEYED CHAIN PROOF — node_chain_link boundary-passed vs live Muse (633→629 tokens), vault KNOWN_ARCHETYPE recall, chain row rendered, cleanup. Closes 2b-3 live gap: chained verdict fires with real synthesis.
- [ ] AA17. Wave 17 throttle/daemon UI banners: WS error event → visible dashboard banner (LAW 11 proof).
- [x] AA17. Wave 17 outcome: merged 16a46da (banner + 6 RED green); spawner format-only fix; gate 731 green. Worktree removed. Commit `4ba4271`.
- [ ] AA18. Wave 18 TRIBUNAL (mod-3).
- [x] AA18. Wave 18 outcome: tribunal weighted **8.58** (was 8.54, +0.04 keyed chain + banner). Movers: 2b-3 → 9.0 (real synthesis flip), S3-6/7 → 8.5 (banner render). Proof: matrix.
- [ ] AA19. Wave 19 banner operate-proof (LAW 11): trigger error path live both browsers.
- [x] AA19. Wave 19 outcome: BANNER PROVEN LIVE (Chrome): overlapping scans → second client got `type:busy` + close 1013 at protocol level; dashboard STATUS went red "Another scan is already running", #scan-banner rendered lock text, timeline carried refusal, first scan unaffected. Screenshot captured. Server torn down, zero leftovers. (Busy path needs no LAW-12 bump — render-only of Wave-17 work.)
- [ ] AA20. Wave 20 HARD GATE + WILD CRUCIBLE #2 (keyed wildcard sweep).
- [x] AA20. Wave 20 outcome: GATE GREEN (dev.py check exit 0) + CRUCIBLE #2 FULL PASS — keyed wildcard sweep: staged in Docker, RED CWE-78 at exact sink line, PRE-PROBE 0, BLUE allowlist patch, cleanup ok, zero leftovers. Shim note (input() blocks readiness → HTTP shim, sink verbatim) logged. Files: `docs/WILD_INGESTION_LOG.md`.
- [ ] AA21. Wave 21 TRIBUNAL (mod-3).
- [x] AA21. Wave 21 outcome: tribunal weighted **8.70** (was 8.58, +0.12 crucible #2 + banner live). Movers: 2a real-repo keyed sweep (1→8.0, 2→9.0), 2d busy-banner live (4→8.5), S3 render half (6→8.5). Proof: matrix.
- [ ] AA22. Wave 22 ingest submit wiring (form → project workflow → sweep, RED-first + live proof).
- [x] AA22. Wave 22 outcome: writer routing merged (32aee83) + spawner completion (78874b9: real clone=True staging, sandbox adapter, file_list forwarding; 21 RED green). Live proof: validation → staging → compress → vault NOVEL → baseline passed → red review (real Muse) → cleanup; full green needs server-shaped staged tree (recorded). Gate 752 green. Worktree removed.
- [ ] AA23. Wave 23 Tailwind decision (migrate or document + pin).
- [ ] AA24. Wave 24 TRIBUNAL (mod-3).

