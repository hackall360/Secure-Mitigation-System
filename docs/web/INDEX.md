# web/ — dashboard + server surface (category map, files stay pinned)

`web/` is a documented category, not a moved directory. Three gate pins forbid
moving: `dev.py check` runs `node --check static/app.js` and smoke-tests
`GET /static/*`; `main.py` mounts `StaticFiles(directory=BASE_DIR / "static")`;
~12 test files assert on `static/` contents and `import main` + monkeypatch
`main.*` targets.

## web/static/ ≡ `static/` (pinned, do not move)

| file | what | why web |
|---|---|---|
| `static/index.html` | shell: routes `#/` `#/demo` `#/live`, scoreboard, HUD, panels | page structure |
| `static/app.js` | WS client, render, HUD wiring, toggles | behavior |
| `static/app.css` | token-CSS v2 (no Tailwind, offline-safe) | style |
| `static/graph.js` | canvas-2D phase graph + timeline fallback | visualization |
| `static/fx.js`, `static/panels.js` | effects + panel builders | behavior split |
| `static/favicon.svg` | icon (smoke-tested) | asset |

## web/server/ ≡ `main.py` serving section (pinned, do not move)

`create_app` + `application.mount("/static", ...)` (~l.665),
`/api/health|/api/targets` (~ll.695-730), WS executors
`run_socket/combat/project_combat/demo_build/binary_combat` (~ll.737-1100),
`POST /mcp` + `--mcp` STDIO (~ll.100-170, ~2300s), `--serve/--port`.
Tests pinning it: `test_web.py`, `test_mcp_server.py`, `test_tui_plain.py`
(monkeypatch `main.*`), `test_w22_ingest_wire_red.py`,
`.jcode/tools/project_ui_scan.py` (`import main`).

## web/e2e/ ≡ `.jcode/tools/{ui_scan,browser_controls_check,ui_design_metrics}.py`

Git-ignored, untouched per directive. LAW 11 browser proof lives here.
