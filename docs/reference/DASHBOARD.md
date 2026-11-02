# Dashboard panels and hooks map

`web/js/pages/` owns all per-page DOM writes and network calls;
`web/js/ui/` widgets are side-effect-scoped layers fed by
`web/js/stream/interpreter.js`. CSP-safe throughout: `h()` in
`web/js/ui/dom.js` sets `textContent` and `setAttribute` only, no
`.innerHTML` assignments in `web/js/`, no `eval`, no inline handlers.

## Layers

| File | Hooks in / out |
|---|---|
| `web/js/pages/start.js` | Mode selection + version panel + ambient map. In: `SMS.link.probe()`, `SMS.topology.profile()`. Out: links to `demo-setup.html` / `prod-setup.html` / `visualizer.html` (`data-key` 1/2/3 shortcuts). |
| `web/js/pages/setup-demo.js` | Demo selection. In: `O.OptionForm` (`demo-opts`, `demo-build-opts`), `SMS.topology.profile()`. Out: `SMS.launch.save({page:'demo', kind, mode, fixture, request, topo, grow, values, summary})` → `demo.html`. |
| `web/js/pages/setup-prod.js` | Production selection (7 sources). In: `O.OptionForm` (src/run/prop forms), `O.compile()`, `SMS.topology.{profile,project,fromSource,fromBinary,fromSystem}()`. Out: `SMS.launch.save({page:'console', kind:'live'|'fake', ...})` → `console.html`; binaries via `L.putBlob('binary', buf)` (IndexedDB `sms-v3`/`blobs`). |
| `web/js/pages/demo.js` | Cinematic presenter. Owns `run()`, `onLine`, `onResult` → `showVerdict`, `onClose`, `onGraph`, `onSnapshot`. All `addEventListener` wiring for director/labels/fullscreen/speed/pause keys. |
| `web/js/pages/console.js` | Production workspace. Owns `start()`, `onLine`, `onResult` → `V.renderResult`, `onClose`, `onGraph`, `onSnapshot`, `showTab`, `runSnippet` (MCP). All tab/filter/tool wiring (`t-fit`, `t-dir`, `t-labels`, `t-flow`, `t-comms`, `t-sweep`, `t-png`). |
| `web/js/pages/visualizer.js` | Backend-free test bench. In: `?lens=` / `?scenario=` query params. Out: none (no network, nothing sent). |
| `web/js/core/handoff.js` | Launch handoff. In: setup pages call `SMS.launch.save()` (sessionStorage `sms.v3.launch`); binaries via `putBlob`/`getBlob`. Out: `SMS.launch.load()` + `topology(launch)` → `{topo, buf}` on the visual page; wrong `page` redirects to its setup page. |
| `web/js/stream/link.js` | Orchestrator client. In: `probe()` (`GET /api/targets`, `/api/health`), `Session(path, body, handlers)`, `mcpSnippet` (`POST /mcp` JSON-RPC `submit_code_snippet`), `query()` (`?sweep_passes`, `research`, `profile`). Out: `onOpen` / `onLine(team,msg)` / `onResult` / `onGraph` / `onSnapshot` / `onRefuse` / `onClose` / `onError`. |
| `web/js/stream/interpreter.js` | Stream → HUD normalizer. In: `load(topo, {grow})`, `line(team, msg, meta)` per socket frame. Out: normalized `ev` (`{seq, at, team, speaker, to, toLabel, label, text, body, stage, exit}`) + `stage`/`result` events; drives graph choreography and `interp.stats` (findings/patches/verified). |
| `web/js/ui/dom.js` | Shared helpers. In: nothing. Out: `h(tag, cls, text, attrs)`, `stamp`, `counter`, `toast`, `elapsed`, `scramble` for every widget and page. |
| `web/js/ui/stage-bar.js` | `StageBar(root, {onPick})`: seven phases (`sandbox … cleanup` from `P.STAGES`/`P.STAGE_META`). In: `interp` `stage` events → `set(stage)`; verdict → `finish(ok)`. Out: click → `onPick(stage)` (console filters activity). |
| `web/js/ui/comms-feed.js` | `CommsFeed(root)`: chat rows per event. In: `add(ev)`, `setFilter(set)` (legend family filter), `clear()`. Out: none (map bubbles are drawn by the engine from the same `ev`). Caps at 120 rows. |
| `web/js/ui/terminal.js` | `Terminal(root)`: typed stdout lines. In: `push(team, text)` (prompt swaps `sandbox` → team family), `clear()`. Out: none (demo-only `#term`; queue of 12, 60 rows max, instant when `prefers-reduced-motion`). |
| `web/js/ui/hex-stream.js` | `HexStream(root)`: hexdump of the real bytes of each message. In: `push(team, text)` (first 16 bytes via `TextEncoder`), `clear()`. Out: none (demo-only `#hex`, decorative but true, 18 rows max). |
| `web/js/ui/activity.js` | Console log + timeline (`SMS.views`). `ActivityLog(root)`: `add(ev)` / `setTeam` / `setStage` / `reveal(seq)` / `visibleText()` (copy button). `Timeline(root, {onPick})`: one `.mk` marker per event, newest right; gap spacers sized by real log-scale time, `data-exit` on probe exits, `stage-start` on phase change. In: `onLine` evs. Out: marker click → `onPick(ev)` → Activity tab + `reveal`. |
| `web/js/ui/result-view.js` | Console Result pane (`SMS.views`). `renderResult(p, {source, started})` + `summarize(p)` (`pre`/`post`/`receipt`/`recs`) + `redact(evidence)` (withholds `verification_script_python`, truncates long `output`). In: `onResult` payload. Out: `#r-facts` rows (Baseline, pre/post probe, Regression, Receipt, chain, Cleanup, Sweep), `#r-diff` patch spans, `#r-usage` cost list, `#r-cycles` per-cycle/research `<details>`; feeds `dl-json`/`dl-receipt`/`dl-patch`/`cp-diff`. |
| `web/js/ui/inspector.js` | Console Inspect pane (`SMS.views.renderInspect(root, graph.describe(id), {events, topo})`). In: graph `select` events. Out: none (agent card: personality/role/messages/recent traffic; node card: kind/ring/state/path/links/attack-path/touching events). Null select → hint text. |

