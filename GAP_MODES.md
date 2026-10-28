# GAP MODES — backend contracts vs Step 1 dashboard widgets

Read-only audit (2026-10-28, branch `feature/work-gap-modes`). Scope: focus
passes, light/medium/extra-light scan profiles, scan-profile, project/demo
handlers, green-build options. No source was edited for this audit.

Sources: `scan_profiles.py`, `profiles.py`, `projects.py`,
`project_workflow.py` (`execute_project_workflow`), `workflow.py`
(`execute_purple_workflow`), `demo_gen.py` (`parse_build_intent`,
`generate_demo_project`), `main.py` (`run_demo_build`, `run_socket`,
`ai_demo_runner`, CLI argparse), `project_agents.py`
(`configure_review`, `_uses_discovery_teams`), `static/index.html` (Step 1
`#picker` card), `static/app.js` (senders), `docs/architecture/SCAN_PROFILES.md`.

Conventions below: "Backend contract" = exact param name, accepted values,
default. "Widget" = Step 1 control in `static/index.html`. "Sender" = the
`static/app.js` function whose payload must carry the widget value.

## 1. Backend contracts

### 1.1 Scan intensity (`scan_profile`)

| Item | Contract |
| --- | --- |
| Param | `scan_profile` (ProjectSpec field, CLI `--scan-profile`, WS spec JSON key, `/api/health` `scan_profiles[]` list) |
| Values | `extra_light`=1 cycle, `light`=3, `medium`=5, `heavy`=8, `super_heavy`=12, `ultra_heavy`=12 (+ bounded automatic discovery from round 1), `custom` (free cycles, single pass) |
| Defaults | `ProjectSpec.scan_profile` = `"custom"`; CLI `--scan-profile` = `"custom"`; `ai_demo_runner(scan_profile=...)` = `"extra_light"`; dashboard project form preselects `extra_light` |
| Rules | `projects._apply_scan_profile`: named profile forces `cycles` to the profile count; explicit conflicting `cycles` is rejected. `focus_for_cycle(key, round)` accepts rounds `1..cycles*2`, else `ValueError`. Custom mode = 1 pass/cycle, no cumulative focus |
| Fixture mode | N/A by design: `execute_purple_workflow(target_key, emit, config=...)` takes no intensity params (single Red→Blue pass). No widget is correctly missing here |

### 1.2 Passes (focus passes)

There is **no `passes` parameter anywhere**: no `ProjectSpec` field, no CLI
flag, no WebSocket field. `passes_per_cycle` is derived inside
`execute_project_workflow` (`project_workflow.py`): `2` when the profile is
named (`Red, Blue, Red, Blue` per cycle, reported as `Cycle N · pass 1/2`),
`1` when `custom`. Display-only: cycle reports render `Cycle N · pass M`
(`renderCycles`), and the intensity description line names the pass order.
Correctly no Step 1 widget.

### 1.3 Team sizes (`red_agents`, `blue_agents`)

| Item | Contract |
| --- | --- |
| Params | `red_agents`, `blue_agents` (ProjectSpec fields, CLI `--red-agents`/`--blue-agents`, WS spec JSON keys) |
| Values | integers `1..12` each; defaults `5` / `5` |
| Effect | `configure_review()` team sizes; `ultra_heavy` additionally switches to discovery-team orchestration (`_uses_discovery_teams`); CLI warns at team `>= 10` and total `>= 20` |
| Green-build backend | `run_demo_build()` accepts **none** of these; CLI `ai_demo_runner` accepts `red_agents`/`blue_agents`/`scan_profile` and stamps them onto the spec, but the WS `/ws/demo` path never does |

### 1.4 Context budget (`context_budget`)

| Item | Contract |
| --- | --- |
| Param | `context_budget` (ProjectSpec field, CLI `--context-budget`, WS spec JSON key) |
| Values | integers `1024..131072`, default `32768`; feeds `resolve_payload_budget` per-call cap; CLI warns at `>= 65536` |
| Green-build backend | accepted **nowhere**: neither `run_demo_build()` nor CLI `ai_demo_runner()` takes it |

### 1.5 Model profile (`profile`, from `profiles.py`)

