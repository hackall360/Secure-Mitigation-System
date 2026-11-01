# web/ — dashboard + server surface (physical v3 dir + pinned v2 static/)

`web/` is the physical WebUI v3 tree (2026-11-01 migration, branch
`feature/webui-v3-migration`): 6 pages + `js/` + `css/` + `tools/` copied
verbatim from the v3 source with license headers intact. The asset pipeline
invariant holds: never hand-edit `<!-- assets:begin -->` blocks — route all
JS/CSS changes through `web/tools/manifest.json` + `web/tools/sync_assets.py`
(`--check` in CI/contract tests). `static/` (v2 single-page dashboard) stays
pinned: `dev.py check` runs `node --check static/app.js` and smoke-tests
`GET /static/*`; ~12 test files assert on `static/` contents.

## web/v3/ ≡ `web/` (migrated 2026-11-01, served at `/web/*`)

| path | what | source |
|---|---|---|
| `web/index.html` | start page (Demo / Production / Visualizer) | v3 verbatim |
| `web/prod-setup.html` | production setup (source/fields/controls/preview) | v3 verbatim |
| `web/console.html` | production console (HUD sc-nodes/sc-msgs/sc-find/sc-patch/sc-ver + chip-server/chip-docker/chip-key) | v3 verbatim |
| `web/demo-setup.html` + `web/demo.html` | demo setup + cinematic demo view | v3 verbatim |
| `web/visualizer.html` | visual test bench (simulated only) | v3 verbatim |
| `web/js/stream/interpreter.js` | line()/result() → HUD events; reads `{team,msg,ts?}` + `{type:result}` | v3 verbatim |
| `web/js/stream/link.js` | probe()/Session WS client (`/api/health`, `/api/targets`, `/ws/*`) | v3 verbatim |
| `web/js/ui/comms-feed.js` | chat-style agent→target feed | v3 verbatim |
| `web/js/options/compile.js` | form values → `{path, body}` wire shape | v3 verbatim |
| `web/tools/manifest.json` + `sync_assets.py` | single source of asset order; regenerates blocks | v3 verbatim |
| `web/AGENTS.md` + `web/README.md` | v3 contributor guide + page flow | v3 verbatim |

## web/static/ ≡ `static/` (pinned v2, do not move)

| file | what | why web |
|---|---|---|
| `static/index.html` | shell: routes `#/` `#/demo` `#/live`, scoreboard, HUD, panels | page structure |
| `static/app.js` | WS client, render, HUD wiring, toggles | behavior |
| `static/app.css` | token-CSS v2 (no Tailwind, offline-safe) | style |
| `static/graph.js` | canvas-2D phase graph + timeline fallback | visualization |
| `static/fx.js`, `static/panels.js` | effects + panel builders | behavior split |
| `static/favicon.svg` | icon (smoke-tested) | asset |

## web/server/ ≡ `main.py` serving section (pinned, do not move)

`create_app` + `application.mount("/static", ...)` + `mount("/web", ...)` (~l.663),
v3 page routes `/web/*.html` (~l.683), `/api/health|/api/targets` (~ll.699-710),
WS executors `run_socket` + connect-time `{type:snapshot}` hydration (~ll.752-880),
`combat/project_combat/demo_build/binary_combat` (~ll.1114+),
`POST /mcp` + `--mcp` STDIO (~ll.1133+, ~1480+), `--serve/--port`.
WS frame contract: `{team,msg,ts?,type:log}` (`socket_emit` in
`library/services/chatter.py`), `{type:snapshot}` (`build_snapshot` in
`library/services/telemetry_hub.py`), `{type:result|busy|invalid|graph}`.
Batching: `TelemetryBatcher` 100–250 ms for telemetry-team bursts only;
red/blue verdict lines send immediately (real time is sacred).
Tests pinning it: `test_web.py`, `test_mcp_server.py`, `test_tui_plain.py`
(monkeypatch `main.*`), `test_w22_ingest_wire_red.py`,
`.jcode/tools/project_ui_scan.py` (`import main`).

## web/e2e/ ≡ `.jcode/tools/{ui_scan,browser_controls_check,ui_design_metrics}.py`

Git-ignored, untouched per directive. LAW 11 browser proof lives here.
