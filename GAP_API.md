# GAP_API.md — UI vs server input/display gap audit

Date: 2026-10-28 · Branch: `feature/work-gap-api` · Scope: read-only audit.
Server surface: `main.py` (WS routes, query params, socket JSON, CLI flags),
`projects.py` (ProjectSpec), `profiles.py` (model profile keys),
`scan_profiles.py` (intensity keys), `workflow.py` (ScanResult),
`project_workflow.py` (ProjectWorkflowResult), `demo_gen.py`.
UI surface: `static/app.js` (sends/renders), `static/index.html` (controls).

Rule: each item = server capability the UI never sends or never displays,
with file:line evidence on both sides. No source was edited for this report.

## Sends (UI never sends it)

1. `research=on` for fixture scans. Server applies it to every socket
   (`main.py:276`), CLI passes `--research` for `--scan` (`main.py:1211-1219`),
   but both toggles live inside `#project-form` (`index.html:86-87`), which
   `setSourceMode` hides unless mode is `project` (`app.js:397-399`). Fixture
   `startScan` reuses the hidden unchecked toggles (`app.js:812-814`), so
   `/ws/combat/{key}` can never get `research=on` from the dashboard.
2. `research=on` for demo builds. Same cause: `startDemoBuild` reuses
   `socketQuery()` (`app.js:924`), toggles hidden, always off; server would
   honor it (`main.py:276-291`).
3. Online intel opt-in for demo builds on hosted inference. `run_demo_build`
   accepts `intel_offline` (`main.py:49-57,345`), but the only consent input
   (`#allow-remote`, `index.html:88`) is inside the hidden project form, so
   the coercion `intel_offline = ... || !allow-remote.checked` (`app.js:931`)
   forces offline demos in hosted mode with no visible override. CLI has the
   explicit `--allow-remote-inference` / `--intel-offline` pair
   (`main.py:970-973,1009-1013`).
4. `research_scanners=dependency-track`. Server allowlist has five scanners
   including `dependency-track` (`main.py:277-278`); UI hardcodes four
   (`app.js:727`) with a single on/off toggle and no per-scanner picker
   (`index.html:87`). The fifth scanner is unreachable from the dashboard.
5. Non-default `red_agents`/`blue_agents` on any non-ultra profile. Server
   honors 1-12 on every `scan_profile` (`projects.py:85-86`,
   `project_workflow.py:795-796`); UI disables both inputs unless
   `scan_profile === 'ultra_heavy'` (`app.js:432-435`, `index.html:83-84`),
   always sending 5 otherwise (`app.js:468`).
6. Demo intensity (`scan_profile`, `red_agents`, `blue_agents`). CLI
   `--ai-demo` accepts them (`main.py:1226-1228,1235-1238`); WS `/ws/demo`
   reads only `theme/build_brief/vulns/intel_offline` (`main.py:340-345`),
   `run_demo_build` takes no intensity args (`main.py:49-57`), and
   `materialize_demo_project` hardcodes defaults (cycles=1, 5v5,
   `demo_gen.py:310-317`). Dashboard demo config has no intensity controls
   (`index.html:62-65`).
7. CVE-scan mode (`cve_scan`, `deep_assessment`, `offline_cve`). CLI flags
   exist (`main.py:979-993`) and `cli_runner` branches on them
   (`main.py:589-595`); `/ws/project` always runs
   `execute_project_workflow` (`main.py:335`) with no JSON key to select CVE
   mode, and the UI sends none.

## Displays (UI never renders it)

8. Fixture `ScanResult.traces` (`workflow.py:230`). `showResult` renders
   message/diff/usage/cycles but never `payload.traces` (`app.js:686-717`);
   "traces" appears in UI only as an aria-label (`index.html:130`).
9. Fixture structured `finding` / `patch` objects (`workflow.py:222-223`).
   Only the diff string and message are shown (`app.js:689-712`); no
   `payload.finding` / `payload.patch` reference exists in `static/`.
10. Project `context_coverage` (`project_workflow.py:166`). Zero references
    in `static/`; coverage shortfall per cycle is invisible on the dashboard.
11. Project `passes_per_cycle`, `cycles_requested`, `cycles_completed`
    (`project_workflow.py:158-162`). Zero references in `static/`; UI shows
    only a derived kept/total count (`app.js:675-677`), so requested-vs-done
    is never displayed.
12. Per-cycle `changed_paths` (`project_workflow.py:140`). `renderCycles`
    shows Report/Evidence/Diff only (`app.js:630-639`); changed paths never
    rendered.
13. `health.busy` scan-lock state (`main.py:251`). UI gates Run on key+docker
    only (`app.js:758`) and never reads `health.busy`; contention is learned
    only post-connect via the `busy` frame (`app.js:837-840`).

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
- `research_records`, `cycle_reports`, usage/cost, diff, cleanup,
  baseline/regression/pre/post facts all rendered (`app.js:565-588`,
  `604-717`); every fixture/project status has a label (`app.js:8-20`).

## Server-side note (not a UI gap, found during audit)

- `--cycles` and `--context-budget` combined with `--ai-demo` pass argparse
  validation (`main.py:1136-1152` allows them for ai-demo) but
  `ai_demo_runner` accepts neither (`main.py:437-452` signature), so both
  flags are silently dropped for AI demos.

Gap count: 13 (7 send, 6 display).