Param `profile` = `economy` (`muse-spark-1.3`/`muse-spark-1.3`) |
`balanced` (`muse-spark-1.3`/`muse-wonder-1.0`, default) |
`quality` (`muse-wonder-1.0`/`muse-wonder-1.0`) | `custom` (server
configured models; also the default when nothing matches). Transport: WS
`?profile=` query param on all three sockets, CLI `--profile`. Widget exists
for all modes (`#profile-row` Models radiogroup, `renderProfiles` /
`selectProfile`). No gap.

### 1.6 Green-build intent (`parse_build_intent`)

Signature: `parse_build_intent(*, build_brief="", vulns="", theme="")`.
Pure string surgery, never raises on weird input. Output `BuildIntent`:

| Field | Bound | Notes |
| --- | --- | --- |
| `build_brief` | ≤ 500 chars, whitespace-collapsed | free text describing the app |
| `themes` | ≤ 6 words (model allows 8) | whitespace/comma-split from `theme` |
| `cve_ids` | ≤ 8, canonical `CVE-YYYY-NNNN+` upper-cased | regex-extracted from `vulns` chunks |
| `named_types` | ≤ 8 canonical names | `VULN_TYPES` alias match (sqli, xss, cmdi, rce, ssti, xxe, ssrf, lfi, path traversal, idor, open redirect, header injection/reflection, crlf, deserialization, prototype pollution, nosql/ldap/xpath injection, log4shell …); leftovers stay free text |
| `free_text` | ≤ 8 entries, each ≤ 120 chars, ≥ 2 chars | web-search grounding |

WS `/ws/demo` first-frame fields: `theme` (sliced `[:200]`), `build_brief`
(`[:500]`), `vulns` (`[:500]`), `intel_offline` (bool, default `False`).
CLI mirrors: `--build-brief` (default `""`), `--vulns` (default `""`),
`--intel-theme` (default `"input validation SQL injection XSS
deserialization"`, ≤ 6 words used), `--intel-offline` (flag). Note the
naming trap: WS field is `theme`, CLI flag is `--intel-theme`.

### 1.7 Project/demo socket handlers (`main.py run_socket`)

- Shared query (all three sockets): `?profile=<key>`, `research=on`,
  `research_scanners=<allowlisted subset of trivy,grype,osv-scanner,dependency-check,dependency-track>`.
- `/ws/project`: first WS text frame must be a `ProjectSpec` JSON model
  (≤ 32768 bytes); invalid → `{"type":"invalid"}` + close 1008.
- `/ws/demo` → `run_demo_build(emit, settings, *, theme="", build_brief="",
  vulns="", intel_offline=False)`: own threat-intel gathering
  (`intel_for_demo` per theme, CVE records per requested id, web notes per
  named/free-text query), then `generate_demo_project` →
  `materialize_demo_project` → `execute_project_workflow` with a default
  spec (custom profile, 1 cycle). It does **not** read
  `scan_config.research_enabled`, and takes no intensity/team/budget params.
- Consent: hosted inference requires `allow_remote_inference` (project) /
  explicit checkbox (demo coerces `intel_offline=True` without consent).

### 1.8 Dashboard Step 1 inventory (exists today)

`#mode-switch` (demo / demo-build / project) · `#demo-config` (fixture
`#target-list`) · `#demo-build-config` (`#demo-build-brief`, `#demo-vulns`,
`#demo-theme`) · `#project-form` (`#project-path`, `#project-image`,
`#project-command`, `#project-test-command`, `#project-contract`,
`#project-scan-profile` + readonly-unless-custom `#project-cycles`,
`#project-red-agents` / `#project-blue-agents` disabled unless
`ultra_heavy`, `#project-budget`, `#research-toggle`,
`#research-scanners-toggle`, `#allow-remote`) · `#profile-row` (all modes).

### 1.9 Dashboard senders (must carry any new widget)

- `socketQuery()` — `?profile=&research=on&research_scanners=` on **all
  three** sockets (`startScan` fixture/project, `startDemoBuild`).
- `projectSpec()` — first-frame JSON for `/ws/project` (path, image,
  command, test_command, contract, scan_profile, cycles, red_agents,
  blue_agents, context_budget, allow_remote_inference).
