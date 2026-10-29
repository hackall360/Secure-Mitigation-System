# GAP_API.md — UI vs server input/display gap audit

Date: 2026-10-28 · Branch: `feature/work-gap-api` · Scope: read-only audit.
Rerun: same date, same worktree (`96c1ff2` + LAW commits in main repo).
Server surface: `main.py` (WS routes, query params, socket JSON, CLI flags),
`projects.py` (ProjectSpec), `profiles.py` (model profile keys),
`scan_profiles.py` (intensity keys), `workflow.py` (ScanResult),
`project_workflow.py` (ProjectWorkflowResult), `demo_gen.py`, `sms_redact.py`.
UI surface: `static/app.js` (sends/renders), `static/index.html` (controls).
TUI surface: `tui.py` (checked for parity; sends no research/intensity keys).

Rule: each item = server capability the UI never sends or never displays,
with file:line evidence on both sides. No source was edited for this report.

Status key: OPEN = still unreachable/invisible in this worktree.
CLOSED = fixed in latest code (drop or annotate). No gap below is CLOSED:
sibling tracks (`work-gap-cli`, `work-gap-modes`, `work-bug-green`,
`work-bug-rounds`, `work-bug-e2e`, `work-startup-law`, `ui-gaps-green-crash`)
touch only their own `*_CLI.md`/`*_MODES.md` notes, demo error handling,
parse matching, redaction fail-closed, or LAW text — none wires a dashboard
control, WS key, TUI binding, or render path listed here.

LAW 8 mapping per gap: the missing binding is named as a `Core → bus → surface`
chain (Core = workflow/config logic, bus = WS query/JSON route, CLI flag, or
TUI bridge; surface = Web UI control/render, TUI view, CLI flag). Closing a
gap means wiring the full chain, not one end.
LAW 10B mapping per gap: Blast radius lists every file a fix must touch
(caller + consumer + tests), so a closer updates all call sites atomically.

## Sends (UI never sends it)

