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

- [.] I1. Green builder: "What do you want to build?" + "Vulnerabilities to
      implement" dashboard prompts (CVE ids, named types, or free text).
      Files: `static/index.html`, `static/app.js`, `main.py` (`run_demo_build`).
      Proof: UI scan showing both prompts; WS carries both fields.
- [ ] I2. Intent interpreter: green/research agents parse the vuln field into
      CVE ids vs named types vs free text and plan research accordingly.
      Files: `demo_gen.py` (new `parse_build_intent`), tests.
      Proof: unit test on mixed input ("CVE-2024-3094, sqli, weird header thing").
- [ ] I3. CVE endpoint series for green/research: NVD + OSV + GHSA already
      keyless; add CIRCL CVE lookup + EPSS scoring per CVE id so builders see
      severity/context. Files: `intel_search.py`, `research.py`, tests.
      Proof: live keyless fetch of a known CVE id with EPSS score attached.
- [ ] I4. Real web search for green/research: keyless, bot-tolerant web
      endpoint (no scraping wars) for named types + free text, same
      never-raises + caps discipline as `research.py`. Files: new
      `web_search.py` or extended `research.py`, tests with canned fixtures.
      Proof: canned test + one live probe.
- [ ] I5. Green prompt upgrade: Greenhouse system prompt consumes build
      intent + CVE records + web notes and implements the requested flaws.
      Files: `demo_gen.py` (`DEMO_GEN_SYSTEM_PROMPT` + payload), tests.
      Proof: offline generation test with canned intel shows requested vuln class.
- [ ] I6. Research sidecar upgrade: red/blue digests consume the same
      CVE + web context for grounding. Files: `prompts.py`, `agents.py`,
      `workflow.py` (`_gather_research`), tests. Proof: digest test with CVE context.
- [ ] I7. Small features that fall out: keep each cheap, tested, shippable
      (record here as they land).
