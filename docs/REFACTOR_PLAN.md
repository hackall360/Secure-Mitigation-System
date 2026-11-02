# REFACTOR_PLAN — code category maps (no file moves where the gate forbids them)

Lead plan for the BB remodel. Each sweep gets a what/where/why index. Rule of
thumb: **rename by copy inside the repo, never by breaking a gate-pinned
path**. Where a path is pinned (`dev.py check`, smoke test, test markers),
the directory map lives in a doc + `__init__` re-exports, not in moved files.

## library/ — the central core (`library/core`, `library/shared`)

- Status: `modules/` IS the library. `modules/core/*.py` = central core logic
  (agents, checks, config, docker_manager, patches, personas, pricing,
  profiles, prompts, registry, scan_profiles); `modules/shared/*.py` =
  cross-cutting reuse (sms_async, sms_budget, sms_compress, sms_http,
  sms_records, sms_redact, sms_scan_parse, sms_text); `modules/intel/` =
  keyless intel transports (research, intel_search, scanner_binaries,
  scanner_dtrack, sms_vault — never-raises, host-only); `modules/services/`
  = product surfaces (mcp_bridge, sms_api, projects, repo_intake, demo_gen,
  project_agents, chatter, binary_intake, binary_telemetry);
  `modules/workflows/` = the five verification loops (workflow, sweep,
  binary_sweep, project_workflow, cve_workflow, deep_scan).
- Remodel: rename `modules/` → `library/` (git mv, history preserved) and
  keep a `modules/` shim package re-exporting every symbol, so all
  `from modules.*` import sites (main, tui, tests, tools) keep working.
  Update `pyproject.toml` isort first-party to include `library`.
- Why a shim, not a full rewiring: ~40+ import sites across tests/tools plus
  string-form seams (`tui` sys.modules fakes, web monkeypatch targets,
  `scripts/` namespace) make a flag-day rewiring high-blast-radius. The shim
  keeps the gate green at every commit; a follow-up can rewire file by file.

## web/ — dashboard + server surface (map, no move)

- `static/` (index.html shell, app.js, app.css, graph.js, fx.js, panels.js,
  favicon.svg): stays at `static/` — pinned by `dev.py` (`node --check
  `web/js/**`, smoke `GET /web/*`) and `main.py` StaticFiles mount +
  a dozen tests. Map: `web/static/` ≡ `static/`.
- Server surface in `main.py` (create_app, `/api/*`, `/ws/*`, `/mcp`,
  `--serve/--port`, StaticFiles mount at `static/`): stays in `main.py` —
  ~10 test files `import main` + monkeypatch `main.*` targets; a move would
  rewrite the whole test seam layer. Map: `web/server/` ≡ `main.py`
  serving section (~ll. 600–1400). Documented in `docs/web/`.
- E2E tools (`.jcode/tools/ui_scan.py`, `browser_controls_check.py`,
  `ui_design_metrics.py`): in git-ignored `.jcode/`, untouched per directive.

## tui/ — terminal surface (map, no move)

- `tui.py` (curses + run_plain, sys.modules workflow fakes), `sms_cli.py`
  (CLI tables/config helpers imported by `main.py`), `--tui/--sweep/--scan`
  flags in `main.py`, `scripts/mcp_client_demo.py` (terminal demo client):
  all stay — pinned by `import tui` / `import main` / `scripts.*` test
  seams. Map: `tui/` ≡ these files. Documented in `docs/tui/`.

## mcp/ — model context protocol surface (map, no move)

- `modules/services/mcp_bridge.py` (executor), `modules/services/sms_api.py`
  (scan_source/scan_binary/query_vault_stats/verify_receipt),
  `main.py --mcp` STDIO + `POST /mcp` HTTP, dashboard MCP mode,
  `scripts/mcp_client_demo.py`: stay in place (same import-seam reason).
  Map: `mcp/` ≡ these files. Documented in `docs/mcp/`.
- After the `library/` rename the MCP code lives at
  `library/services/{mcp_bridge,sms_api}.py`; the `mcp/` doc points there.

## docs/ + laws + agents + README

- Sweep B: prompt-history/session docs stash (git-ignored), MVP pages stay.
- Sweep C: root AGENTS (project) + `.jcode/AGENTS.md` (harness) + numbered
  `.jcode/laws/` mirror + `.jcode/agents/` INDEX + README rewrite.