1. OPEN. `research=on` for fixture scans. Server applies it to every socket
   (`main.py:276`), CLI passes `--research` for `--scan` (`main.py:1036-1039,
   `main.py:1211-1219`), but both toggles live inside `#project-form`
   (`index.html:86-87`), which `setSourceMode` hides unless mode is `project`
   (`app.js:397-399`). Fixture `startScan` reuses the hidden unchecked toggles
   (`app.js:812-814`), so `/ws/combat/{key}` can never get `research=on`
   from the dashboard.
   LAW 8 missing binding: `workflow._gather_research → WS query research=on
   on /ws/combat/{key} (main.py:276-291,418) → Web UI fixture-mode research
   toggle`. TUI has no research binding either (`tui.py` has no WS client).
   LAW 10B blast radius: `static/index.html` (move/duplicate toggles),
   `static/app.js` (`socketQuery`, `startScan`), `main.py` (query parse),
   `workflow.py` (`_gather_research`), `tests/test_web.py`,
   `tests/test_dashboard_toggles*` (research toggle tests).

2. OPEN. `research=on` for demo builds. Same cause: `startDemoBuild` reuses
   `socketQuery()` (`app.js:924`), toggles hidden, always off; server would
   honor it (`main.py:276-291`, then `run_demo_build` at `main.py:49-57`).
   LAW 8 missing binding: `workflow._gather_research → WS query research=on
   on /ws/demo (main.py:276-291,426) → Web UI demo-build-mode research
   toggle`. No CLI research-for-demo gap: CLI has it (`--ai-demo --research`).
   LAW 10B blast radius: `static/index.html`, `static/app.js`
   (`startDemoBuild`, `socketQuery`), `main.py` (`run_demo_build`,
   `/ws/demo` handler at `main.py:426`), `tests/test_web.py`.

3. OPEN. Online intel opt-in for demo builds on hosted inference.
   `run_demo_build` accepts `intel_offline` (`main.py:49-57,345`), but the
   only consent input (`#allow-remote`, `index.html:88`) is inside the hidden
   project form, so the coercion `intel_offline = ... ||
   !allow-remote.checked` (`app.js:931`) forces offline demos in hosted mode
   with no visible override. CLI has the explicit
   `--allow-remote-inference` / `--intel-offline` pair
   (`main.py:970-973,1005-1013`).
   LAW 8 missing binding: `demo_gen/intel_search online path
   (main.py:73-118) → WS JSON intel_offline on /ws/demo (main.py:340-345)
   → Web UI demo-build-mode consent control`.
   LAW 10B blast radius: `static/index.html` (demo consent control),
   `static/app.js` (`startDemoBuild` coercion at `app.js:931`),
   `main.py` (`run_demo_build`), `demo_gen.py`, `intel_search.py`,
   `tests/test_demo_build*` / `tests/test_green*`.

4. OPEN. `research_scanners=dependency-track`. Server allowlist has five
   scanners including `dependency-track` (`main.py:277-278`); UI hardcodes
   four (`app.js:727`) with a single on/off toggle and no per-scanner picker
   (`index.html:87`). The fifth scanner is unreachable from the dashboard.
   LAW 8 missing binding: `scanner_dtrack.scan_packages → WS query
   research_scanners allowlist (main.py:277-290) + CLI --research-scanners
   (main.py:1043-1047) → Web UI per-scanner picker`.
   LAW 10B blast radius: `static/index.html` (picker),
   `static/app.js` (`socketQuery` at `app.js:721-731`), `main.py` (allowlist
   at `main.py:277,464,583`), `scanner_dtrack.py`, `scanner_binaries.py`,
   `tests/test_scanners.py`, `tests/test_web.py`.

5. OPEN. Non-default `red_agents`/`blue_agents` on any non-ultra profile.
   Server honors 1-12 on every `scan_profile` (`projects.py:85-86`,
   `project_workflow.py:795-796`); UI disables both inputs unless
   `scan_profile === 'ultra_heavy'` (`app.js:432-435`, `index.html:83-84`),
   always sending 5 otherwise (`app.js:468`). CLI accepts them freely
   (`main.py:960-965`).
   LAW 8 missing binding: `project_workflow team sizing
   (project_workflow.py:795-796,907-908) → WS JSON red_agents/blue_agents
   on /ws/project (main.py:331-335) + CLI --red-agents/--blue-agents
   → Web UI enabled agent inputs for every scan_profile + TUI roster sizing`.
   LAW 10B blast radius: `static/index.html` (agent inputs),
   `static/app.js` (`updateScanProfile`, `projectSpec`), `projects.py`
   (`ProjectSpec` bounds), `project_workflow.py` (sizing), `tui.py`
   (roster display), `tests/test_project_entrypoints.py`,
   `tests/test_cycle_profiles_workflow.py`.

6. OPEN. Demo intensity (`scan_profile`, `red_agents`, `blue_agents`). CLI
   `--ai-demo` accepts them (`main.py:949-965,1226-1238`); WS `/ws/demo`
   reads only `theme/build_brief/vulns/intel_offline` (`main.py:340-345`),
   `run_demo_build` takes no intensity args (`main.py:49-57`), and
   `materialize_demo_project` hardcodes defaults (cycles=1, 5v5,
   `demo_gen.py:286-316`). Dashboard demo config has no intensity controls
   (`index.html:62-65`).
   LAW 8 missing binding: `ProjectSpec scan_profile/red_agents/blue_agents
   (projects.py:73-92, ai_demo_runner main.py:525-535) → WS JSON intensity
   keys on /ws/demo (main.py:340-345) + run_demo_build signature
   → Web UI demo-build intensity controls`.
   LAW 10B blast radius: `static/index.html` (demo-build config),
   `static/app.js` (`startDemoBuild`), `main.py` (`run_demo_build`,
   `/ws/demo`, `ai_demo_runner`), `demo_gen.py`
   (`materialize_demo_project`), `projects.py`, `project_workflow.py`,
   `tests/test_demo_build*`, `tests/test_project_entrypoints.py`.

7. OPEN. CVE-scan mode (`cve_scan`, `deep_assessment`, `offline_cve`). CLI
   flags exist (`main.py:980-993`) and `cli_runner` branches on them
   (`main.py:589-595`); `/ws/project` always runs
   `execute_project_workflow` (`main.py:335`) with no JSON key to select CVE
   mode, and the UI sends none.
   LAW 8 missing binding: `cve_workflow.execute_cve_scan (main.py:589-598)
   → WS JSON cve_scan/deep_assessment/offline_cve on /ws/project
   + CLI --cve-scan/--deep-assessment/--offline-cve → Web UI project-mode
   CVE controls + CLI/TUI result rendering`.
   LAW 10B blast radius: `static/index.html`, `static/app.js`
   (`projectSpec`, `startScan`), `main.py` (`/ws/project`, `cli_runner`),
   `cve_workflow.py`, `deep_scan.py`, `tui.py`, `tests/test_cve*`,
   `tests/test_deep_scan.py`.

## Displays (UI never renders it)

8. OPEN. Fixture `ScanResult.traces` (`workflow.py:230`). `showResult`
   renders message/diff/usage/cycles but never `payload.traces`
   (`app.js:686-717`); "traces" appears in UI only as an aria-label
   (`index.html:130`). Redaction keeps before/after withheld and
   baseline/regression truncated (`sms_redact.py: redact_fixture_result`),
   so the safe subset is renderable but unrendered.
   LAW 8 missing binding: `workflow ScanResult.traces →
   redacted WS result payload (workflow.py:461, sms_redact.py) →
   Web UI result-panel traces section (+ TUI result view, CLI table/JSON)`.
   LAW 10B blast radius: `static/app.js` (`showResult`),
   `static/index.html` (result panel), `sms_redact.py`, `workflow.py`,
   `tui.py` (`result_summary`), `sms_text.py` (`fact_table`),
   `tests/test_sms_leaves.py`, `tests/test_tui.py`.

9. OPEN. Fixture structured `finding` / `patch` objects
   (`workflow.py:222-223`). Only the diff string and message are shown
   (`app.js:689-712`); no `payload.finding` / `payload.patch` reference
   exists in `static/`. CLI tables already render finding fields
   (`main.py:797-815`).
   LAW 8 missing binding: `workflow ScanResult.finding/patch →
   redacted WS result payload → Web UI structured finding/patch sections`.
   LAW 10B blast radius: `static/app.js`, `static/index.html`,
   `sms_redact.py`, `workflow.py`, `sms_text.py`, `tests/test_web.py`.

10. OPEN. Project `context_coverage` (`project_workflow.py:166`). Zero
    references in `static/`; coverage shortfall per cycle is invisible on
    the dashboard. Server appends per pass (`project_workflow.py:947`).
    LAW 8 missing binding: `project_workflow context_coverage →
    redacted WS result payload (project_workflow.py:1357) →
    Web UI per-cycle coverage display (+ TUI/CLI)`.
    LAW 10B blast radius: `static/app.js` (`renderCycles`),
    `static/index.html`, `project_workflow.py`, `sms_redact.py`,
    `tui.py`, `tests/test_project_workflow.py`.

11. OPEN. Project `passes_per_cycle`, `cycles_requested`,
    `cycles_completed` (`project_workflow.py:158-162`). Zero references in
    `static/`; UI shows only a derived kept/total count
    (`app.js:675-677`), so requested-vs-done is never displayed.
    LAW 8 missing binding: `project_workflow progress counters
    (project_workflow.py:799-803,971,1026,1052) → WS result payload →
    Web UI progress header (requested vs completed vs passes)`.
    LAW 10B blast radius: `static/app.js` (`renderResultMeta`),
    `static/index.html`, `project_workflow.py`,
    `tests/test_cycle_profiles_workflow.py`
    (`passes_per_cycle == 2` assertion).

12. OPEN. Per-cycle `changed_paths` (`project_workflow.py:140`).
    `renderCycles` shows Report/Evidence/Diff only (`app.js:630-639`);
    changed paths never rendered. Redacted payload already carries them
    (`sms_redact.py: redact_project_result` preserves cycle fields).
    LAW 8 missing binding: `project_workflow ProjectCycleReport.changed_paths
    → WS cycle_reports payload → Web UI per-cycle changed-paths list`.
    LAW 10B blast radius: `static/app.js` (`renderCycles`),
    `project_workflow.py`, `sms_redact.py`,
    `tests/test_project_workflow.py`, `tests/test_deep_scan.py:585`.

13. OPEN. `health.busy` scan-lock state (`main.py:251`). UI gates Run on
    key+docker only (`app.js:758`) and never reads `health.busy`;
    contention is learned only post-connect via the `busy` frame
    (`app.js:837-840`, server `main.py:299`). `/api/health` also reports it
    (`main.py:891`) and tests assert it (`tests/test_web.py:38-40`).
    LAW 8 missing binding: `/api/health busy (main.py:251,891) + WS busy
    frame (main.py:299) → Web UI pre-run lock indicator + TUI status +
    CLI --health busy flag`.
    LAW 10B blast radius: `static/app.js` (`initialize`, run gating),
    `static/index.html` (lock indicator), `main.py` (`_health_report`,
    scan-lock), `tui.py` (status line), `tests/test_web.py`,
    `tests/test_project_entrypoints.py:114-138`.

## Non-gaps (verified parity, for the record)

- All 3 WS routes used: `/ws/combat/{key}` (`main.py:418` vs `app.js:814`),
  `/ws/project` (`main.py:422` vs `app.js:814`), `/ws/demo` (`main.py:426`
  vs `app.js:924`).
- `profile` query sent for all three sockets (`app.js:723`) and read for all
  (`main.py:273`); profile keys render dynamically from health
  (`app.js:492-513`) covering economy/balanced/quality/custom
  (`profiles.py:30-52`).
- All 6 `scan_profiles.py` keys + custom offered (`index.html:73-80`,
  `scan_profiles.py:18-55`); server cycles/description rendered
  (`app.js:428-440`).
- All 11 `ProjectSpec` fields sent (`app.js:468` vs `projects.py:73-92`),
  including `context_budget`, `image`, `command`, `test_command`, `contract`,
  `allow_remote_inference`.
- Demo `theme/build_brief/vulns/intel_offline` all sent (`app.js:931`) and
  all read (`main.py:342-345`); named-profile/cycles coherence enforced both
  sides (`projects.py:94-114` vs `app.js:433-436`).
- `research_records`, `cycle_reports` evidence, usage/cost, diff, cleanup,
  baseline/regression/pre/post facts all rendered (`app.js:565-588`,
  `604-705`); every fixture/project status has a label (`app.js:8-20`).
  `research_records` rendering in `renderCycles(payload.research_records)`
  (`app.js:705`) is why research display is not listed as a gap.

## Server-side note (not a UI gap, found during audit)

- `--cycles` and `--context-budget` combined with `--ai-demo` pass argparse
  validation (`main.py:1110-1152` allows them for ai-demo) but
  `ai_demo_runner` accepts neither in its signature (`main.py:437-452`
  takes `scan_profile/red_agents/blue_agents` only), so both flags are
  silently dropped for AI demos. (CLI→runner binding gap, not UI→server.)

Gap count: 13 (7 send, 6 display). All OPEN. None closed by other tracks.
