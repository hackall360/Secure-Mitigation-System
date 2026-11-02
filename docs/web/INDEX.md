# web/ — dashboard + server surface (WebUI v3 only)

`web/` is the WebUI v3 site (v3-only cutover 2026-11-02, brief
`2026-11-02-v3-only-cutover`): 6 pages + `js/` + `css/` + `tools/`. The
asset pipeline invariant holds: never hand-edit `<!-- assets:begin -->`
blocks — route all JS/CSS changes through `web/tools/manifest.json` +
`web/tools/sync_assets.py` (`--check` in CI/contract tests). `main.py`
serves `/` → 307 `/web/index.html`, explicit `/web/*.html` page routes,
and the `/web` static mount; `dev.py check` smoke-tests the site via
`GET /` + `/api/targets` + `/web/index.html` + `/web/console.html` +
`/web/js/core/palette.js` + `/web/css/core/tokens.css`.

## web/ pages (served at `/web/*`)

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

## v2 dashboard retired (2026-11-02, do not resurrect)

The pinned v2 single-page dashboard (old top-level asset dir, formerly
served under the v2 routes) was removed in the v3-only cutover
(2026-11-02). No v2 asset directory exists; `GET /v2/` and the old v2
asset URLs return 404, pinned by `test_v2_dashboard_gone_after_cutover`
in `tests/test_webui_v3_contract.py`. History lives in TODO ZZ.

## web/server/ ≡ `main.py` serving section (pinned, do not move)

`create_app` + `mount("/web", ...)` (~l.707),
`/` → 307 `/web/index.html` + `/web/` → 307 + v3 page routes
`/web/*.html` (~ll.682-702), `/api/health|/api/targets` (~ll.709-720),
WS executors `run_socket` + connect-time `{type:snapshot}` hydration (~ll.763-880),
`combat/project_combat/binary_combat` (`/ws/combat/...`, ~ll.1164+),
`POST /mcp` + `--mcp` STDIO (~l.1208+, ~ll.2550+), `--serve/--port`.
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
