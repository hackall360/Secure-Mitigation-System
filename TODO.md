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