## Launch handoff (setup → visual)

No query-string run key: setup pages `SMS.launch.save()` a launch object to
sessionStorage (`sms.v3.launch`: `{page:'demo'|'console', kind:'live'|'fake',
mode, fixture, title, filename?, request:{path, body?, mcp?, binary?},
topo:{type:'profile'|'project'|'source'|'binary'|'system', ...},
grow?, values?, summary}`) then navigate to `demo.html` / `console.html`,
which `SMS.launch.load()` on boot and redirect to their setup page when the
launch is missing or for the other page. Binary bytes exceed sessionStorage,
so `setup-prod.js` stashes them with `L.putBlob('binary', buf)` (IndexedDB
`sms-v3` / `blobs`) and `topology()` rehydrates `{topo, buf}` via
`SMS.topology.fromBinary`; `console.js` base64s the bytes (`bytesToB64`) into
the first `/ws/binary` frame (8 MiB cap, magic-checked server-side).

| Step | DOM ids | Render fn | Source |
|---|---|---|---|
| Start cards | `ver-btn`, `orch`, `lenses`, `fams` | `start.js` (`showLens`, version facts, `SMS.link.probe()` chip) | `index.html` → `demo-setup.html` / `prod-setup.html` / `visualizer.html` |
| Demo setup | `targets`, `demo-opts`, `demo-build-opts`, `req`, `summary`, `launch`, `src-live`, `src-fake` | `setup-demo.js` (`pick`/`setSource`/`request`/`start`) | `O.compile('fixture'\|'build', …)` → `WS {path}` + body preview, or fake-run note |
| Prod setup | `fixture-list`, `src-opts`, `run-opts`, `prop-opts`, `req`, `summary`, `launch`, `fake` | `setup-prod.js` (`setMode`/`preview`/`compile`/`launch`/`fake`) | `O.compile(mode, …)` per `O.SOURCES[mode]`; snippet/binary/system parse findings boxes (`s-`/`x-`/`y-findings`), provenance `#prov` |
| Demo visual | `comms`, `term`, `hex`, `stagebar`, `cap-*`, `st-*`, `verdict` (`v-pre`/`v-post`/`v-reg`/`v-sha`/`v-diff`) | `demo.js` (`run`/`onLine`/`onResult`/`showVerdict`/`onClose`) | Live `Session(request.path, request.body)` or `scenario.Replay(script(key, topo), result(key, topo))` |
| Console visual | `rail` (`r-target`/`r-sum`), `stagebar`, `graph`, `timeline`, `comms`, `log`, `inspect`, `result` (`r-facts`/`r-diff`/`r-usage`/`r-cycles`), `history`, scoreboard `sc-*` | `console.js` (`begin`/`start`/`onLine`/`onResult`/`onClose`/`resetRun`/`showTab`) | Live `Session` (+ `runSnippet` for `mcp:true` snippet mode) or `Replay`; `?sweep_passes`/`research` via `link.query()` |

## Key hooks (v3)

| Hook | Role |
|---|---|
| `SMS.launch.save/load/topology` (`core/handoff.js`) | Single chokepoint for setup → visual handoff; `load()` miss or wrong `page` redirects to setup |
| `SMS.link.probe()` (`stream/link.js`) | Bootstraps fixture list + readiness (`{online, ready, keyOk, docker, inferenceMode, health, targets, notes}`); never throws |
| `new SMS.link.Session(path, body, handlers)` | One live socket; routes `result`/`invalid`/`busy`/`graph`/`snapshot`/`telemetry_batch`/`msg` frames to handlers |
| `interp.line(team, msg, payload)` (`stream/interpreter.js`) | Single chokepoint for feed lines; widgets (`comms`, `activity`, `timeline`, `term`, `hex`) tap the returned `ev` |
| `#launch` / `#fake` click | `setup-prod.js` `launch()` (validates via `OptionForm.validate`, disabled until `probe().ready`) vs `fake()` (same lens, scripted events, no backend) |
| `stagebar` click | `StageBar onPick` → console `setStageFilter` → `activity.setStage` (+ `#stage-filter-note`); demo `StageBar` has no `onPick` |
| `[data-f]` / `#copy-log` click | Activity team filter (`all`/`red`/`blue`/`purple`/`green`/`yellow`/`orange`) / copy visible rows |
| WebSocket `onmessage` | Unparseable frame → `onLine('system', …)`; `snapshot` hydrates chips/counters only, never a stream line |
| `onResult` payload | Probe exits (`pre_probe_exit`/`post_probe_exit`), `regression_passed`, `receipt`/`verdict_receipt` (chain via `summarize`), `pass_results` sweep tally, `candidate.patch`/`cumulative_diff` |

Related: [MODULES.md](MODULES.md), [CLI.md](CLI.md).