- `startDemoBuild` `socket.onopen` — first-frame JSON for `/ws/demo`
  (`theme`, `build_brief`, `vulns`, `intel_offline`); `intel_offline` is
  currently **coerced**, not widget-driven:
  `inferenceMode === 'local' || !el('allow-remote').checked`.

## 2. Missing widgets — 8 total

All eight sit in Step 1 (`#picker` card). M1–M5 additionally need a backend
prerequisite: `run_demo_build()` must accept and forward the new param
(it currently takes only `theme/build_brief/vulns/intel_offline`), otherwise
the sender has nowhere to deliver the value.

- **M1 — Green-build scan intensity.** Control: `<select>` mirroring
  `#project-scan-profile` (extra_light default + light/medium/heavy/
  super_heavy/ultra_heavy/custom). Placement: top of `#demo-build-config`,
  before `#demo-build-brief`. Sender: `startDemoBuild` `onopen` JSON adds
  `scan_profile`.
- **M2 — Green-build cycles (derived/custom).** Control: readonly number
  input mirroring `#project-cycles` (derived from M1; editable only when
  M1 = custom, 1–20). Placement: beside M1 in `#demo-build-config`.
  Sender: same `onopen` JSON adds `cycles`.
- **M3 — Green-build red agents.** Control: number input 1–12 default 5,
  disabled unless M1 = `ultra_heavy` (same rule as `updateScanProfile()`).
  Placement: `#demo-build-config`, team-size row with M4. Sender: same
  `onopen` JSON adds `red_agents`.
- **M4 — Green-build blue agents.** Control/sender/placement: mirror of M3
  for `blue_agents`.
- **M5 — Green-build context budget.** Control: number input 1024–131072
  default 32768 mirroring `#project-budget`. Placement:
  `#demo-build-config`, beside the M3/M4 row. Sender: same `onopen` JSON
  adds `context_budget`. Backend prerequisite includes `ai_demo_runner`
  (CLI takes no `--context-budget` for demo either).
- **M6 — Green-build explicit offline toggle.** Control: checkbox
  `intel_offline` in `#demo-build-config` (replaces silent coercion).
  Placement: under `#demo-theme`. Sender: same `onopen` JSON sends its
  state instead of `inferenceMode === 'local' ||
  !el('allow-remote').checked`. No backend change needed (param exists).
- **M7 — Visible consent in Green-build mode.** Trap: `#allow-remote`
  lives inside `#project-form`, which is `hidden` in demo-build mode, yet
  `startDemoBuild` reads it to coerce M6 — the user cannot see the control
  deciding offline-vs-remote. Control: visible consent checkbox bound to
  the same `#allow-remote` element (sync, not a second source of truth).
  Placement: `#demo-build-config`, under the M6 toggle. Sender: same
  `onopen` coercion line (unchanged logic, now user-visible).
- **M8 — Research toggles reachable in fixture + Green-build modes.**
  Trap: `#research-toggle` / `#research-scanners-toggle` live inside
  `#project-form` (hidden unless project mode), but `socketQuery()` sends
  them on **all** sockets — fixture and Green-build users can never turn
  them on. Control: relocate the two toggle `<label>`s out of
  `#project-form` to picker level (e.g. directly above `#profile-row`) so
  they are visible in every mode. Placement: Step 1, outside any
  mode-specific container. Sender: `socketQuery()` unchanged. Backend note:
  fixture workflow honors `research_enabled`; `run_demo_build()` ignores it
  (own intel path), so for Green-build the toggle is advisory until the
  demo path reads the flag.

## 3. Explicitly not gaps

- Fixture (bundled-demo) scan intensity/passes/agents/budget: backend
  (`execute_purple_workflow`) exposes none of these; single-pass by design.
- Passes: derived (`2` named / `1` custom), display-only in cycle reports.
- Model `profile` (economy/balanced/quality/custom): widget + sender exist
  for all modes. Light/medium/extra-light coverage in the project
  intensity dropdown is complete (all six + custom).
- `parse_build_intent` inputs (`build_brief`, `vulns`, `theme`): all three
  widgets exist with matching `maxlength` bounds (500/500/200).
