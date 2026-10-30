# UI Guidance State Matrix — live telemetry ledger (directive 2026-10-30)

> LAW 2 source: `.jcode/briefs/2026-10-30-ui-guidance-matrix.md`.
> Baseline (2026-10-30, branch `feature/ui-guidance-matrix`): `dev.py check`
> **615 passed**, ruff clean/format clean, harness PASS, `--list-targets` OK
> (4 entries incl. binary_argv_echo). LAW 10A clean tree, no open TODO items
> (V1 Y-series + W1 integration all `[x]` on develop).
> Recon: 2 read-only sidecars (route-pinned `meta-muse:muse-spark-1.3-contributor`):
> backend recon (main.py + modules inventory) + frontend gap audit (guppy anchors).
> Stack decision (LAWs 8/10F/10G + directive's own "based on the project's
> current framework"): vanilla HTML/CSS/JS + FastAPI stays. No React/Next.js,
> no `react-force-graph-3d`, no npm/CDN — CSP is `script-src 'self'`
> (`main.py:358-361`), there is no package.json/build step, and LAW 8
> tri-surface parity has no WebGL equivalent in TUI/CLI. Canvas-2D
> force-directed engine (hand-rolled, zero-dep, CSP-safe) is the "or equivalent"
> primary; the existing log-derived timeline strip is the fallback (Gate 3).
> Routes are hash-routed views (`#/`, `#/demo`, `#/live`) in the single served
> shell — no server route churn, deep-linkable, offline-safe.

## Backend telemetry inventory (everything the UI may surface)

- Transports: `WS /ws/combat/{key}` (`main.py:702`), `/ws/project` (`:706`),
  `/ws/demo` (`:710`), `/ws/binary` (`:715`); query `profile`,
  `sweep_passes=2|3`, `research=on`, `research_scanners` allowlist (`:439-467`).
  `GET /api/targets` (`:371`), `GET /api/health` (`:382`: version,
  api_key_configured, inference_mode/ready, red/blue model, profiles,
  default_profile, scan_profiles+cycles, docker state, busy). `POST /mcp`
  (`:721`, JSON-RPC tools incl. snippet/source/binary scan, vault stats,
  receipt verify). CLI (`main.py:1924-2126`): --serve/--port, --scan,
  --sweep-passes, --binary-target, --mcp-snippet, --ai-demo + Greenhouse flags
  (--demo-size/--flaw-count/--seed), --research/--research-scanners, --init-images,
  --list-targets, --version. TUI (`tui.py`, parity 0.6.0): fixture/sweep/binary/
  mcp/demo-build/project/cve modes + keys.
- Emit teams: red/blue/green/research/system (`modules/services/chatter.py:65-116`).
  Stages: sandbox/baseline/analysis/probe/patch/regression/cleanup
  (`static/app.js:7`, advanced by log vocabulary `:289-308`).
- Result payload fields (all redacted server-side, LAW 4): status, receipt /
  VerdictReceipt / CycleReceipt (`workflow.py:220-267`, `project_workflow.py:265-320`),
  cleanup_ok, usage.calls[] (model, prompt/completion/reasoning tokens, seconds,
  cost_usd), total_tokens, cost_usd, compression{raw_tokens_estimated,
  compressed_tokens_sent, tokens_saved, compression_ratio}
  (`sms_compress.py:93-100`), vault_recall + vault_namespaces, research_records
  (CVE/scanner rows), guard_rationale, fast-lane topping, mutation evidence,
  cycle_reports/cycles (report/evidence/diff/receipt/pass_number),
  differential_passed + differential_class (`project_workflow.py:1171-1182`),
  property checks, sweep pass results (`sweep.py:49-93`), binary telemetry
  (`binary_sweep.py`), deep-scan reach_score/KEV/EPSS (`deep_scan.py`,
  `cve_workflow.py`), scan-profile cycles (`scan_profiles.py`).

## Subsystem A — Split-route architecture (landing + /demo + /live, shared core)

- Where It Is ($S_{current}$): single served shell `GET /` → `static/index.html`
  (273 lines; CSS `app.css`, scripts `panels.js`+`app.js`+`fx.js`, CSP-safe).
  Five in-page source modes (`app.js:406-420` `setSourceMode`, `hidden` toggle,
  no router/history): demo (bundled fixtures via `/ws/combat`), demo-build
  (Greenhouse `/ws/demo`), project (live uploads `/ws/project`), mcp (`POST /mcp`),
  binary (`/ws/binary`). All transports already share one viz core: `writeLine`
  → logs + `Panels.renderTimeline` + `SMSFx` pulses (`app.js:244,257,275,332`).
- Where It Isn't ($\Delta$): no URL-addressable routes — nav is in-page anchors
  (`index.html:20-27`); brand `href="/"`; no landing view distinct from console;
  no `#/demo` happy-path vs `#/live` live-input separation; mode state not
  deep-linkable or back-button safe.
- Corrective Action Vector:
  1. RED test `tests/test_ui_guidance.py`: route shell (landing/demo/live links,
     hash router boot, shared-core contract) FAILS pre-change.
  2. `index.html`: landing hero view + `#/demo` (fixture happy path) + `#/live`
     (project/binary/MCP inputs) views; all existing mode forms/cards move
     under views unchanged (LAW 8/10C: no surface removed, all IDs preserved).
  3. `app.js`: tiny hash router (`#/`, `#/demo`, `#/live` + legacy `#configure`
     anchors honored), mode↔route sync, one shared viz core (logs/timeline/fx —
     already shared, keep DRY, no duplication).
  4. Gates 1+2+3 (Gate 3: router works with JS motion disabled / no-canvas).
- Verification Gate Status: `[x] VERIFIED_ZERO_DELTA`

## Subsystem B — Cinematic force-directed graph engine

- Where It Is ($S_{current}$): NO graph — `panels.js` (202 lines) renders a
  horizontal marker strip (`#scan-timeline`, `MAX_MARKERS=100`, rAF-batched,
  `classify()` log-regex → glyph/kind/label `◆✕?✔✚◉➤○▣`, `buildMarker` DOM-only,
  zero canvas/SVG/force sim). `fx.js` (262 lines): cursor glow + parallax CSS
  vars + WAAPI 10px data-flow pulses (`fire(kind,fromSel,toSel)`, selectors
  RED/BLUE/SYS fixed). Glue only in `app.js` (`onEvent/onStage/onFinish`).
- Where It Isn't ($\Delta$): no node/edge/physics renderer; no team visual
  language beyond log colors (green Matrix glow, red glitch, blue radar sweep,
  purple physics-freeze all absent); no particle lanes on dependency links;
  no 2D/WebGL split (nothing to fall back FROM — timeline strip must remain
  as the degraded path).
- Corrective Action Vector:
  1. RED test: `static/graph.js` `SMSGraph` API (init/update/fallback) + DOM
     mount + team-color contract FAILS pre-change (file absent).
  2. New `static/graph.js` (CSP-safe, no deps): canvas-2D force layout; nodes =
     pipeline stages + sweep passes + agent roster presence; edges = data flow;
     team styling green-glow/red-jagged/blue-sweep/purple-freeze; particle dots
     on edges; `prefers-reduced-motion`/no-canvas → timeline strip stays
     (fallback = existing strip, Gate 3 asserts strip renders with graph off).
  3. Wire: `app.js` feeds stage/roster/result events into `SMSGraph.update`;
     `index.html` mounts `<canvas id="phase-graph">` in pipeline card;
     `fx.js` vocabulary untouched.
  4. Gates 1+2 (mock JSON + live WS binding, no crash) + 3 (fallback proof).
- Verification Gate Status: `[x] VERIFIED_ZERO_DELTA`

## Subsystem C — Telemetry HUD + feature surfacing

- Where It Is ($S_{current}$): status chips (`#chip-key/docker/server`,
  `index.html:33-38`); session stats (`#status/#pass-chip/#elapsed/#event-count`,
  `:50-55`); team rosters (`red/blue/green-roster`, `app.js:1101-1103`,
  `RED_NAMES/BLUE_NAMES:44-45`, leaders Warlord/Warden/Greenhouse); result facts
  (`fact-baseline/pre/regression/post/receipt/guards/topping/mutations/
  compression/vault/cleanup`, `:222-234`) + usage block (`:238-241`);
  log filters only (All/System/Red/Blue/Research/Green, `:252-260`); only
  checkboxes are consent/intel (`research-toggle`, `research-scanners-toggle`,
  `allow-remote`, `demo-offline`, `demo-allow-remote`) + config selects
  (`sweep-passes`, scan profiles). L/R terminals exist as `#red-log/#blue-log`
  panels (`:177-192`, CSP textContent-only) — terminal-like pop is decorative
  transient (`spawnTerminalPop`, 4.2s).
- Where It Isn't ($\Delta$): no aggregate scoreboard (Active Agents / Vulns
  Found / Patches Applied / Verified Purple across the session); no toggles
  for the rest of the backend inventory (sweep depth is a select; scan-profile
  cycles, compression badge, vault recall, KEV/EPSS/reach display, binary
  telemetry, differential/property gates have no dedicated HUD controls —
  several render only inside result facts post-run).
