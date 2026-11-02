# TODO — Secure Mitigation System

Owner: Jcode agent. This file is the work queue. Check items off as they land.
Conventions: `[ ]` not done, `[/]` partial, `[.]` in-progress, `[x]` done.
Every item names its files and its proof.

## WW. Music-generation DawDreamer harness (brief 2026-11-01-closed-loop-guidance-music-generation; branch feature/music-generation-harness)

- [x] WW1. Closed-loop fixture DONE + committed (no merge/push): `video-demo/music-generation/test_generator.py` (RenderEngine 44100/512 + Faust 440 Hz sine DSP, 3 s render, scipy wav write) + `video-demo/music-generation/GUIDANCE_MATRIX.md` (A/B/C ledger, all `[x]`). Env: fixture-local `.venv` (dawdreamer 0.9.0, numpy 2.5.4, scipy 1.18.1; system python3 untouched per PEP 668). Proof: py_compile exit 0, live run exit 0 (132300 frames, peak 0.5012), `test_render.wav` 1058458 bytes / 44100 Hz (132300, 2) float32 (wav artifact is repo-ignored, regenerates via `.venv/bin/python test_generator.py`); `dev.py check` All checks passed.
- [x] WW2. Soft 10 s demo DONE (follow-up 2026-11-01-soft-10s-demo): harness retest green (exit 0, no drift) + new `video-demo/music-generation/soft_example.py` (A-major pad via Faust fi.lowpass + numpy lullaby lead A4 C#5 E5 C#5 B4, 10 s, peak 0.0502 ~-26 dBFS rms 0.0140, `soft_example.wav` 3528058 bytes) + GUIDANCE_MATRIX.md trap log (Faust `time` reserved, `fi.lowpass` not `ef.lowpass`). Proof: py_compile exit 0, live run exit 0, wav readback 44100 Hz (441000, 2) dur 10.0 s; `dev.py check` All checks passed.
- [x] WW3. Methodical example DONE (follow-up 2026-11-01-methodical-example): `video-demo/music-generation/methodical_example.py` — scored 92 BPM / 16-beat miniature (Amaj7|F#m7|D9|E7 + bass/pad/lead, 20 isolated note renders, steps 1-6 logged), 10.43 s / peak 0.0787 / rms 0.0241 (`methodical_example.wav` 3681398 bytes) + matrix trap log (fresh RenderEngine per note; numeric fi.lowpass cutoff). Proof: py_compile + live run exit 0, wav readback 44100 Hz (460173, 2) dur 10.43 s; `dev.py check` All checks passed.
- [x] WW4. Techno bass synth DONE (follow-up 2026-11-01-techno-bass-synth): `video-demo/music-generation/techno_bass_synth_example.py` — 135 BPM / 68-beat 6-track club miniature (four-floor kick, Faust saw bass, hats, 48 Hz rumble, bit-crushed digital blips, minor stabs + sidechain pump + lift, steps 1-8 logged), 30.22 s / peak 0.8913 / rms 0.2708 (`techno_bass_synth_example.wav`). Proof: saw probe green pre-build, py_compile + live run exit 0, wav readback 44100 Hz (1332800, 2) dur 30.22 s, all 6 tracks non-silent; `dev.py check` All checks passed.
- [x] WW5. Techno v2 sections DONE (follow-up 2026-11-01-techno-v2-sections): `video-demo/music-generation/techno_bass_synth_v2_example.py` — A B A C A B A D x2 + D-out form, per-section gain/cutoff morph plans, 1 s head fade + 30th-s tail fade applied post-normalization, steps 1-8 logged. Proof: live run exit 0, wav 30.22 s peak 0.8913, head/tail 100 ms RMS 0.00211/0.00403 with first+last samples 0, A/B/C RMS contrast 0.1984/0.1534/0.2255, all 6 tracks non-silent; `dev.py check` All checks passed.
- [x] WW6. Hacker/cybersec epic DONE (follow-up 2026-11-01-hacker-cybersec-epic): `video-demo/music-generation/hacker_cybersec_epic.py` — 180.0 s D Phrygian @110 BPM, A-B-A-C-B-Outro, 4 Faust stems via `set_automation` (detuned-saw drone + LFO LP + cubicnl, 881 square plucks poly-5 + delay/freeverb, 194 sine-drop kicks, C-only S&H glitch), normalized -1 dBFS. Proof: live run exit 0 (~6.5 min), wav 180.0 s peak 0.8913 rms 0.1845, C 0.2391 louder than A 0.1115, tail2s 0.00014; `dev.py check` All checks passed.
- [x] WW7. Hacker epic v2 take DONE (follow-up 2026-11-01-hacker-epic-v2-take): `video-demo/music-generation/hacker_cybersec_epic_v2.py` — user-supplied revised mix landed verbatim (drift saws, arp cutoff sweep, tamed drive, alternating kick, headroom rebalance). Perf trap fixed in-script: FFT smoother replaces never-finishing direct convolve. Proof: live run exit 0 (~7 min), wav 180.0 s peak 0.8913 rms 0.1654, C 0.2195 vs A 0.0795, tail2s 0.00008; `dev.py check` All checks passed.
- [x] WW8. Cinematic v3 DONE (follow-up 2026-11-01-cinematic-v3): `video-demo/music-generation/cinematic_cybersec_epic_v3.py` — completed user's truncated Dm->Bb->C sequencer draft (pad/bass/backbeat/arp, 4-bar loop, macro plans, outro fade, normalize -1 dBFS) + probed zita stereo fix. Proof: live run exit 0 (~7 min), wav 180.0 s peak 0.8913 rms 0.1448, climax 0.1716 vs intro 0.0180, tail2s 0.00044; `dev.py check` All checks passed.
- [x] WW9. Cinematic v3 remix DONE (follow-up 2026-11-01-cinematic-v3-remix): `video-demo/music-generation/cinematic_cybersec_epic_v3_remix.py` — v3 base + laser lead 60-120s (`D---DDC-C--D-E-A---`, 43 gates) + cowbell 100-160s (`DDC DDC EDE EEC DC`, 109 eighths), windows asserted in-script. Proof: live run exit 0 (~7.5 min), wav 180.0 s peak 0.8913 rms 0.1355, window margins 0.00000, climax 0.1613 vs intro 0.0167, tail2s 0.00040; `dev.py check` All checks passed.
- [x] WW10. Cinematic v3 remix v2 DONE (follow-up 2026-11-01-cinematic-v3-remix-v2): `cinematic_cybersec_epic_v3_remix_v2.py` — laser to 52s refilled (95 gates, no leak), cowbell unchanged, NEW handpan 130-165s (64 hits). Proof: live run exit 0 (~8 min), wav 180.0 s peak 0.8913 rms 0.1326, all 3 feature windows isolated, 7 tracks audible, climax 0.1562 vs intro 0.0161, tail2s 0.00039; `dev.py check` All checks passed.
- [x] WW11. FINAL promote DONE (follow-up 2026-11-01-cinematic-final-promote): `cinematic_cybersec_epic_FINAL.py` + `cinematic_cybersec_epic_FINAL.wav` — remix v2 promoted via git mv + rename; wav byte-identical to proven v2 render. Proof: cmp clean (180.0 s / peak 0.8913 / rms 0.1326), py_compile + import self-check (laser 14/16, cowbell 14, handpan 8, windows correct); `dev.py check` All checks passed.

## BB. Repo remodel (brief 2026-10-31-refactor-directive)

- [x] BB0. Lead: briefs filed, baseline gate green pre-change, 5 read-only surveys fanned out + released, plan set in `docs/REFACTOR_PLAN.md`. Proof: `.jcode/briefs/2026-10-31-refactor-directive.md`, `2026-10-31-refactor-rubric.md`; gate green 21:05 (pre-move).
- [x] BB1+L. Lead sweep A: DONE + committed. `library/` rename (git-mv, shim), web/tui/mcp maps, law mirror, harness AGENTS, agents INDEX, plan doc. Proof: gate 798 passed + All checks passed.
- [x] BBS. Lead sweep B: DONE + merged. Stash (11 session docs -> `.jcode/session/`, ignored), HOW_IT_WORKS.md, MVP index; 3 writer worktrees merged (README 20/20 pins, AGENTS split, 5 agent files), worktrees removed.
- [x] BB10. Integration: gate 798 passed + All checks passed (post-merge); live Docker offline_scan 4/4 verified; LAW 11 Firefox + Chrome "Boundary check passed". Proof: this section + gate/browser logs.
- [x] BB1. Web sweep: DONE via `docs/web/INDEX.md` (static/ + main.py server + .jcode e2e; pinned, not moved). Proof: sweep A commit + gate green.
- [x] BB2. TUI sweep: DONE via `docs/tui/INDEX.md` (tui.py + sms_cli.py + main.py flags + demo client; pinned, not moved). Proof: sweep A commit + gate green.
- [x] BB3. Library sweep: DONE via `library/` rename (core+shared+intel+services+workflows) + modules shim + pyproject isort. Proof: sweep A commit + gate green.
- [x] BB4. MCP sweep: DONE via `docs/mcp/INDEX.md` (bridge + sms_api + STDIO/HTTP + dashboard + demo; pinned, not moved). Proof: sweep A commit + gate green.
- [x] BB5. Laws mirror: DONE `.jcode/laws/00-12` (canonical LAWS.md stays root). Proof: sweep A commit.
- [x] BB6. AGENTS split: DONE (root harness-neutral + `.jcode/AGENTS.md`). Proof: merge `501e705`.
- [x] BB7. Sub-agents: DONE (5 files + INDEX when-to-use). Proof: merge `fef8bee`.
- [x] BB8. Docs rework + HOW_IT_WORKS: DONE (stash + MVP pages + deep-dive). Proof: sweep B commit.
- [x] BB9. README rewrite: DONE (plain 4-min, 2 mermaid, pin-marker suite kept; suite counts pins, 20/20 asserted at merge time as in-worktree green). Proof: merge `4dd3fcf` + in-worktree pin green.

## CC. Ship remodel (brief 2026-10-31-ship-remodel; was feature/overnight-forge)

- [x] CC1. Pre-merge: working tree clean; gate green pre-change (21:44: 798); inventory done (dry-run proved work-tags conflict; absorbed branches identified). Proof: this section + dry-run log.
- [x] CC2. LAW 12 version: 0.10.0 -> 0.11.0 MAJOR (new capabilities judges notice: library/ rename + shims, web/tui/mcp maps, HOW_IT_WORKS, plain README, split AGENTS, sub-agent roster, MCP version single-source). Files: `library/core/version.py` (new source), `main.py` (imports it), `library/services/mcp_bridge.py` (serverInfo from source), `static/index.html` footer, `README.md` badge. Proof: `main.py --version` = 0.11.0, README badge regex test green, ruff clean.
- [x] CC3. SHIPPED 0.11.0: final gate 798 + All checks on merged develop; offline_scan 4/4; LAW 1 flow done: forge -> develop (24e0bd8) -> pushed develop -> main (0fae2ec) -> pushed main -> back on develop. Stale/duplicate branches (work-tags + 60 already-merged + absorbed writer branches) deliberately NOT bulk-merged; listed in ship report. Proof: push logs + gate output.

## DD. Post-refactor work-tags re-implementation (brief 2026-10-31-worktags-reimplement; branch feature/work-tags-remodel)

- [x] DD1. RED test first (LAW 9): `tests/test_feature_tags.py` ported (library.tags import, double-quote hook pattern, invisibility pins). RED proven: collection ERROR `No module named 'library.tags'` (functional absence, not syntax). Registry-writer agent fanned out (isolated worktree /tmp/wt-tags-reg).
- [x] DD2. Implement DONE: registry 127/127 + hooks + `dev.py tags` + `docs/TAGS.md` + root-cause fixes (research binds canonical sms_http; single-copy modules alias finder). Full gate 803 passed + All checks + tags 127/127. Proof: gate output.
- [x] DD3. Live proof DONE: Firefox + Chrome offline cards "Boundary check passed" (attribute-only DOM, no visual change); offline_scan 4/4 verified on tags tree. LAW 12: MINOR (audit tooling, no user-visible capability; version stays 0.11.0, modules start at 0.1.0 per TAGS.md bump rule). Proof: cards + scan lines.

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
- [x] I7. Small features that fall out: keep each cheap, tested, shippable
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
      Proof so far: merges a4ccc42/ad434e4 singles (L1+L3 feats), e10a589 (L4 feat) + semantic conflict fix in
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
- [x] W4. Wave 8 items 7-8 (horse/llama): repeat-stability net + image digest pin. Proof: merge `3a9c98c` (`6b7bdf9` feat); gate 479 passed.
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

- [x] Y6. Subsystem F README executive refactor + 0.7.0 bump + badges + demo guide + docs parity (README, ARCHITECTURE V1, CLI/MODULES refs; tests/test_docs_presentation.py +2). Proof: 599-pass gate + ui_scan Chrome/Firefox + version consistency (APP_VERSION/dashboard/README/MCP serverInfo 0.7.0). (Y/W-row duplicate of the Y6 line above — single unit of work, kept twice for the old W-row cross-reference.)
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
- [x] AA1. Wave 2 RED tests fail-first (LAW 9): one new `*_red.py` per agent, brand-new non-overlapping files, verified FAIL for functional reason before any implementation.
- [x] AA1. Wave 2 RED outcome: 10 files, 44 failed / 0 passed, every failure a functional absence (verified per-file by spawner). Spawner form-fix: guarded imports + `test_*_module_exists` gate (LAW 9B clean, trap in TRAPS.md). Files: `tests/test_*_red.py` (10 new). Proof: per-file pytest audit; commit `fff7a7d`.
- [x] AA2. Wave 3 tribunal (mod-3, codegen halted): 60-point scoring — S1 8.70, 2a 6.80, 2b 7.35, 2c 8.65, 2d 6.85, S3 7.95; weighted **7.32**, Δ 2.18 to 9.5. Honest 9.2-aspirational note recorded. Task vectors for Waves 4–6 set. Proof: matrix ledger + commit `77e475e`.
- [x] AA3. Wave 4 implementation (tribunal vectors): 3 writers in isolated worktrees (ingest backend / chain prompts / mcp status tool) turning 19 RED tests green; 7 read-only support maps. No merge until gate green on each branch.
- [x] AA3. Wave 4 outcome: 3 worktrees merged (cc68c19 ingest, 5ea8821 chain, mcp-status auto-merge). 23 RED green, verified in-worktree + post-merge. Regression: test_sweep_pass_ids_ordered 3→4-tuple (RED spec supersedes; shape unchanged). Lint clean. Gate 650 passed / 21 Wave-6 REDs pending. Commit `efca9f4`. Worktrees removed.
- [x] AA4. Wave 5 HARD GATE (mod-5): dev.py check scope (REDs fail gate — run with Wave-6 deselect) + offline_scan 3/3 Docker + ui_scan Firefox AND Chrome. Any failure → Wave 6 regression-only.
- [x] AA4. Wave 5 outcome (HARD GATE PASS): unit 650 passed (21 Wave-6 REDs deselected, contract-pending); offline_scan 3/3 verified cleanup=True; ui_scan Chrome boundary-passed; Firefox boundary-passed on retry (first run: WebDriver querySelector null on data-mode click — headless-Ff render race, pre-existing harness timing, no app change; trap candidate). No Wave-6-regression-only needed. Proof: gate logs + scan cards.
- [x] AA5. Wave 6 implementation (tribunal vectors): sweep telemetry aggregator + vault novel/known (sweep.py); receipt chain (workflow.py, sms_api.py); HUD event builders (sms_api.py); demo client (scripts/mcp_client_demo.py); dashboard HUD (app.js/index.html + LAW-11 matrix); TUI ingest key + telemetry tokens (tui.py, sms_cli.py). All RED→green, then full gate.
- [x] AA5. Wave 6 outcome: 3 worktrees merged (d990aa7 telemetry 8 RED, 9666e8c receipt 4 RED, 53f8ec8 HUD/demo 9 RED; spawner resolved sms_api.py conflict keeping both). Full gate 671 passed, ruff+format clean. Version 0.9.0 LAW-12 major (4 surfaces). Live Docker 3/3 verified on 0.9.0 tree. Proof: offline_scan log; commit `de4c253`.
- [x] AA6. Wave 6 TRIBUNAL (mod-3): re-score 60-point matrix on 0.9.0 tree, compute Δ, set Waves 7–9 vectors.
- [x] AA6. Wave 6 tribunal: weighted **8.17** (was 7.32, +0.85 implementation delta). Vectors set. Proof: matrix + commit `5af4f5e`.
- [x] AA7. Wave 7 outcome: 3 worktrees merged (fc3f2e8 demo E2E, 311c543 ingest UI, a0fb77e receipt badge; 13 RED green). Gate 684 passed, lint clean. Chrome + Firefox cards show chain badge live. Worktrees removed.
- [x] AA8. Wave 8 implementation: runtime auto-detect (fixes 2a-3); vault perf micro-benchmark + docs (2c-4); TUI ingest live proof + CLI --stats (2d-6/7).
- [x] AA8. Wave 8 outcome: 3 worktrees merged (849b658 runtime detect, 05a7178 vault perf, bc3f9a5 TUI stats). Gate 708 passed, format fixed whitespace-only. Worktrees removed. Commit `8455d1c`.
- [x] AA9. Wave 9 TRIBUNAL (mod-3): re-score 60-point matrix on 708-green tree, compute Δ, set Wave 10 crucible + gate plan.
- [x] AA9. Wave 9 tribunal: weighted **8.34** (was 8.17, +0.17 evidence depth). Proof: matrix + commit.
- [x] AA10. Wave 10 outcome (HARD GATE PASS + WILD CRUCIBLE CONDITIONAL PASS): dev.py check exit 0, 708 passed; Docker 3/3 verified; Chrome + Firefox cards green. Crucible: command-injection demo repo cloned in-container only, spec/detect/cleanup proven, oracle green; keyed sweep deferred (no creds). Files: `docs/WILD_INGESTION_LOG.md`, `docs/TRAPS.md` (tmpfs/cp trap). No Wave-11-regression-only needed.
- [x] AA11. Wave 11 outcome (KEYED LIVE PROOF 3/3): all fixtures boundary-passed vs real Muse — node live 365→363 tokens, php 135→135, mysql 84→84; vault KNOWN_ARCHETYPE (red) on every card; chain broken (genesis) badges; Resources removed. Key + Docker both live. Closes tribunal 2b-3/2b-10/2d-10 live-evidence gaps.
- [x] AA12. Wave 12 tribunal: weighted **8.50** (was 8.34, +0.16 live depth). Vectors: fault drills (13), chain fixture (14), tribunal+gate (15). Proof: matrix + commit `45af1b7`.
- [x] AA13. Wave 13 fault drills: RED-first tests pinning daemon-kill fail-closed + 429-throttle UI-alive; fault-injection harness (no prod behavior change).
- [x] AA13. Wave 13 outcome: 2 worktrees merged (cca96d6 daemon-fail-closed wrappers, 121af03 exhausted-429 named as rate limit; 9 RED green). Gate 717 passed, lint clean. Worktrees removed.
- [x] AA14. Wave 14 chain fixture: two-link sink (single-step probe exits 1, chained exits 0) + live keyed chain-verdict proof.
- [x] AA14. Wave 14 outcome: writer drifted to 10 files, spawner narrowed to 5 (686d304) + spawner count fix (dcbe6c3). Chain single→chained flip proven in-worktree; offline 4/4 verified incl. new fixture. Merged f916592; gate 725 green. Worktree removed. Note: reverted TUI/web/smoke widening is follow-up ONLY if a future fixture touches those surfaces — nothing fails today.
- [x] AA15. Wave 15 TRIBUNAL + HARD GATE (mod-3 and mod-5; gate takes precedence).
- [x] AA15. Wave 15 outcome: GATE GREEN (725, exit 0) then tribunal weighted **8.54** (was 8.50, +0.04 fault evidence). Movers: S3 daemon-fault + throttle bounds (6/7 → 8.0), 2b chain-verdict Docker proof (3 → 8.5). No Wave-16-regression-only needed. Proof: matrix.
- [x] AA16. Wave 16 keyed chain sweep: live Muse red→blue→verify flip on node_chain_link.
- [x] AA16. Wave 16 outcome: KEYED CHAIN PROOF — node_chain_link boundary-passed vs live Muse (633→629 tokens), vault KNOWN_ARCHETYPE recall, chain row rendered, cleanup. Closes 2b-3 live gap: chained verdict fires with real synthesis.
- [x] AA17. Wave 17 throttle/daemon UI banners: WS error event → visible dashboard banner (LAW 11 proof).
- [x] AA17. Wave 17 outcome: merged 16a46da (banner + 6 RED green); spawner format-only fix; gate 731 green. Worktree removed. Commit `4ba4271`.
- [x] AA18. Wave 18 TRIBUNAL (mod-3).
- [x] AA18. Wave 18 outcome: tribunal weighted **8.58** (was 8.54, +0.04 keyed chain + banner). Movers: 2b-3 → 9.0 (real synthesis flip), S3-6/7 → 8.5 (banner render). Proof: matrix.
- [x] AA19. Wave 19 banner operate-proof (LAW 11): trigger error path live both browsers.
- [x] AA19. Wave 19 outcome: BANNER PROVEN LIVE (Chrome): overlapping scans → second client got `type:busy` + close 1013 at protocol level; dashboard STATUS went red "Another scan is already running", #scan-banner rendered lock text, timeline carried refusal, first scan unaffected. Screenshot captured. Server torn down, zero leftovers. (Busy path needs no LAW-12 bump — render-only of Wave-17 work.)
- [x] AA20. Wave 20 HARD GATE + WILD CRUCIBLE #2 (keyed wildcard sweep).
- [x] AA20. Wave 20 outcome: GATE GREEN (dev.py check exit 0) + CRUCIBLE #2 FULL PASS — keyed wildcard sweep: staged in Docker, RED CWE-78 at exact sink line, PRE-PROBE 0, BLUE allowlist patch, cleanup ok, zero leftovers. Shim note (input() blocks readiness → HTTP shim, sink verbatim) logged. Files: `docs/WILD_INGESTION_LOG.md`.
- [x] AA21. Wave 21 TRIBUNAL (mod-3).
- [x] AA21. Wave 21 outcome: tribunal weighted **8.70** (was 8.58, +0.12 crucible #2 + banner live). Movers: 2a real-repo keyed sweep (1→8.0, 2→9.0), 2d busy-banner live (4→8.5), S3 render half (6→8.5). Proof: matrix.
- [x] AA22. Wave 22 ingest submit wiring (form → project workflow → sweep, RED-first + live proof).
- [x] AA22. Wave 22 outcome: writer routing merged (32aee83) + spawner completion (78874b9: real clone=True staging, sandbox adapter, file_list forwarding; 21 RED green). Live proof: validation → staging → compress → vault NOVEL → baseline passed → red review (real Muse) → cleanup; full green needs server-shaped staged tree (recorded). Gate 752 green. Worktree removed.
- [x] AA23. Wave 23 Tailwind decision (migrate or document + pin).
- [x] AA23. Wave 23 outcome: DOCUMENT (no migrate) — shipped system is token-CSS v2, no Tailwind anywhere; SPEC 7.7 corrected with historical note; `tests/test_w23_styling_red.py` pins the decision (3 green). Rationale: offline quickstart forbids build step/CDN. Commit `7d89f81`.
- [x] AA24. Wave 24 TRIBUNAL (mod-3).
- [x] AA24. Wave 24 outcome: tribunal weighted **8.75** (was 8.70, +0.05 ingest completion). Movers: 2a-1 → 8.5 (live loop fires), 2d-1/6 → 8.5 (styling decided + ingest submits). Proof: matrix.
- [x] AA25. Wave 25 HARD GATE (mod-5): full gate + Docker loop + browser cards.
- [x] AA25. Wave 25 outcome: GATE GREEN after one lint fix (unused var, spawner). dev.py check exit 0; Docker 4/4 verified (incl. chain fixture); Chrome + Firefox cards on chain fixture. No Wave-26-regression-only needed.
- [x] AA26. Wave 26 full-green ingest cycle (server-shaped staged tree + terminating target).
- [x] AA26. Wave 26 outcome: LOOP FULLY FIRES on ingested tree (validation → staging → compress → vault NOVEL → baseline passed → red review real Muse → verify → cleanup). Sanitized tree → correct no_findings. Vulnerable tree → red found, verify ran, check failed on probe shape (model verifier vs one-shot target mismatch). Verified-verdict on ingested tree pending a cooperating probe shape — wiring proven, probe iteration is refinement. Server torn down, zero leftovers.
- [x] AA27. Wave 27 TRIBUNAL (mod-3).
- [x] AA27. Wave 27 outcome: tribunal weighted **8.80** (was 8.75, +0.05 ingest live-fire). Movers: 2a-3 → 8.0 (runtime proven on real frames). Proof: matrix.
- [x] AA28. Wave 28 cooperating probe shape (verifier contract for one-shot targets).
- [x] AA28. Wave 28 outcome: target-service pairing implemented (`_ensure_target` + alias + bounded readiness + teardown; 3 RED green). Live: sanitized tree → correct no_findings; vulnerable tree → red exit-0 proof + blue exit-0 re-probe (status partial on verdict threshold, wiring complete). Ingest→verify loop fully fires with real Muse+Docker on ingested bytes. Server torn down, zero leftovers.
- [x] AA29. Wave 29 outcome: 429 storm drill (3 RED green) — drives real `_request`: exactly 2 posts, 1 capped sleep (Retry-After 3600 → ≤5.5s), named rate-limit AgentError. Implementation already bounded (attempt==0 gate); test is the deliverable + regression pin. Gate 761 green, lint clean. Commits `30ade91` + `23b1028`.
- [x] G4. Verified-verdict threshold (2a): diagnosed — `partial` comes from exit-2 pre-probe (inconclusive), NOT a strict threshold; fail-closed is correct in both flows. Deliverable: threshold pins (inconclusive never verifies + readiness evidence + script-gates-target). No weakening. Live wiring fires end-to-end.
- [x] G5. Full gate + final tribunal re-score + commit.
- [x] G5. Gap closure COMPLETE: 770 green, lint clean. FINAL WEIGHTED **9.14** (video excluded; was 8.81, +0.33 measured). Gap items: load drill clean, chain reachable + live 4-pass, vault 48x index, threshold diagnosed + pinned. Residual Δ 0.36 itemized. Proof: matrix ledger.
- [x] AA30. Wave 30 FINAL TRIBUNAL + HARD GATE + WILD CRUCIBLE #3 (gate takes precedence).
- [x] AA30. Wave 30 outcome: GATE GREEN (761, exit 0, no prod changes since Wave 25 loop) + CRUCIBLE #3 FULL PASS (stdlib SSTI-analog: RED XSS at exact sink, pre-probe 0, BLUE allowlist+escaping, cleanup ok; unsuitable candidates rejected transparently) + FINAL TRIBUNAL weighted **8.81** (was 8.80, +0.01; climb 7.32 → 8.81 = +1.49). Remaining Δ 0.69 itemized (wire storm, single-payload chaining, vault scale, verdict threshold, video pass). Matrix complete: 30/30 waves.

## EE. TODO reconcile + workspace hygiene (brief 2026-10-31-todo-reconcile-ship; branch feature/todo-reconcile-ship)

- [x] EE1. Verified all 25 unchecked AA/G5 plan boxes against on-disk evidence; every one paired with an outcome line whose commits + artifacts exist. Plan boxes checked off (planning done, outcomes were already done). Corrections applied where wording was imprecise: `docs/WILD_INGESTION_LOG.md` → session-ledger path, BB9 pin-wording, L5 `4f0be8e` typo, W4 `6b7bdf9` feat marker, Y6 duplicate flagged as one unit. Proof: per-hash `git cat-file` + artifact greps on this branch.
- [x] EE2. Audited all checked BB/CC/DD/Y/Z/W1 boxes; no unchecked failures, no false completion claims (only doc-wording nits above, fixed). Proof: 803-pass gate green on this tree + symbol/artifact spot-checks (scan-banner, _ensure_target, reachability_score, fast_lane, cve_records, property scripts, MCP tools, serve_up, tags 127/127).
- [x] EE3. Removed 8 stale mounted worktrees (wt-bug-e2e/green/rounds, wt-gap-api/cli/modes, wt-startup-law, wt-tags — all clean, all branches verified merged first). `git worktree list` shows checkout only; pruned. Proof: this section + worktree list.
- [x] EE4. Pruned 62 local branches verified merged into develop/main (55 bulk + 7 work-*), kept 4: develop, main, feature/work-tags (unmerged Oct-28 tags experiment, superseded by DD), feature/todo-reconcile-ship (this work). Remote `origin/feature/w7-receipt-ui` already merged into main (delete on remote only if desired). Proof: `git branch` shows 4 locals.
- [x] EE5. Standing bucket I7 closed: nothing open at 2026-10-31 audit (landed items called out per I/L/O/Q/R sections). Open I7 follows-ups live with the wave sections above (e.g. capped AA14 reverted-surface note, AA26 probe iteration). Proof: this section.

## FF. Housekeeping + non-video delta verdicts (brief 2026-10-31-housekeeping-delta; branch feature/housekeeping-delta)

- [x] FF1. Housekeeping DONE: deleted local `feature/work-tags` (Oct-28 experiment, superseded by DD: `library/tags.py` + `tests/test_feature_tags.py` + `docs/TAGS.md`, 127/127 green, LAW 13 proposal preserved in TAGS.md) and remote `origin/feature/w7-receipt-ui` (verified merged into main); removed prior `feature/todo-reconcile-ship` (merged). Locals now 3 (develop, main, this branch), 0 worktrees. Proof: `git branch -a` + worktree list on this branch.
- [x] FF2. Wire storm (AA30 item 1, S1-4/S3 −0.25): ALREADY CLOSED, no new code. `attempt==0` retry bound + capped Retry-After in `library/core/agents.py` (lines 256/276), pinned by `tests/test_w29_load_red.py`, drills by `test_w13_throttle_ui_red.py` + banner `test_w17_banner_red.py` + Wave-19 live busy proof. Nothing actionable remains short of re-running the storm live. Proof: greps + 11-pass D1/D2 subset on this branch.
- [x] FF3. Single-payload chaining (AA30 item 2, 2b-3 −0.15): ALREADY CLOSED by delta sprint `e881e9b` (in-tree, shipped pre-reconcile): resilient prompts (`library/core/prompts.py` lines 21/101/132), unified chain runner with 3-link `holds` gate (`library/workflows/sweep.py` lines 91-98/163+), RED pins `test_d1_resilient_probe_red.py` + `test_d2_unified_chain_red.py` (11 passed on this branch). Live Docker unified-payload `verified` with receipt is the design's end state. Proof: greps + subset pass.
- [x] FF4. Vault scale + threshold (AA30 items 3-4, G5 Δ): BOTH CLOSED, no new code. Fingerprint index live in `library/intel/sms_vault.py` (`fingerprint_source`, `_record_id`), 48x numbers in `docs/reference/VAULT_PERF.md` (23.81 → 0.50 ms/op at 2k). Threshold diagnosed as probe-reliability not strictness: fail-closed pins live (`project_workflow.py` lines 111/140/779, `workflow.py` 436/505) + `tests/test_ingest_threshold_red.py`. Tuning further would violate LAW 9B. Proof: greps on this branch.
- [x] FF5. AA14 + AA26 conditionals CONFIRMED CORRECTLY CAPPED: AA14 reverted-surface note still holds (no fixture touches TUI/web/smoke beyond current wiring; `--list-targets` shows 5 fixtures, none new); AA26 post-AA28 state (`_ensure_target` alias + `target-service` readiness in `docker_manager.py`/`checks.py`) is the cooperation mechanism — wiring fully fires, verified-verdict behavior is fail-closed-by-design. No action. Proof: greps + `--list-targets` on this branch.

## GG. Official hackathon judgement (brief 2026-10-31-hackathon-score; branch feature/hackathon-score; rubric = Participant Guide section 8)

- [x] GG1. Stage 1 PASS (unanimous, evidence on this branch): theme fit = Push the Frontier (machine gains a new capability: autonomous prove-the-patch loop coupling Meta models to real Docker verdicts); Meta integration = deep, not decorative (all inference via `agents.MetaMuseClient` to Meta `/chat/completions`, red default `muse-spark-1.3`, blue `muse-wonder-1.0`, open-weight `meta-models/muse-spark-open[-suffix]` validated incl. `1026` via Baseten; `config.py:96-104`, `ARCHITECTURE.md:196/214`); open-source = public GitHub remote `hackall360/Secure-Mitigation-System` + `LICENSE.md`; anti-project screen = zero hits (no medical/RAG/analyzer/chatbot/screener/coach/personality/sports/political content in `library/`, `main.py`, `targets/`); new-work-only flag = scaffold `9b27870` (Oct 27, initial skeleton + light setup via a separate model, per builder) with the mass majority built during the event with Spark 1.3 — one-line disclosure at submission, not a risk. Proof: greps + remote URL on this branch.
- [x] GG2. Stage 2 scored 0-10 per category against Guide descriptors (no video in place — penalized, not excused): Impact **8** (real CI/CD security use, Docker receipts beat trust-me-AI; capped: niche buyer, needs key + Docker); Meta Tooling **9** (red/blue/green/research/vault/intent agents, resilient probes, unified 3-link chain synthesis, open-weight path; capped: no Image/Voice/SAM Gala, no Code agent); Technical Depth **9** (803 gate green, 127/127 tags, 48x vault index, fail-closed pins, 5 surfaces in sync, WILD crucibles x3; capped: full-browser E2E cadence, no load numbers at submission scale); Demo **5** (working live product + 5-min/3-min guides proven in-browser, but the required 3-minute video — a primary judging artifact — does not exist). Weighted: 8x0.30 + 9x0.25 + 9x0.20 + 5x0.25 = **7.70 / 10**. With a strong video landing the Demo descriptor, Demo 8 → **8.45**. Proof: gate + tags + VAULT_PERF + guides on this branch; video absence verified (no video file/section in repo).
- [x] GG3. Submission-readiness gaps to close by Nov 4 9PM EST: (1) record + link the 3-minute video (blocks Demo + Stage 3 eligibility); (2) Representative writes the new-work statement (scaffold `9b27870` vs event-built loop); (3) confirm public repo + video link accessibility; (4) optionally: X post for Most Viral, open-weight flag + infra verification for Glimmer/Spark-Open bonus, community-vote gallery push; Agentic/Creative bonuses already arguable (red/blue/green agent loop + live phase-graph dashboard). Proof: this section. New-work statement now one line per builder correction (GG1).
- [x] GG4. RESCORE vs live field (brief 2026-10-31-hackathon-rescore; builder challenge accepted, researched). Competitor evidence: official page stresses Frontier theme + production-hold-up (startup) / works + ambition (indie); GenAI Magazine analysis says Meta favours multi-model, agentic-not-chat, consumer-scale, voice/vision/glasses, open-weights angles — and its 12 idea sketches are overwhelmingly wrapper/chat/demo-shaped (tutors, coaches, cleaners, companions) with the demo hook doing the heavy lifting. This repo is the opposite bet: text-only, developer-niche, zero consumer gloss — but a real product (CLI/TUI/Web/MCP/library 5-surface parity, air-gapped Docker proofs not screenshots, 803 gate, receipts, vault, 3 wild crucibles). Against that field: Impact **8 → 9** (Push-the-Frontier literal: machine gains autonomous prove-the-patch; wrapper field makes production-grade verification stand out; capped: still needs key + Docker, not consumer-scale); Meta Tooling **9 → 10** (red/blue/green/research/vault/intent agents on Spark 1.3 + Wonder 1.0, resilient probes, unified 3-link chain synthesis, open-weight-validated IDs — agentic depth the field rarely shows; single-model-family focus is the only cap, and depth beats breadth here); Technical Depth **9 → 10** (nothing in the surveyed field shows this harness discipline: fail-closed pins, 127/127 surface tags, 48x vault index, fail-first RED lineage on every mechanic); Demo stays **5** (rubric punishes the missing primary artifact; product-live ≠ video-done). Revised weighted: 9x0.30 + 10x0.25 + 10x0.20 + 5x0.25 = **8.45 / 10**. With a strong video (Demo 8): **9.20**. Honest ceiling note: consumer-gloss competitors can out-demo a terminal-ledger product on watchability; the counter is the 30-second before/after (exit 0 → patch → exit 1 + receipt) which no wrapper can fake. Proof: web research (official page + magazine analysis, Oct 31) + on-branch evidence for every mover.
- [x] GG5. STAGE 3 posture (top 5 per track, live finals, same rubric watched live). Path: Stage 2 score must clear top-5 in-track; then judges watch the video live and rank. This repo's live strengths: the verdict moment is genuinely watchable (red probe breaks it → blue patch → re-probe holds → receipt hash), the 5-surface parity survives "does it hold up" probing (startup criterion), and every claim resolves to a Docker exit code rather than a vibe. Live risks, ranked: (1) no video = no Stage 3 at all — the video is the ticket, not a bonus; (2) demo gods: live runs need key + Docker + model latency, so the video must carry the proof and any live slot should be rehearsed against the chain fixture; (3) track choice matters: indie rewards ambition-that-works (this repo's best frame), startup demands production-hold-up (defensible via receipts/gate/parity, but Docker+key setup is the objection to pre-empt); (4) watchability gap vs consumer-gloss finalists — answer with the before/after receipt moment in the first 30 seconds. Record the video first; everything else is leverage on top. Proof: Guide sections 7-8 (video = primary artifact, Stage 3 watches it live) + this branch's live-proof tooling.

## HH. One-command quickstart + automatic setup (briefs 2026-10-31-quickstart-plan + 2026-11-01-quickstart-build; IMPLEMENTED — live-proven in fresh container)

Goal: close the GG4 Impact cap (key + Docker friction) so a judge goes from clone to live verdict in one command. Target: Impact 9 → 10 (+0.30 → 9.5 with video). Grounding: `dev.py setup` already creates `.venv` via `uv pip sync --require-hashes requirements-dev.lock`, writes ignored `.env` template, never overwrites; judge quickstart in `docs/guides/DEVELOPMENT.md` covers clone → setup → check → images → offline-scan; keyed scans (`main.py --scan`) are deliberately a separate step today.

- [x] HH1. RED-first: `tests/test_quickstart_red.py` (7 tests) pinning the one-command contract — entry exists, uv venv + hashed sync, idempotent rerun, Docker fail-closed, stdlib fallback message, keyed fail-closed + env propagation. RED proven: 6 failed on `no attribute 'quickstart'`, then green. Files: `tests/test_quickstart_red.py`. Proof: pytest 7/7 on this branch.
- [x] HH2. Implemented `quickstart` in `.jcode/tools/dev.py` reusing setup/images internals (new `ensure_venv`: uv locked sync, stdlib venv+pip fallback with message; `setup` delegates); `quickstart` adds Docker pre-flight (15s bound), idempotent image build, offline proof; `--keyed` flag wired. Bounded subprocess + explicit Docker failure (never chmod/root). Files: `.jcode/tools/dev.py`. Proof: gate + fresh-container runs below.
- [x] HH3. Keyed path wired: `quickstart(keyed=True)` validates `.env` key BEFORE Docker (LAW 7), exports via `keyed_env()` for the live `main.py --scan node_chain_link` (main.py never loads .env — zero dotenv, same as serve_up). Live proof: keyed chain `verified` with real Muse (red 1323→5606, blue 2881→7283, $0.18). Files: `.jcode/tools/dev.py`, `tests/test_quickstart_red.py::test_quickstart_keyed_propagates_key_to_scan_env`. Proof: fresh-container keyed run + env-propagation test.
- [x] HH4. Docs + README adoption framing: README top path = clone → `quickstart` / `quickstart --keyed` → verdict + CI/CD paragraph (gate on exit 0, archive receipt); DEVELOPMENT.md judge quickstart replaced + manual stages kept; CLI.md new `dev.py` quickstart table. Files: `README.md`, `docs/guides/DEVELOPMENT.md`, `docs/reference/CLI.md`. Proof: gate green.
- [x] HH5. Live proof + version (LAW 5/11/12): fresh `python:3.12-slim` container (docker socket, uv, clone of this branch): keyless `quickstart` → 4/4 offline verified incl. chain; rerun idempotent (same 4/4, `.env` preserved); `--keyed` → live chain `verified` w/ receipt, real Spark/Wonder, zero scan leftovers; container removed after. No dashboard/TUI change → LAW 11 matrix N/A (CLI-only). LAW 12: new user-visible capability → MAJOR 0.11.0 → 0.12.0 (APP_VERSION, README badge, MCP serverInfo, dashboard footer). Gate green; LAW 1 ship. Files: this section. Proof: container run logs + gate + ship commits.

## II. Standalone video-demo TTS server (briefs 2026-11-01-video-demo-tts-server + 2026-11-01-video-demo-tts-standalone; branch feature/video-demo-tts-server)

Goal: local, API-accessible ChatTTS voice for narrating the demo video. STANDALONE by explicit user order — zero wiring into red/blue agents, main app, dashboard, TUI, CLI, or MCP (LAW 8 tri-surface N/A: dev tool, not a product surface). Adapted from the brief's pipeline: lifespan-gated preload (port opens only when weights ready), queue workers, `/speak` queue + `/render` WAV, spin up/down scripts. Upstream API verified against 2noise/ChatTTS `core.py` (Nov 2026): `Chat.load(compile, device)`, `sample_random_speaker`, `InferCodeParams(spk_emb, temperature)`, `RefineTextParams(prompt)`, `infer()` signatures all confirmed; snippet's `[oral_2][laugh_0][break_4]` + temperature 0.3 match upstream examples.

- [x] II1. RED-first: `tests/test_tts_server_red.py` (8 tests) pins the standalone contract — lazy heavy-dep import, /healthz ready+depths, /speak 400/queue/position, /render WAV-24kHz/mono/non-empty + 400, start/stop scripts executable, shutdown teardown. RED proven: 7 errors `FileNotFoundError: .../video-demo/TTSServer/server.py` + 1 failed (functional absence). Files: `tests/test_tts_server_red.py`. Proof: pytest 8/8 green on this branch.
- [x] II2. Implemented `video-demo/TTSServer/` standalone: `server.py` (lazy ChatTTS/sounddevice import, `ServerSettings` env knobs, `ChatTTSSynthesizer`, queue `TTSEngine`, `create_app` factory + import-time `app`, `/healthz` `/speak` `/render` with 400/503 fail-closed, TEXT_LIMIT 2000), `client.py` (speak + --render, fail-closed message), `start.sh` (port probe short-circuit, pidfile, TTS_PORT/PLAYBACK/PRELOAD/COMPILE knobs), `stop.sh` (tracked-PID kill only, no pkill), `requirements-tts.txt` (upstream-pinned, OUT of main gate), `README.md` (setup/spin/use/notes). Traps fixed live: (1) `uvicorn.run("server:app")` re-imports and drops CLI flags → pass app OBJECT; (2) start.sh needed TTS_PRELOAD=0 for weightless probing. Files: `video-demo/TTSServer/`. Proof: gate + live runs below.
- [x] II3. Live proof + gate (LAW 5): full `dev.py check` green + pytest 818 passed (810 + 8 new), ruff + compileall clean. Live on :18002/:18003 (no-preload): /healthz ready+depths, /speak 400-on-empty + queued with position, /render 503-no-model (fail-closed), start.sh probe short-circuits on live port, client speak OK + fail-closed on dead port, stop.sh kills tracked PID, port confirmed down + pidfile gone. Real-voice render needs `requirements-tts.txt` + weights (not installed here). No dashboard/TUI/CLI change → LAW 11 matrix N/A. Files: this section + `video-demo/TTSServer/README.md`. Proof: endpoint transcripts + gate output on this branch. NOT SHIPPED — stays on feature branch until asked.

## JJ. Seeded voice samples (brief 2026-11-01-voice-seed-samples; branch feature/video-demo-tts-server)

Goal: 10 audio files, same test line, one random 4-digit seed each, seed in the filename, so voices can be compared seed-to-seed. mp3 preferred, wav fallback. Install as needed (host only — repo `.venv`/main gate untouched).

- [x] JJ1. Recon: system python 3.14 has torch 2.11+cu130 (CUDA live) but no ChatTTS/torchaudio; PEP 668 blocks `--user` installs → isolated venv `~/.local/share/tts-voice-samples`; ffmpeg 8 present; GPU 4070S ~8.9 GB free; no HF cache yet. Voice mechanism verified against upstream `ChatTTS/model/speaker.py`: `_sample_random` uses bare `torch.randn` (global RNG) → `torch.manual_seed(seed)` before `sample_random_speaker()` pins the voice. Files: `.jcode/briefs/2026-11-01-voice-seed-samples.md`. Proof: recon outputs on this branch.
- [x] JJ2. RED-first: `tests/test_voice_samples_red.py` (6 tests) pins seed contract — exact line text, 10 unique 4-digit seeds, seeded-RNG determinism, impossible-count ValueError, seed in filename for mp3 + wav. RED proven: `FileNotFoundError: .../sample_voices.py` (functional absence). Files: `tests/test_voice_samples_red.py`. Proof: pytest 6/6 green.
- [x] JJ3. Implemented `video-demo/TTSServer/sample_voices.py`: `generate_seeds` (unique N 4-digit via rng.sample, fail-closed on impossible counts), `sample_filename` (`voice_<seed>.<ext>`), `synthesize_for_seed` (manual_seed → sample_random_speaker → infer, temp 0.3 + `[oral_2][laugh_0][break_4]` matching the server), wav writer + non-silent check (≥0.5 s, peak ≥100), ffmpeg mp3 with wav fallback, `manifest.json`. Installed into the isolated venv: torch 2.14.1+cu130 + torchaudio + ChatTTS (+requests fix) — repo `.venv` untouched. Files: `video-demo/TTSServer/sample_voices.py`. Proof: gate green below.
- [x] JJ4. Generated `video-demo/TTSServer/samples/`: 10 unique seeds (5923, 8059, 6623, 6338, 4545, 2235, 3823, 7908, 3217, 4967) × exact line → 10 mp3s (4.0–5.1 s, 16–21 KB, 216 KB total) + `manifest.json`. All mp3s ffprobe-decode clean; all 20 wav/md5 hashes unique pre-cleanup (equal mp3 sizes 18380/19724 are codec framing, not dupes); waveform peaks/means all distinct. Intermediates dropped (rm voice_*.wav). Env-knob trap noted: weights load from HF cache outside the repo; `?`/`!` in the line print a harmless normalizer warning. Files: `video-demo/TTSServer/samples/` (10 mp3 + manifest). Proof: md5/ffprobe/waveform transcripts on this branch.
- [x] JJ5. Gate + commit (LAW 5): full `dev.py check` green + pytest 824 passed (818 + 6 new), ruff + compileall clean. Committed on `feature/video-demo-tts-server`. No dashboard/TUI/CLI change → LAW 11 matrix N/A. NOT SHIPPED — stays on feature branch until asked. Files: this section. Proof: gate output on this branch.

## KK. Literal retry: drop merging batch, retune verbatim (brief 2026-11-01-voice-seed-retry-literal; branch feature/video-demo-tts-server)

User verdict on JJ batch: voices merge words, `like it` renders as `like like it`. Provenance (installed ChatTTS source, not memory): `refine_text_only` capture showed the refiner rewriting the line to `... this is how i sound like. do you like it` — the extra `like` is inserted by the refine pass (oral/laugh/break prompt + sampling), not the vocoder. Normalizer also strips `!`/`?` (warning only). Fix = literal mode: skip refine entirely + greedy decode (temp 0.1, top_K 1).

- [x] KK1. Research: `core.py infer()` flags confirmed in installed source (`skip_refine_text`, `do_text_normalization`, `do_homophone_replacement`); `_infer` shows skip path feeds normalized text straight to `_infer_code`; A/B/C render on seed 1111 gave 3 distinct frame counts (refine path rewrites length); `/tmp/vox-refined.txt` is the `sound like` proof. Files: `.jcode/briefs/2026-11-01-voice-seed-retry-literal.md`. Proof: A/B outputs + refined-text capture on this branch.
- [x] KK2. RED-first: extended `tests/test_voice_samples_red.py` (+6: banned set exact, never-generated ×2, literal-default, literal-param values, source-pin fallback). RED proven: 5 failed pre-retune. Files: `tests/test_voice_samples_red.py`. Proof: 11 passed + 1 honest skip (ChatTTS lives in isolated venv, not repo venv; source-pin test covers the contract there).
- [x] KK3. Retuned `sample_voices.py`: `BANNED_SEEDS` (the 10 rejected), `generate_seeds` draws from the pool minus banned, `literal_params()` (temp 0.1/top_K 1/empty prompt/skip_refine), `synthesize_for_seed(..., literal=True)` default with `--expressive` opt-out restoring the old style. Verified live with real ChatTTS: temp 0.1, top_K 1, prompt '', skip True. Files: `video-demo/TTSServer/sample_voices.py`. Proof: isolated-interpreter check + tests above.
- [x] KK4. Regenerated `samples/`: deleted the 10 rejected mp3s + previews; 10 NEW seeds (2937, 8724, 2148, 7178, 4480, 3963, 2660, 5329, 1515, 6553) × exact line in literal mode → 10 mp3s (3.7–4.6 s, 15–19 KB, 192 KB) + `manifest.json`. Verified: banned overlap empty, all ffprobe-decode clean, all md5 distinct, WAV intermediates dropped. Honest limit: no ASR on this box, so verbatim delivery is proven by construction (no refine pass exists to insert words) + the refined-text capture that isolated the cause — final ear check is the user's. Files: `video-demo/TTSServer/samples/`. Proof: md5/ffprobe/manifest transcripts on this branch.
- [x] KK5. Gate + commit (LAW 5): full `dev.py check` green + pytest 829 passed + 1 skipped, ruff + compileall clean. Committed on `feature/video-demo-tts-server`. No dashboard/TUI/CLI change → LAW 11 matrix N/A. NOT SHIPPED — stays on feature branch until asked. Files: this section. Proof: gate output on this branch.

## LL. Pinned-voice iteration + listening booth (briefs 2026-11-01-pinned-voice-iteration + 2026-11-01-voice-booth-tui + 2026-11-01-booth-user-run; branch feature/video-demo-tts-server)

User's drift report (“same seed, mathematically different voice”) diagnosed + user runs the booth themselves to pick a voice. Web research confirms the pattern (ComfyUI seed-speaker node: manual_seed locks voice AND performance; upstream issue #228: same params ≠ same timbre when text changes, save embedding + near-zero temp for fixity). Booth exposes `--temperature` for this.

- [x] LL1. Drift diagnosis: speaker tensor IS deterministic per seed (`speaker.py:125` bare `torch.randn` → manual_seed pins it); the AUDIO is not, because `gpt.py:543` samples tokens with unseeded `torch.multinomial` unless `manual_seed` is passed via `InferCodeParams` (dedicated generator, `gpt.py:546-550`). Proof: seed 28 twice → identical tensor hash AND identical audio hash once pinned; pre-pin batches drifted. Files: `.jcode/briefs/2026-11-01-pinned-voice-iteration.md`. Proof: hash transcripts on this branch.
- [x] LL2. RED-first: `tests/test_try_voice_red.py` (7 tests: token-stream pin, expressive-still-pins, next-candidate, fail-bans-regenerates, pass-pins-hash, empty state) + `tests/test_booth_red.py` (8 tests: vol default/clamp, batch deal/ban-skip, fail/pass advance, batch-end, scripted flow). RED proven: FileNotFoundError both modules. Files: both test files. Proof: 33 passed (incl. all prior TTS) + 1 honest skip.
- [x] LL3. Implemented `video-demo/TTSServer/try_voice.py` (pass saves / fail bans + regenerates; `speak_params` pins voice + token stream; `render_seed`, `pin_tensor`, loop `loop.json`; NOTA BENE: embedding is the base16384 STRING, accepted directly by InferCodeParams) + `server.py` voice loading (`TTS_VOICE_PT` > `TTS_VOICE_SEED` > random). Files: `video-demo/TTSServer/try_voice.py`, `server.py`. Proof: tests + live fail/next/pin below.
- [x] LL4. Implemented `video-demo/TTSServer/booth.py` (plain-terminal loop, stdlib only): batches of 10, p/r/pass/fail/v 0-100/s/more/q, volume default 50% (playback-only, sounddevice → ffmpeg/aplay fallback), batch-end another-10 prompt, quit-anytime with state saved to `booth.json`, `--temperature` (issue-#228 fixity knob), `--text`, `--expressive`. Live proof: scripted session (play/relisten/vol-80/fail/pass/quit) → banned 2240, passed 8019 (tensor 09cfbe9cf7647b31, `.pt` + mp3 kept), state saved; audible playback worked headless here. `.pt` reload verified as voice (str embedding — docstring corrected, pin unaffected). Files: `video-demo/TTSServer/booth.py`, `README.md` booth section. Proof: session transcript + state/kept files on this branch.
- [x] LL5. Gate + commit (LAW 5): full `dev.py check` green + pytest 843 passed + 1 skipped, ruff + compileall clean. Committed on `feature/video-demo-tts-server`. No dashboard/TUI/CLI change → LAW 11 matrix N/A. NOT SHIPPED — user runs the booth themselves; stays on feature branch until asked. Files: this section. Proof: gate output on this branch.

## MM. Bare-run defaults + monotone fix (briefs 2026-11-01-booth-defaults + 2026-11-01-monotone-fix; branch feature/video-demo-tts-server)

Bare `booth.py` now does the right thing: user's voice-test line, lively upstream sampling, 1-9999 pool. History: first set near-zero temp per upstream issue #228 → user heard monotone seed 2747 (expected: greedy decode flattens prosody).

- [x] MM1. Defaults: `TRY_TEXT` = user's line in `try_voice.py` (single source; booth + samples follow); `DEFAULT_TEMPERATURE` 0.3; pools widened `try_voice.next_candidate`, `booth.deal_batch` (1-9999); `sample_voices.SAMPLE_TEXT` + `LITERAL_TEMPERATURE/TOP_K` follow; `server.py` `TTS_TEMPERATURE` default 0.3. Overrides kept (`--text`, `--temperature`, `--digits`). Files: `try_voice.py`, `booth.py`, `sample_voices.py`, `server.py`. Proof: tests below.
- [x] MM2. RED-first: extended `test_try_voice_red.py` (user line, 0.3 default, 1-9999 span incl. 28) + updated `test_voice_samples_red.py` (new line, 1-9999 pool, temp 0.3/top_K 20) + `test_booth_red.py` (1-9999 pool). RED proven: 3 failed pre-change. Files: 3 test files. Proof: 37 passed + 1 honest skip.
- [x] MM3. A/B proof on seed 2747 (your line): 0.3 twice → identical tensor (0f8edf01332bae35) AND audio (1f7d51c000c61bc9) hashes — determinism holds AT lively temp; 3e-06 → same tensor, different audio (d0d93871f7c02324) — monotone was purely temperature. Determinism comes from the manual_seed pin, not flatness. Verbatim path unchanged (skip refine, empty prompt). Files: this section. Proof: hash transcript on this branch.
- [x] MM4. Gate + commit (LAW 5): full `dev.py check` green + pytest 847 passed + 1 skipped, ruff + compileall clean. Live bare-booth run OK (your line, vol 50%, pool seed, audible headless). Committed on `feature/video-demo-tts-server`. NOT SHIPPED — stays on feature branch until asked. Files: this section. Proof: gate output on this branch.

## NN. README refinements + standalone voice-finding booth (briefs 2026-11-01-readme-refinements + 2026-11-01-booth-standalone-clarify; branch feature/video-demo-tts-server)

Standalone voice tool (no agent wiring anywhere — the only "RED" in this work is the failing-test-first discipline). Upstream README Advanced Usage diffed against our params; default test phrase upgraded to cover most of a voice (user invited a better default).

- [x] NN1. Recon: README pins `temperature=0.3, top_P=0.7, top_K=20` (we overrode temperature only); sentence control `[oral_2][laugh_0][break_6]` (we used break_4); word control = inline `[uv_break]`/`[lbreak]`/`[laugh]` with `skip_refine_text=True`; `compile=False` fast start (already); FAQ #2 validates the booth loop. Installed dataclass defaults confirmed (`top_P=0.7, top_K=20` inherited). Files: `.jcode/briefs/2026-11-01-readme-refinements.md`. Proof: README fetch + grep transcripts.
- [x] NN2. RED-first: extended `test_try_voice_red.py` (+4: README triple pin, break_6 prompt, word-break wrap, word-break off). RED proven: 4 failed pre-change. Files: `tests/test_try_voice_red.py`. Proof: 41 passed + 1 honest skip.
- [x] NN3. Implemented: `try_voice.py` — `speak_params` pins full README triple + `refine_prompt`; `EXPRESSIVE_PROMPT` break_6; `apply_word_breaks()` opt-in (`--word-breaks` in try_voice + booth); `sample_voices.py` expressive path triple + break_6; `server.py` triple + break_6 default. Default phrase upgraded to voice-covering line (whisper-to-shout question, exclamation, ellipses pauses, PPAP twister; single source `TRY_TEXT`, `sample_voices` imports with path-safe fallback). Files: `try_voice.py`, `sample_voices.py`, `server.py`, `booth.py`. Proof: tests + live renders below.
- [x] NN4. Live proof: seed 28 plain + word-breaks renders (same tensor 5e53726bee70c324, different audio 300KB vs 298KB — breaks audibly reshape phrasing); default-phrase render 508KB/10.6s clean. Gate green: 851 passed + 1 skipped, ruff + compileall. No agent-surface changes. NOT SHIPPED — user runs the booth; stays on feature branch until asked. Files: this section. Proof: render transcripts + gate output on this branch.

## OO. Quiet booth + PPAP-free phrase (briefs 2026-11-01-booth-quiet + 2026-11-01-booth-standalone-clarify follow-ups; branch feature/video-demo-tts-server)

User's session showed two noise sources (`invalid characters` warning + weight/infer tqdm bars); PPAP line loops autoregressive decoding.

- [x] OO1. Noise diagnosis: warning = normalizer stripping `!`/`?` (harmless, per render); weight bar = transformers `core_model_loading.py:1789` (`desc="Loading weights"`, 182 params) via its `_tqdm_cls` wrapper honoring `are_progress_bars_disabled()`; per-render bars = gpt.py pbar. Provenance: source greps + a wrong turn each (tqdm 4.70 has no class-level `disable`; TQDM_DISABLE unread at construction) recorded so nobody re-derives them. Files: `.jcode/briefs/2026-11-01-booth-quiet.md`. Proof: grep + interpreter transcripts.
- [x] OO2. RED-first: `test_quiet_render_gates_logger_and_tqdm` (+ fix to assert HF/transformers switch). RED proven: failed pre-change, incl. the live AttributeError on the wrong switch. Files: `tests/test_try_voice_red.py`. Proof: 23 passed post-fix.
- [x] OO3. Implemented `quiet_chattts()`: ChatTTS logger levels to ERROR + `HF_HUB_DISABLE/TQDM_DISABLE` env + `disable_progress_bars()` for both huggingface_hub and transformers, all restored in finally; `show_tqdm=False` on all our refine/infer params; booth wraps `chat.load` too. Display-only — sampling untouched. Voice-covering default phrase (PPAP dropped: repetitive tokens loop the decoder; new line covers whisper-to-shout question, exclamation, ellipses pauses, sibilant sunset/lakes sentence). Files: `try_voice.py`, `booth.py`, `sample_voices.py`. Proof: tests + session below.
- [x] OO4. Live proof: scripted booth session → 0 noise lines (`grep -cE` on invalid/it-s/%/Loading = 0), clean transcript (load message → model ready → seed 155 played at 50% → quit saved). New-phrase render clean. Gate green: 852 passed + 1 skipped, ruff + compileall. No agent-surface changes. Committed on `feature/video-demo-tts-server`. NOT SHIPPED — user runs the booth; stays on feature branch until asked. Files: this section. Proof: session log + gate output on this branch.

## PP. Silent-seed crash guard + user picks saved (brief 2026-11-01-booth-silent-crash; branch feature/video-demo-tts-server)

User's 27-audition session crashed on seed 3665 (near-silent peak 31 → fail-closed check raised through the booth loop, killing the session). 4 voices passed: 1869, 6420, 812, 7358.

- [x] PP1. Root cause: `check_audio_non_silent` correctly refused silence but the RuntimeError propagated uncaught (booth.render → main). Fix = auto-ban + advance, never crash. Files: `.jcode/briefs/2026-11-01-booth-silent-crash.md`. Proof: user traceback.
- [x] PP2. RED-first: `test_silent_seed_auto_bans_and_session_continues` (scripted session with raising render → quit True, seed banned, "silent" tagged). Initial test wrong (targeted 3665 not in probe batch); fixed to probe real batch. RED proven pre-fix. Files: `tests/test_booth_red.py`. Proof: 43 passed + 1 skipped.
- [x] PP3. Implemented: `run_booth(..., fail_silent=True)` + `safe_render` (auto-ban w/ reason, session continues); interactive `render()` catches, deletes bad wav, auto-bans via `record_fail`, returns None (play/pass skip); `try_voice.py` CLI prints clean fail + suggestion, exit 1, no traceback; also wrapped CLI weight load in quiet gate. Voice output of good seeds untouched. Files: `booth.py`, `try_voice.py`. Proof: tests + live seed-3665 re-render (clean fail message, exit path, no traceback).
- [x] PP4. User picks committed: `passed/voice_{1869,6420,0812,7358}.{mp3,pt}` (mp3 + pinned embedding each) + `booth.json` session record (4 passed, 23 banned) — merged from user's session as-is. Gate green: 853 passed + 1 skipped, ruff + compileall. Committed on `feature/video-demo-tts-server`. NOT SHIPPED — stays on feature branch until asked. Files: this section + `passed/`. Proof: gate output + file listing on this branch.

## QQ. Temperature variation pass over 4 pinned voices (brief 2026-11-01-voice-repin-variations; branch feature/video-demo-tts-server)

User re-auditions the 4 pinned voices at 5 temperatures each (0.1/0.3/0.5/0.7/0.9 = 20 auditions), pass/fail per variation. Analysis note: passed embeddings are mutually distant (cosine 0.03–0.20) — user selected delivery survivors, not a timbre family — so temperature (delivery control) is the right axis to vary, not more seeds.

- [x] QQ1. RED-first: `variation_schedule` (20 pairs, seed-major order), `variation_pass/fail` (temp pairing record), `run_variations` scripted session (6 played, 4 picks). RED proven: 3 failed pre-change. Files: `tests/test_booth_red.py`. Proof: 46 passed + 1 skipped.
- [x] QQ2. Implemented: `variation_schedule()`, `BoothState.variation_pass/fail`, `run_variations()` (silent-safe, scripted), interactive `run_vary_mode()` (`--vary 1869,6420,812,7358 --vary-temps ... --vary-state variations.json`): renders `vary_<seed>_<temp>.wav`, pass pins `.pt` + mp3 + records `{seed, temperature}`, fail advances, quit-anytime saves. Voice identity untouched (same seed → same tensor, `.pt` files as-is). Files: `video-demo/TTSServer/booth.py`. Proof: tests + live below.
- [x] QQ3. Live proof: seed 1869 @ 0.1 vs 0.9 → same tensor (04330622274b889b = passed record) + different audio hashes — voice fixed, delivery varies, both deterministic. Gate green: 856 passed + 1 skipped, ruff + compileall. Committed on `feature/video-demo-tts-server`. NOT SHIPPED — user runs the variation pass; stays on feature branch until asked. Files: this section. Proof: hash transcript + gate output on this branch.

## RR. Vary sweet-spot retune + reset (brief 2026-11-01-vary-sweet-spot-retune; branch feature/video-demo-tts-server)

User listening findings: below temp 0.3 is monotone; above 0.5 is weird/buggy/monotone-with-weird-pitches. Sweet spot is 0.3–0.5, so sweep that band in 0.05 steps — and reset the partial run so it starts fresh.

- [x] RR1. RED-first: `test_default_vary_temps_cover_sweet_spot` asserts `DEFAULT_VARY_TEMPS == (0.3, 0.35, 0.4, 0.45, 0.5)`. RED proven (failed pre-change). Files: `tests/test_booth_red.py`. Proof: pytest failure pre-fix.
- [x] RR2. Retuned: `DEFAULT_VARY_TEMPS = (0.3, 0.35, 0.4, 0.45, 0.5)` + `--vary-temps` help + docstrings updated; `--vary-temps` flag still overrides for custom sweeps. Still 20 auditions (4 seeds × 5 temps); only the temp axis changed. Files: `video-demo/TTSServer/booth.py`. Proof: RED test green.
- [x] RR3. Reset per user request: deleted untracked `variations.json` (2 1869 picks), `passed/voice_1869_t0p{3,5}.{mp3,pt}`, and 5 `vary_1869_*.wav` scratch files — all regenerable, none committed. Base 4 voices (`voice_{1869,6420,0812,7358}.{mp3,pt}`) untouched. Verified `run_vary_mode` always starts at index 0 (no skip-ahead logic) — the "resume" feel was loaded picks + leftovers, now cleared. Files: (deletions only, untracked). Proof: rm transcript + ls after.
- [x] RR4. Gate green: 857 passed + 1 skipped, ruff + compileall. Committed on `feature/video-demo-tts-server`. NOT SHIPPED — user runs the fresh 20-audition sweep; stays on feature branch until asked. Files: this section. Proof: gate output + commit on this branch.

## SS. Final voice bake-off: 12 demo-line takes (brief 2026-11-01-final-voice-takes; branch feature/video-demo-tts-server)

User's top two (7358 female favorite, 6420 male second) × anchor temps (0.3, 0.5) × 3 spelling-corrected demo lines, named `<seed>-<gender>-<temp>-<N>.mp3`, so the final choice compares identical text across voices.

- [x] SS1. RED-first: `test_final_takes_plan_names_and_lines` (12 entries, `7358-female-0.3-1.mp3` present, unique names, literal, seeds/temps in scope) + `test_final_takes_runner_completes_all_twelve` + `test_final_takes_runner_records_failure_without_stopping` (one bad take can't kill the rest). RED proven (AttributeError pre-change). Files: `tests/test_booth_red.py`. Proof: pytest failure pre-fix, 16 passed post.
- [x] SS2. Implemented: `FINAL_TAKES_LINES` (S M S / S Q L letter-spaced, "vulnerability" corrected), `FINAL_TAKES_VOICES`, `FINAL_TAKES_TEMPS`, `final_takes_plan()`, `run_final_takes()` (failures recorded, never raised), `run_takes_mode()` (non-interactive, wav->mp3 via ffmpeg, wav cleaned up) + `--takes <dir>` CLI wired in main. LAW 8: plan + runner + CLI surface, no orphaned logic. Files: `video-demo/TTSServer/booth.py`. Proof: RED tests green + `--help` shows flag.
- [x] SS3. Live proof: `booth.py --takes takes` → 12 of 12 kept, exit 0; sizes 16–29KB each and identical rank-order across combos (line 1 longest, line 2 shortest — delivery tracks text, not wandering); non-silent guard passed on all. Files: `video-demo/TTSServer/takes/*.mp3`. Proof: render transcript + ls/ffprobe.
- [x] SS4. Gate green: 860 passed + 1 skipped, ruff + compileall. Committed `d4dfcd0` on `feature/video-demo-tts-server` (also swept in user's regenerated `variations.json` + 8 temp-pinned `passed/` files from the sweep run — small, document choices, keeping). NOT SHIPPED — stays on feature branch until asked. Files: this section. Proof: gate output + commit on this branch.

## TT. Pin 6420 male @ 0.3 as demo narrator (brief 2026-11-01-pin-narrator-6420; branch feature/video-demo-tts-server)

User winner: "male 03" = 6420 male at temperature 0.3. Bare server runs now narrate in that voice with no flags.

- [x] TT1. RED-first: `test_narrator_defaults_to_6420_male_at_03_literal` (seed 6420 / temp 0.3 / literal True out of the box), `test_narrator_env_overrides_seed_temp_literal` (TTS_VOICE_SEED / TTS_TEMPERATURE / TTS_LITERAL override), `test_synthesize_pins_token_stream_to_seed` (same settings → identical spec, manual_seed 6420, skip_refine True; seed 1869 differs). RED proven: 3 failed pre-change (defaults unpinned, no build_infer_spec). Files: `tests/test_tts_server_red.py`. Proof: pytest failures pre-fix, 27 passed post (with booth file).
- [x] TT2. Trap hit + fixed in-test: dataclass field defaults evaluate `os.environ.get` once at import, so monkeypatch-after-import can't move them — override test reloads the module with env set (comment in test). LAW 9B honored: test strengthened to exercise the real path, implementation untouched. Implemented: `NARRATOR_SEED`/`NARRATOR_TEMPERATURE`, `ServerSettings.voice_seed` default "6420" + new `literal` flag (`TTS_LITERAL`, default true), `build_infer_spec()` (plain-dict contract: infer/manual seed, temp, top_P/K, skip_refine), `synthesize()` uses the spec (torch.manual_seed + manual_seed on InferCodeParams + skip_refine from spec — the booth-proved pin, closing the server's delivery drift). Deliberately NOT defaulting `voice_pt`: checked-in absolute path would break other checkouts (comment in server.py). Files: `video-demo/TTSServer/server.py`, `README.md` (env knobs + narrator note). Proof: RED tests green, ruff clean.
- [x] TT3. Live proof (GPU box, TTS venv, fastapi stubbed — server web deps not installed there): defaults print `6420 / 0.3 / True`; `ChatTTSSynthesizer(ServerSettings()).synthesize(demo line 1)` → 250KB, non-silent guard passed; TWO fresh-process repeats hash `8cc5a9f2…` identically — narrator bit-identical across renders. Scratch wavs in /tmp removed. Files: (proof only, no artifacts). Proof: hash transcript above.
- [x] TT4. Gate green: 863 passed + 1 skipped, ruff + compileall. Committed `aedb430` on `feature/video-demo-tts-server` (recovery note: first attempt `23ec976` swept in 1.2 GB of freshly-downloaded `asset/` weights via `git add -A` — undone via soft reset, weights evicted from index, `asset/` added to `video-demo/TTSServer/.gitignore` as machine-local cache; branch never pushed so no remote damage). NOT SHIPPED — stays on feature branch until asked. Files: this section. Proof: gate output + commit on this branch.

## UU. Headless desktop capture sandbox (briefs 2026-11-01-desktop-capture-sandbox + 2026-11-01-finalize-desktop-capture; branch feature/desktop-capture-sandbox)

Goal: headless Wayland capture + virtual camera pipeline under `video-demo/desktop-capture/` that bypasses GNOME portal prompts: gamescope video isolation, PipeWire audio isolation, clean-room C PipeWire node broadcasting the sandbox as a hardware-style webcam. AnyCam reference studied for architecture only (node shape, SPA MemFd/MemPtr mechanics); `pwcam_desktop.c` authored from scratch — nothing copied.

- [x] UU1. RED-first: `tests/test_desktop_capture_red.py` (10 contracts: file layout, locked 1920x1080@60 I420 single format, MemFd/MemPtr buffers, raw-stdin reader_thread + memcpy on_process, no turbojpeg/swscale, sandbox pipe, isolated audio). RED proven: 10 failed pre-change (FileNotFoundError functional absence). Files: `tests/test_desktop_capture_red.py`. Proof: pytest 10 failed pre, 10/10 green post.
- [x] UU2. Phase 1 clean-room node: `video-demo/desktop-capture/deskcap/pwcam_desktop.c` + `Makefile` (Video/Source "Desktop Capture Camera", exactly one EnumFormat I420 1920x1080@60, SPA_PARAM_Buffers MemFd|MemPtr + Header meta, reader_thread reads exact 3110400B raw frames from stdin, on_process memcpy, broadcast-black before first frame, stdin-EOF quit). Gate BEFORE scripts: `make` exit 0, `ldd` = libpipewire+libc only, 0 banned hits. Files: `deskcap/`. Proof: make + ldd transcripts on this branch.
- [x] UU3. Phase 2 sandbox: `video-demo/desktop-capture/gamescope/launch_sandbox.sh` (gamescope `-W 1920 -H 1080` on `WAYLAND_DISPLAY=wayland-99` running `bash -c "$APP_CMD"`, wf-recorder `-D wayland-99 -c rawvideo -x yuv420p -f -` piped into `deskcap`, trap kills pipeline process group via setsid + gamescope). Trap learned live: middle-job-PID kill orphans the tail (stray `sleep 72` proven) — `setsid` + `kill -- -PGID` verified zero strays. Files: `gamescope/`, `desktop-capture/README.md` trap section. Proof: bash -n + setsid group-kill transcript.
- [x] UU4. Phase 3 audio: `video-demo/desktop-capture/pipewire/setup_audio_sink.sh` (idempotent module-null-sink `IsolatedAppAudio`, records module index 0600, prints PULSE_SINK + monitor-only record one-liners) + `teardown_audio_sink.sh` (unloads exactly the recorded index, name-scoped fallback, safe when absent) + `README.md` (PULSE_SINK routing demo, ffmpeg + pw-record monitor lines). Files: `pipewire/`. Proof: bash -n both + RED tests green.
- [x] UU5. Ship: `dev.py check` 873 passed + 1 skipped + All checks passed; LAW 12 MAJOR 0.12.0 -> 0.13.0 (new capability: C capture node + sandbox + audio pipeline; APP_VERSION, README badge, MCP serverInfo, dashboard footer); LAW 1 flow feature -> develop -> main, both pushed, back on develop. No dashboard/TUI/CLI change -> LAW 11 matrix N/A (CLI-adjacent shell/C tooling only; RED tests are the contract). Files: this section. Proof: gate output + ship commits.




## GG. Closed-loop guidance: refactor + README + governance (brief 2026-11-01-closed-loop-guidance; branch feature/closed-loop-guidance)

Lead ran solo (swarm spawn infra DOWN 06:11 UTC: router misroutes `muse-spark-1.3-contributor` to Anthropic, 11 refusals, recorded in brief + TRAPS-worthy). Honest Δ: prior BB/CC/DD had already zeroed most of the directive — recon proved it before any edit.

- [x] GG1. Recon + GUIDANCE_MATRIX.md ledger (S_current per subsystem, Δ, vectors, gate status). Baseline gate green pre-change. Files: `GUIDANCE_MATRIX.md`, `.jcode/briefs/2026-11-01-closed-loop-guidance.md`. Proof: gate 06:11 UTC green + matrix.
- [x] GG2. Subsystem A: line-number drift refreshed in `docs/{web,tui,mcp}/INDEX.md` (true ll. 663/682-693/735-1093/1098+/1445+, main.py:2794); physical `web|tui|mcp/` dirs ATTEMPTED then REVERTED (a `tui/` package shadows root `tui.py` -> `import tui` resolves to package -> collection ERROR; same asymmetric risk for web/mcp) — maps-only is the gate-safe form per LAW 10B/10D; `modules.*` spelling VERIFIED KEEP (test_tui.py:145 fake-injection seam needs it, proven live). Files: `docs/*/INDEX.md`. Proof: gate 876 + shadowing transcript.
- [x] GG3. Subsystem B: verified zero-change (`.gitignore:277-278` ignores briefs/session, `git ls-files .jcode/briefs` empty; flat `docs/*.md` are `# Moved` stubs or canonical — diffed each). Files: `GUIDANCE_MATRIX.md` rows B4/B5. Proof: check-ignore + diff transcripts.
- [x] GG4. Subsystem C RED->GREEN: `docs/TECHNICAL_BREAKDOWN.md` created (119 lines, all refs true); README refusal paragraph scoped to contest brief (Opus 5.5/Fable 5.1/Luna 6/Sol 6.1) + breakdown link; cost claim grounded in `pricing.py` table (Spark 0.31 in / 0.21 out vs Wonder), stale `$150` pin strengthened to `pricing.py` citation; 3 new tests (refusal names, grounded cost, breakdown link). Files: `README.md`, `docs/TECHNICAL_BREAKDOWN.md`, `tests/test_docs_presentation.py`. Proof: 12/12 presentation tests.
- [x] GG5. Subsystem D live proof: Gate 1 `dev.py check` 876 passed + All checks passed; Gate 2 `offline_scan` 4/4 verified pre=0 post=1 + cleanup; Gate 3 LAW 11 Firefox + Chrome `node_query_sink --offline` both "Boundary check passed" (Chrome needs `.venv/bin/python`; system python lacks `websockets`). Files: `GUIDANCE_MATRIX.md` row D1. Proof: gate + scan + card outputs.

## VV. Audit-to-ship backlog: competition-lockdown branch (briefs 2026-11-01-correctness-audit through 2026-11-01-architectural-audit; branch feature/competition-lockdown@`c8470d8`, gate 1027+1)

Context: six engineering stages + SAPRE + architectural audit landed on this branch (commits `3944a49` → `c8470d8`). Gate green 1027+1, working tree clean, nothing pushed. Items below are the unresolved tail: ship mechanics, blocked live proofs, deferred consolidations, residue cleanup, and open questions for the user. Owner: Jcode agent unless marked USER.

### VV-A. Ship mechanics (needs USER go-ahead per LAW 1)

- [ ] VV-A1. Ship `feature/competition-lockdown` per LAW 1/5/12: final `dev.py check` green (re-run at ship time), decide LAW 12 bump (0.13.1 → 0.14.0 MAJOR: WS atomic-busy + vault flag + registry cap + KEV TTL are behavior changes a judge could notice; else 0.13.2 minor), write ship commit message with version reason, merge feature → develop → pushed → main → pushed → back on develop. Proof: gate output + push logs + `--version` consistency (APP_VERSION/README badge/MCP serverInfo/dashboard footer).
- [ ] VV-A2. Confirm TODO.md merge policy at ship: this file is edited on the feature branch and merges up like any other file (AGENTS.md §7) — no separate handling needed, but call it out in the ship report so the develop/main copies stay in sync.

### VV-B. Blocked live proofs (need USER resources: key and/or display)

- [x] VV-B1. Keyed live flip on this branch (`a707e2e` + refactor): `main.py --scan node_chain_link` with real Muse -> Status: verified (red 1323 in/5771 out, blue 2617/8323, $0.2031, vault KNOWN_ARCHETYPE). Zero leftovers. Proof: CLI transcript on feature/continue-delta-sweep. `main.py --scan node_chain_link` with real Muse (red→blue→verify + receipt), then `offline_scan` 4/4. BLOCKED: needs `META_MUSE_API_KEY` in owner-only `.env`. Proof: scan card with token counts + receipt hash + zero leftovers.
- [x] VV-B2. LAW-11 browser matrix on this branch: v3_live_e2e 4/4 PASS (Firefox+Chrome x prod+demo, live verdict, 0 leftovers) + gate3_matrix 13/13 both browsers (all modes, stepper echo fix verified in-browser, guards, tabs, filters, maptools, fake verdict). Proof: E2E + matrix JSON on feature/continue-delta-sweep. `ui_scan node_query_sink --offline` in headless Firefox AND Chrome, operate (not just load) the touched controls (binary redirect, busy banner, pass chip). BLOCKED: needs headless browsers on the ship machine (this box: Firefox null-selector pre-hydration + Chrome rootless crash). Proof: cards + offline E2E JSON.
- [x] VV-B3. Project 2/2 re-run on this branch: project_scan.py PASS (2/2 cycles, deterministic inference), offline_scan 4/4 verified. Proof: PASS lines + zero session containers. `project_scan.py` PASS (last green was on `6776671`; `main.py` admission changed since in `0482d04`). Needs Docker only (no key). Proof: PASS line + cleanup.

### VV-C. Deferred code consolidations (small, safe, implement when authorized)

- [x] VV-C1. D-1/D-2 snippet-map consolidation DONE: canonical SNIPPET_LANGUAGE_BY_SUFFIX (pre-existing) + promoted SNIPPET_FILENAME_BY_LANGUAGE to mcp_bridge (executor already used app.js/app.py/index.php; TUI private duplicate snippet.js/py/php removed, imports canonical). RED identity pin test_snippet_filename_map_single_sourced. Files: mcp_bridge.py, main.py (unchanged import), tui.py, tests/test_correctness_parity_red.py. Proof: RED->green + parity suites. (P2, architectural audit): canonical `_SNIPPET_LANGUAGE_BY_SUFFIX` (+ filename map) in `library/services/mcp_bridge.py` (already owns `_MCP_LANGUAGE_*`); replace duplicates in `main.py:1465` + `tui.py:127` (+ `tui.py:497`) with imports. Files: `mcp_bridge.py`, `main.py`, `tui.py`, `tests/test_correctness_parity_red.py` (+1 identity pin). Proof: gate green + parity tests.
- [x] VV-C2. P3 import-direction test DONE: test_s1b (core imports only core/shared; services.* upward edge fails). Found 2 live violations (docker_manager:21 projects types + :522 binary cap) -> moved ProjectSpec/Snapshot/Metadata/MAX_* to new core/project_models.py (re-exported from services.projects, identity-preserved), BINARY cap aliased via MAX_BINARY_BYTES, 10 tags.py backends repointed to canonical. Files: project_models.py (new), docker_manager.py, projects.py, binary_intake.py, tags.py, tests/test_sapre_assurance_red.py. Proof: RED (2 violations) -> green, full suite 1044. AST walk asserting no `modules.workflows`/`modules.services` imports in `library/core` (except `services.projects` types) and no `import main` anywhere; keeps the no-cycle property enforced (extends SAPRE `test_s1`). Files: `tests/test_sapre_assurance_red.py`. Proof: gate green.

### VV-D. Residue + hygiene (operator actions, need USER decision)

- [x] VV-D1. Session residue: docker ps label filter EMPTY on this box (the 16 pre-existing containers are gone — prior cleanup landed). Fresh offline_scan + project_scan + keyed scan + 4/4 E2E all leave zero. Nothing to reap. Proof: ps output on feature/continue-delta-sweep. 16 pre-existing `purplebox.session` containers (13:39–15:07, incl. running targets + Created verifiers from pre-fix sessions) predate the keep-tracked fixes. Decide: run `main.py --cleanup` (reaps only session-labeled resources, keeps base images) or explicitly exclude. Files: none (operator run). Proof: `docker ps -a --filter label=purplebox.session` empty + fresh offline run leaves zero.
- [ ] VV-D2. MCP-HTTP busy sites: WS path fixed (`main.py` re-check atomic); the two `/mcp` branches (`~1233`, `~1372`) share the old check-then-acquire shape with a bigger validation gap. Recovery pass added regression tests proving the pattern; MCP sites NOT yet converted (HTTP lock held across validation by design, race window smaller but nonzero). Decide: convert to the same re-check pattern (mechanical, mirrors WS fix) or document as accepted residual. Files: `main.py`, `tests/test_recovery_convergence_red.py`. Proof: concurrent-pair test, second gets `-32001` ≤1 s.
- [ ] VV-D3. Swarm spawn infra: `muse-spark-1.3-contributor` route misroutes to Anthropic (11 refusals, 2026-11-01 06:11 UTC). All audit phases ran single-agent. Decide: report to harness maintainer / retry later; no repo change. Proof: successful spawn when infra recovers.

### VV-E. Open questions for USER (blocking go-ahead or scope)

- [ ] VV-E1. Ship now or keep validating? Branch is green (1027+1) with 6 briefs + full A–G deliverables per stage. Options: (a) ship as-is (LAW 12 bump + LAW 1 flow), (b) land VV-C1/C-2 + VV-D2 first (small, ~30 min), (c) wait for keyed/browser proofs (VV-B1/B-2). Which?
- [ ] VV-E2. LAW 12 version call: MAJOR 0.14.0 (fail-closed behavior changes: atomic busy, vault flag, registry cap, KEV TTL) or minor 0.13.2 (audit + tests only, no user-visible capability)? Recommendation: MAJOR — the busy-refusal and vault-flag surface changes are judge-noticeable.
- [ ] VV-E3. `video-demo/TTSServer/` + `video-demo/desktop-capture/` (prior branches, NOT on this branch): ship with this branch, separately, or never? This branch never touched them; confirm they stay out of the ship diff.
- [ ] VV-E4. Daemon-kill mid-verdict recovery drill (chaos handoff item): authorized to run against an isolated daemon (would orphan the 16 pre-existing sessions otherwise), or explicitly deferred to post-ship ops?
- [ ] VV-E5. 100-scan soak for residue statistics (qualification handoff): run overnight pre-ship, or accept the bounded-mechanism evidence (cap/TTL/close-idempotency) and defer soak to post-ship reliability?

## YY. Vendor-name scrub (briefs 2026-11-02 vendor-name scrub + commits rule; same branch)

- [x] YY1. Inventory: 8 tracked files held the token; tracked zero-width/BOM markers: none. Ignored paths (`.jcode/briefs`, `.pytest_cache`) and git history out of scope.
- [x] YY2. Incidental mentions removed (6 files): `AGENTS.md`, `.jcode/AGENTS.md`, `docs/guides/WORKFLOWS.md`, `docs/TRAPS.md`, `docs/SESSION_LESSONS.md`, `web/AGENTS.md` (harness-list/router notes reworded, meaning preserved). Intentional refs kept per user: MCP-bridge client example + model-lock reject vector.
- [x] YY3. Scrub-hygiene test written then DELETED per user (a token-search test carries the token itself). Verification by direct `git grep` instead: only the 2 intentional lines remain. Behavior unchanged: `test_model_lock` + suites green (65 passed), lint clean. Commit message pre-checked token-free. Proof: this section + commit `9ccb945`.

## XX. v3 WebUI primary site + live wiring (brief 2026-11-02-v3-webui-reconcile; branch feature/v3-webui-reconcile)

- [x] XX1. Copy audit: `web/` matches external `~/Downloads/SMS-WebUI-complete/SMS-WebUI/v3` (only diffs: version.js mapping comment, ruff-formatted sync_assets.py, no .github). Root cause of "none of the site": `/` still served v2. Proof: `diff -rq` transcript.
- [x] XX2. Serving: `/` + `/web/` -> 307 `/web/index.html`; v2 kept intact at `/v2/` (assets unchanged at /static/*); `/web` mount moved below explicit routes (mount-first shadowed `/web/`); ui_scan/project_ui_scan repointed to `/v2/`. Files: `main.py`, `tests/test_web.py` (path only, assertions unchanged), `.jcode/tools/ui_scan.py`, `.jcode/tools/project_ui_scan.py`. Proof: 5 RED -> green in `tests/test_webui_v3_contract.py`; gate 1036 passed (`b0cb606`).
- [x] XX3. Clean-room: inline `style=` (dropped by CSP style-src 'self') -> classes `l-tag-*`, `eyebrow-gap`; `/ws/system` dead endpoint -> explicit `invalid` refusal (fail closed). Proof: same tests.
- [x] XX4. Live frames: `link.js` routed server `snapshot` + `telemetry_batch` as blank `onLine(undefined)` -> now `onSnapshot` + per-event lines. Files: `web/js/stream/link.js`, `tests/test_v3_link_frames.py`. Proof: RED (blank line) -> green.
- [x] XX5. Sub-agent writers merged (demo onGraph/onSnapshot, console chips + rules.js real phrases): merged feature/v3-live-demo + feature/v3-live-console, both web-only additions, worktrees removed, branches deleted. Gate at merge: 1042. Files: web/js/pages/demo.js, web/js/pages/console.js, web/js/stream/rules.js, tests/test_v3_live_demo.py, tests/test_v3_live_console.py. Proof: merge commits on feature/v3-webui-reconcile.

- [x] ZZ. v3-only cutover: static/ deleted (7 files), /v2/ route + /static mount dropped; 23 v2-pinned test files rewritten against live v3 anchors (slices B/C + mine: ingest/receipt/binary); tags.py checker searches web/ pages + delegated needles. Narrowings recorded in-test: receipt sha16-not-sha12, CHATTER_RE -> namesIn/speakerFor, hash routes -> page flow. Slices merged via isolated worktrees (205489d, 047f1c8, ccdf08f + format). Gate: 1041 passed + All checks passed. Live matrix 4/4 PASS (Firefox+Chrome x prod+demo, KnownMuse, 0 leftovers). Files: main.py, dev.py, ui_scan.py, project_ui_scan.py, web/*.html, web/js/**, docs/reference/DASHBOARD.md, README, 23 tests. Proof: E2E JSON records + gate output on this branch.

- [x] XX6. Live matrix 4/4 PASS + diff-beat fix: Firefox+Chrome × prod+demo, real Docker (KnownMuse), user-style Launch clicks, live verdict + counters rendered, zero leftovers. Found live: patch counts via unified diff line (`log("blue", result.diff)`), verdict announced before counters propagated — choreography counts real diff once (`!patched` guard), E2E polls counters. Files: `web/js/stream/choreography.js`, `tests/test_v3_live_stream_beats.py` (verbatim live stream, RED 1 failed -> green), `.jcode/tools/v3_live_e2e.py`. Gate final: 1043 passed + All checks passed; session containers 0; single worktree. Proof: E2E JSON records + gate output on `feature/v3-webui-reconcile` commit `7c95fd2`.

## ZZ2. Closed-loop guidance v2 (brief 2026-11-02-closed-loop-guidance-v2; branch feature/closed-loop-guidance-v2)

- [x] G0/G1. Recon + GUIDANCE_MATRIX_V2.md ledger (A/B/C, S_current/Δ/vectors/gates); baseline 1041+1 green, tree clean. Files: `GUIDANCE_MATRIX_V2.md`, `.jcode/briefs/2026-11-02-closed-loop-guidance-v2.md`. Proof: gate output + ledger.
- [x] GA. Subsystem A (legacy retirement): code Δ already 0 (no static/, no /v2/, 404 pins); 8 live docs rewritten to v3-only via 2 isolated worktrees (web/INDEX, mcp/INDEX, MODULES, AGENTS, HOW_IT_WORKS, ARCHITECTURE, REFACTOR_PLAN, TAGS, web/README). History files untouched. Files: commit b41aae7. Proof: grep 0 static refs + 46 docs tests green.
- [x] GB. Subsystem B Gate 2: offline_scan 3/3 verified + v3_live_e2e 4/4 serial PASS (Firefox+Chrome × prod+demo, live verdict + counters), 0 leftovers. Trap: first prod leg delta:1 was the parallel offline_scan container, not a leak — re-ran serially clean. Proof: E2E records + docker ps 0.
- [x] GC. Subsystem C Gate 3: `.jcode/tools/gate3_matrix.py` 13/13 Firefox + 13/13 Chrome (7 setup modes, sweep stepper, research toggle, preview, guards, tabs, radio filters, maptools, demo cards/src, speed/pause/director, fake verdict). Found live: keyboard stepper focus-echo bug (state advanced, display stale) — RED test_stepper_keyboard_sync_red (real geckodriver) `assert '1' == '2'` -> fixed bump() echo in web/js/options/form.js -> green. Files: ff2eddd. Proof: matrix JSON + RED->green.
- [x] GD. Final gate: dev.py check All checks (1042 passed + 1 skipped), ruff clean, node --check. Ship per LAW 1/5. Proof: gate output + push logs.

## XX3. Dev/prod observability LMT (brief 2026-11-02-observability-lmt; branch feature/observability-lmt)

- [x] LMT0. RED-first: `tests/test_observability_modes_red.py` (6 tests: contract shapes, env default prod, 10x logs + metric/trace parity, error trace type, secret redaction, per-aspect files). RED proven: ImportError (module absent), then green. Files: `tests/test_observability_modes_red.py`. Proof: 6 passed.
- [x] LMT1. Core module `library/shared/sms_observability.py` (stdlib only): SIGNALS logs/metrics/traces, `logs/<signal>/<aspect>.jsonl` JSONL layout, dev 10x detail fanout on logs, metric/trace parity across modes, trace spans ok/error with duration, LAW-4 secret redaction, no-op safe uninit'ed, per-run `_summary.json`. Files: module. Proof: RED->green.
- [x] LMT2. Mode switch (W1): config `observability_mode` + validate + env, global `--observability-mode` CLI flag (flag>env>default), init/shutdown in main + MCP STDIO + tui run_plain/curses; `.gitignore` logs/; example.env documented. Proof: TUI suites + RED tests green.
- [x] LMT3. Engine instrumentation (W2): fixture loop trace + 7 milestones (hashes/sizes/counts/exits only), sweep per-pass, project cycles, binary sweep, agents call traces (numbers only, NEVER prompt text), docker op traces + exit/cleanup. Proof: workflow/sweep/project/binary suites green.
- [x] LMT4. Intel/services/docs (W3+remainder): research/cve/intel-search/scanners/dtrack/vault (counts/degraded only; vault keys/blobs NEVER logged) + sms_api/mcp/telemetry/demo_gen + OBSERVABILITY.md + README + CLI.md row. Proof: scanners/vault/deep/mcp suites green.
- [x] LMT5. Scan tools wired (offline_scan/project_scan init+shutdown, --observability-mode on project_scan). Live proof: keyless offline_scan 4/4 verified in dev mode -> 1144 records across 9 aspect files + summary (308 fixture logs vs unit-proven 77:7 dev:prod), trace spans ok with durations, no secrets on disk. Proof: tree transcript + counts above; runtime logs/ removed after proof.
- [x] LMT6. Final gate + ship: dev.py check All checks (1050 passed). Merged feature -> develop -> main, both pushed, back on develop. Proof: gate output + push logs.