- Corrective Action Vector:
  1. RED test: scoreboard element + per-capability toggle contract FAILS pre-change.
  2. `index.html` header scoreboard (session aggregates, live-updated from
     health + result payloads; zero new backend needed); capability toggles
     wired to EXISTING surfaces only (sweep passes, scan profile, research,
     research-scanners, compression/vault/differential/property visibility,
     binary telemetry panel) — every toggle drives a real execution/reflect
     path (LAW 8D, no dead controls); red/blue log panels keep terminal
     semantics (auto-scroll, mono, CSP-safe).
  3. Gates 1+2+3 (browser matrix operates every toggle, LAW 11).
- Verification Gate Status: `[x] VERIFIED_ZERO_DELTA`

## Execution order (sequential, gates after each)

Z0 (this ledger) → Z1 RED tests → ZA → ZB → ZC → Z2 gate/docs/version.
Regression halts forward progress (doctrine §0.4; LAW 10A/E).
TODO states live in TODO.md section Z.

## Close-out proof (2026-10-30, branch `feature/ui-guidance-matrix`)

- RED (LAW 9A): `tests/test_ui_guidance.py` 8 failed/1 passed pre-change
  (functional absences; terminal-semantics test already green), 9 passed
  post-change, no weakening.
- Gate 1: `dev.py check` GREEN — 624 passed, ruff clean/format clean, harness
  PASS, `--list-targets` OK.
- Gate 2: `offline_scan.py` (venv) 3/3 verified (pre=0/post=1, cleanup clean).
- Gate 3: `ui_scan.py node_query_sink --offline` Chrome + Firefox result cards
  verified; live `serve-up :18080` DOM proof (all route views/graph/scoreboard/
  7 toggles present); CDP operate-proof PASS (hash routes, SMSGraph live,
  toggle flips, mode sync project on #/live).
- Known non-blocker: `browser_controls_check.py` asserts stale
  `mcp_tools == ["submit_code_snippet"]`; live server correctly returns all 5
  library/MCP tools (V1 Subsystem E). Tool needs its assertion updated, not the
  dashboard — recorded here, dashboard untouched further.
