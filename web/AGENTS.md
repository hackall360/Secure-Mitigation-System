<!-- Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use. -->
<!-- https://polyformproject.org/licenses/noncommercial/1.0.0 -->
# AGENTS.md: guide for AI agents (and humans) working on SMS Web UI v3

Read this file before you change anything. It explains what the project is, the rules
you must not break, where everything lives, how data flows, and step-by-step recipes for
the changes people usually ask for.

---

## 1. What this is (and isn't)

* **It is:** the front end of the *Secure Mitigation System*. A static web UI that
  configures verification runs, sends them to an orchestrator backend, and renders the
  real-time event stream as a radial "spider web" system map. Agents (red/blue/purple/
  green/yellow/orange) orbit the map, and their messages fly across it as bubbles.
* **It is not:** the backend. Nothing here runs Docker, calls models, or verifies
  anything. The backend is a separate Python service (`python main.py --serve`). This UI
  only talks to it over HTTP and WebSocket (section 6).
* **No build step, no dependencies, no framework.** Plain HTML, CSS and classic `<script>`
  files that share one global namespace, `window.SMS`. It opens from any static server, and
  fake runs work even from `file://`.

---

## 2. Rules you must not break

1. **CSP-safe DOM only.** No `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `eval`,
   `new Function`, inline `<script>`, or inline `on*=` handlers. Build DOM with
   `SMS.hud.h(tag, className, text, attrs)` and set text with `textContent`.
2. **Classic scripts + namespace.** Every JS file is an IIFE that reads from and adds to
   `window.SMS`. Do not convert files to ES modules (that breaks `file://` and the load
   order). Load order is defined only in `tools/manifest.json` (section 9).
3. **Real time is sacred.** Live runs render at the pace the server streams. Never add
   speed-up, slow-down or buffering to live sessions. Only **fake runs** may change speed.
4. **Honesty labels stay.**
   * Fake runs are labelled `FAKE RUN · scripted` everywhere.
   * Topologies say `modelled` (template), `parsed` (from real code/binary) or `server`.
   * Proposed controls are badged `proposed`. They are sent only when "Send proposed
     controls" is on.
   * Don't present invented data as real.
5. **Don't change the wire contract by accident.** Requests are compiled in exactly one
   place (`js/options/compile.js`). Check the request preview or run the tests after any
   options change.
6. **Respect `prefers-reduced-motion`.** The engine checks `this.reduced`, and the CSS has
   `css/core/motion.css`.
7. **License header on every file.** The two-line "Required Notice … polyformproject" header
   goes at the top of each new JS, CSS and HTML file.
8. **After adding, removing or renaming any JS/CSS file:** update `tools/manifest.json`, then
   run `python3 tools/sync_assets.py`.

---

## 3. Pages and user flow

```
index.html (start: name, version info, description)
 ├─ 1 Demo mode        → demo-setup.html  → demo.html      (cinematic, lighter runs)
 ├─ 2 Production mode  → prod-setup.html  → console.html   (full controls + workspace)
 └─ 3 Visualizer test  → visualizer.html                   (simulated only, no backend)
```

| Page | Controller | Does |
|---|---|---|
| `index.html` | `js/pages/start.js` | Mode choice, version panel, orchestrator status |
| `demo-setup.html` | `js/pages/setup-demo.js` | Pick target + live/fake + light settings → saves a *launch* → `demo.html` |
| `prod-setup.html` | `js/pages/setup-prod.js` | Source, fields, run controls, request preview → saves a *launch* → `console.html` |
| `demo.html` | `js/pages/demo.js` | Reads launch, starts run immediately, cinematic HUD, verdict card |
| `console.html` | `js/pages/console.js` | Reads launch, starts run immediately, rail + map + inspector/comms/activity/result |
| `visualizer.html` | `js/pages/visualizer.js` | Scripted scenarios + event injection to test visuals |

The setup pages hand the run to the visual pages through `SMS.launch` (`js/core/handoff.js`),
which uses sessionStorage, plus IndexedDB for binaries. A visual page opened without a
launch redirects to its setup page.

---

## 4. Directory map

```
v3/
├─ AGENTS.md  README.md
├─ index.html  demo-setup.html  prod-setup.html  demo.html  console.html  visualizer.html
├─ favicon.svg
├─ css/
│  ├─ core/tokens.css      design tokens (colors, fonts) + reset      ← theme lives here
│  ├─ core/surfaces.css    CRT/noise, typography, glass, buttons, chips
│  ├─ core/hud.css         comms feed, legend, stage bar, terminal, hexdump, hover card, toast, meter
│  ├─ core/forms.css       inputs, diff, option controls (switch/stepper/segmented), request preview
│  ├─ core/explain.css     explain levels (.x-simple/.x-expert…), explainer box, map key, lens badge
│  ├─ core/motion.css      reduced-motion overrides (always last)
│  └─ pages/{start,setup,demo,console,visualizer}.css
├─ js/
│  ├─ core/
│  │  ├─ palette.js        6 agent families, 22 agents (color shades, personalities), node states, stage meta
│  │  ├─ lenses.js         the 4 target LENSES (file/repo/binary/system) + node-kind names, simple & expert → SMS.lenses
│  │  ├─ version.js        name / version / description / build notes  → SMS.version
│  │  └─ handoff.js        setup → visual page hand-off (sessionStorage + IndexedDB) → SMS.launch
│  ├─ model/               topology = "what the map shows"
│  │  ├─ topo-builder.js   topology format + builder helpers
│  │  ├─ topo-profiles.js  modelled maps for fixtures + generic projects
│  │  ├─ parse-source.js   snippet → real map (functions, routes, inputs, sinks)
│  │  ├─ parse-binary.js   ELF headers/sections/symbols/imports → real map
│  │  ├─ parse-system.js   services list (name image ports public -> deps) → system map with doors
│  │  ├─ topo-showcase.js  repo_notes_app + system_shop_stack (a showcase target per lens)
│  │  └─ extract.js        entities named in live lines (files, fn(), routes, CVEs, exit codes)
│  ├─ engine/              SpiderGraph canvas engine (constructor + mixins on its prototype)
│  │  ├─ kit.js            constants, math, glow sprites            → SMS.engine
│  │  ├─ graph.js          class + constructor + event emitter      → SMS.SpiderGraph
│  │  ├─ lens.js           per-lens backdrop, core shape, lens-only node kinds, ring/family labels
│  │  ├─ graph-model.js    nodes/links/states/select/describe
│  │  ├─ layout.js         radial tree layout + agent orbit
│  │  ├─ agents.js         speak / tether / team filter / working indicator
│  │  ├─ effects.js        send (bubbles) / wave / flowPath / guard / verdict
│  │  ├─ camera.js         fit / insets / director / zoom / transforms
│  │  ├─ input.js          pointer, wheel, resize, hit testing
│  │  ├─ loop.js           rAF loop + physics/particle/packet step
│  │  └─ render-*.js       scene (web, links), nodes (+labels), agents (+bubbles)
│  ├─ stream/              live event pipeline
│  │  ├─ rules.js          backend wording → stage / speaker / time / bubble label  ← edit when backend text changes
│  │  ├─ choreography.js   ordered "beats": what the map does per kind of line     ← edit to change reactions
│  │  ├─ narrator.js       the story in plain words + expert terms, per lens/phase/beat/verdict ← edit wording
│  │  ├─ interpreter.js    line() / result(): runs rules + beats, emits HUD events  → SMS.Interpreter
│  │  ├─ scenario.js       fake-run scripts + Replay player
│  │  └─ link.js           backend client: probe(), Session (WS), mcpSnippet(), download()
│  ├─ options/             run controls
│  │  ├─ schema.js         FIELDS, MODES, SOURCES, REQUIRED   ← add/rename backend parameters here
│  │  ├─ form.js           OptionForm renderer (switch / stepper / segmented / text / code / file)
│  │  └─ compile.js        values → { path, body } exactly as sent
│  ├─ ui/                  DOM widgets (each owns one piece of UI)
│  │  ├─ dom.js            h(), stamp, toast, counter, elapsed, scramble   → SMS.hud
│  │  ├─ explainer.js      SMS.explain level + ExplainToggle, Explainer, MapKey, lensBadge, lensIcon
│  │  ├─ comms-feed.js  legend.js  stage-bar.js  terminal.js  hex-stream.js  hover-card.js  stream-meter.js
│  │  └─ result-view.js  history.js  inspector.js  activity.js            → SMS.views (console only)
│  └─ pages/               one controller per HTML page (wiring only, no reusable logic)
└─ tools/
   ├─ manifest.json        which CSS/JS each page loads, in order
   ├─ sync_assets.py       regenerates the asset block in every page; --check for CI
   └─ tests/smoke.js       headless Playwright suite with a mocked backend (+ fixtures/)
```

**Layering (dependencies only point left):**
`core → model → engine → stream → options → ui → pages`.
A lower layer must never reference a page, and `engine` must not touch the DOM outside its
canvas.

---

## 5. Data flow (one live run)

```
setup page ──OptionForm values──► options.compile() ──► { path, body }
     │                                                     │
     └──► SMS.launch.save({ page, kind, request, topo, summary, … }) ──► navigate
                                                           │
visual page: SMS.launch.load() → SMS.launch.topology() → interp.load(topo)  (map drawn)
             new SMS.link.Session(path, body, handlers)   (WebSocket opens; body sent on open)
                 │
   server msg {team,msg,ts?} ─► handlers.onLine ─► interp.line(team,msg,meta)
                 │                                   ├─ rules.stageOf/verifierFor/bubbleLabel/eventTime
                 │                                   ├─ model.extract() → new nodes on the map
                 │                                   ├─ first matching beat in choreography.js → graph effects
                 │                                   └─ returns event {seq,at,speaker,to,label,stage,exit,beat…}
                 │                                        └─► comms feed, terminal, activity, timeline, meter, counters
   server msg {type:'result',…} ─► interp.result(p) ─► verdict visuals ─► result view / verdict card / history
   server msg {type:'busy'|'invalid',msg} ─► handlers.onRefuse
   server msg {type:'graph'|'topology',nodes,links} ─► handlers.onGraph (console merges into map)
```

Fake runs replace `Session` with `SMS.scenario.Replay`, which calls the **same handlers**.
That is why fake runs exercise the real pipeline.

---

## 6. Backend contract (v1/v2 + one proposed endpoint)

| Call | When | Body |
|---|---|---|
| `GET /api/health` | every page boot (`link.probe()`) | → `{ inference_mode, api_key_configured, inference_ready?, docker:{state:'ready'\|'images_missing'\|'unavailable'}, profiles:[{key,label,description,red_model,blue_model}], default_profile, scan_profiles:[{key,cycles,description}] }` |
| `GET /api/targets` | every page boot | → `{ <key>: { title, filename, description, lens? } }` · `lens` optional (`file`\|`repo`\|`binary`\|`system`); listing `repo_notes_app` / `system_shop_stack` makes those showcase cards runnable live |
| `WS /ws/combat/<fixture>?query` | Fixture source | no body |
| `WS /ws/project?query` | Project source | `{ path, image, command[], test_command[], contract, allow_remote_inference, scan_profile, cycles, red_agents, blue_agents, context_budget }` |
| `WS /ws/project?query` | Repo ingest | `{ ingest_repo, commit_hash }` |
| `WS /ws/demo?query` | Green build | `{ build_brief, vulns, theme, intel_offline, demo_size, flaw_count?, seed?, scan_profile, cycles, red_agents, blue_agents, context_budget }` |
| `WS /ws/binary?query` | Binary | `{ blob_b64, filename, contract }` |
| `WS /ws/system?query` | System snapshot (**proposed endpoint**) | `{ snapshot_ref, snapshot_kind:'image'\|'compose'\|'vm'\|'clone', services, contract, scan_profile, cycles, red_agents, blue_agents, context_budget }` · `services` is the text format in `model/parse-system.js` |
| `POST /mcp` | Snippet | JSON-RPC `tools/call submit_code_snippet {filename, language, source, contract}` → `result.structuredContent` |

Query parameters: `profile`, `sweep_passes` (omitted when 1), `research=on`,
`research_scanners=…`, and `opt_<key>` for proposed controls when the endpoint has no body.
Proposed controls go in `body.ui_options` when there is a body.

**Socket messages the UI understands:**
* `{ team, msg, ts? }`: a stream line. `team` is one of `red`, `blue`, `green`, `research`,
  `system`, `telemetry`, `ingest`. `ts` (or `time`/`timestamp`) can be seconds, ms or ISO.
* `{ type:'result', status, message, … }`: final verdict. Fields read: `status`,
  `pre_probe_exit`/`pre_exit_code`, `post_probe_exit`/`post_exit_code`, `regression_passed`,
  `baseline_passed`/`baseline_verification`, `receipt`/`verdict_receipt` (`patch_sha256`,
  `chain_ok`, `prev_receipt_sha`), `diff`/`cumulative_diff`, `cleanup_ok`, `usage.calls[]`,
  `cost_usd`, `total_tokens`, `compression`, `cycle_reports`/`cycles`, `pass_results`,
  `research_records`, `vault_recall`.
* `{ type:'busy'|'invalid', msg }`: the run was refused.
* `{ type:'graph', nodes:[{id,label,kind,parent}], links:[{source,target,kind}] }`
  (**optional, recommended**): real topology from the server, merged into the map in the console.

**Agent names in messages.** If a line contains an agent name (`Warlord`, `Breakwater`,
`Stitch`, `Arbiter`, …, see `core/palette.js`), the first name is the speaker and the second
is the recipient. Otherwise the family lead speaks for the backend team.

---

## 7. API reference (what each namespace exposes)

| Namespace | Key exports |
|---|---|
| `SMS.lenses` | `LENSES`, `ORDER`, `KINDS`, `of(topo)`, `get(key)`, `kind(lens, kind) → {simple, expert}`, `ring(lens, depth)` |
| `SMS.narrator` | `context(topo, graph)`, `intro(lens, ctx)`, `stage(lens, stage, ctx)`, `event(lens, ev, ctx, interp)`, `verdict(lens, result, ctx)` → `{simple, expert}` |
| `SMS.explain` | `level`, `set('simple'\|'both'\|'expert')`, `on(fn)`, `cycle()` — mirrors `body[data-explain]` |
| `SMS.palette` | `TEAMS`, `TEAM_ORDER`, `AGENTS`, `STATE`, `STAGES`, `STAGE_META`, `family(team)`, `agent(id)`, `teamAgents(team)`, `speakerFor(team)`, `namesIn(text)`, `rgba()`, `mix()` |
| `SMS.version` | `{ name, version, ui, channel, date, description, contract[], changes[] }` |
| `SMS.launch` | `save(obj)`, `load()`, `clear()`, `putBlob(name, buf)`, `getBlob(name)`, `topology(launch) → {topo, buf}`, `VERSION` |
| `SMS.topology` | `profile(key, target)`, `project(spec)`, `fromSource(src, lang, file)`, `fromBinary(buf, name)`, `fromSystem(text, ref, {kindLabel, provenance})`, `parseServices(text)`, `SHOP_STACK`, `extract(text)`, `parseElf(buf)`, `builder()`, `slug()` |
| `SMS.SpiderGraph` | `new SpiderGraph(canvas, {mode:'demo'\|'console', interactive, agents})`; see the engine API below |
| `SMS.rules` | `OK_STATUSES`, `stageOf()`, `verifierFor()`, `eventTime()`, `bubbleLabel()` |
| `SMS.choreography` | ordered array of `{ name, when(c), run(c) }` beats |
| `SMS.Interpreter` | `new Interpreter(graph)`, `.load(topo,{grow})`, `.line(team,msg,meta)`, `.result(p)`, `.on('stage'\|'event'\|'result'\|'load', fn)`, `.stats` |
| `SMS.scenario` | `script(key, topo, {grow})`, `result(key, topo)`, `Replay(lines, final, handlers)` |
| `SMS.link` | `probe()`, `Session(path, body, handlers)`, `open.{fixture,project,ingest,demo,binary}`, `mcpSnippet(args)`, `download(name, data)`, `bytesToB64(buf)`, `SAMPLE_TARGETS` |
| `SMS.options` | `FIELDS`, `MODES`, `RUN`, `PROPOSED`, `SOURCES`, `REQUIRED`, `OptionForm`, `compile(source, values, x)`, `spec()`, `defaults()` |
| `SMS.hud` | `h`, `stamp`, `toast`, `counter`, `elapsed`, `scramble`, `CommsFeed`, `Legend`, `StageBar`, `Terminal`, `HexStream`, `HoverCard`, `StreamMeter`, `ExplainToggle`, `Explainer`, `MapKey`, `lensBadge`, `lensIcon` |
| `SMS.views` | `renderResult(p,{source,started})`, `summarize(p)`, `RESULT_LABELS`, `RunHistory`, `renderInspect(root,d,{events,topo})`, `ActivityLog`, `Timeline` |

**SpiderGraph API (most used):**
* **Topology:** `setTopology(topo)`, `addNode(spec)`, `link(a,b,kind)`, `setState(id, state)`.
  `state` is one of `idle`, `scanned`, `suspect`, `compromised`, `blocked`, `patched`,
  `verified`, `grown`, `intel`.
* **Effects:** `send(from, to, {label, color, dur, delay})` (bubble), `wave(id, color)`,
  `sweepWave(color)`, `flowPath(ids, {color, count, speed, kind})`, `guard(a, b)`,
  `tether(agent, node)`, `speak(agent)`, `setWorking(agent, node)`,
  `setVerdict('verified'|'failed'|'clear')`.
* **Lens / reading level:** `setLens('file'|'repo'|'binary'|'system')` (set automatically by `setTopology` via `SMS.lenses.of`), `setExplain(level)` (ring + family labels).
* **Camera:** `fit()`, `setInsets({l,r,t,b})`, `setDirector(bool)`, `focus(id)`.
* **Layers:** `setLayer('web'|'flow'|'comms'|'sweep', bool)`, `setLayer('labels', 'auto'|'all'|'none')`,
  `setTeamFilter(Set)`.
* **Selection:** `select(id)`, `describe(id)`.
* **Events:** `on('select'|'hover'|'hovermove'|'speak'|'discover', fn)`.
* **Lifecycle:** `destroy()`.

---

## 7b. Lenses and the explain layer (read this before touching visuals or wording)

The same engine draws four kinds of target. The **lens** is chosen from the topology
(`topo.lens`, set by every builder; fallback `SMS.lenses.of(topo)`):

| Lens | Sources | Plain-words picture | What changes on the map (`engine/lens.js`) |
|---|---|---|---|
| `file` | fixtures, Green build, snippet | a recipe card | ruled page + line numbers + reading line; page-shaped core |
| `repo` | project, repo ingest, `repo_notes_app` | a little city | one district wedge per top-level folder, named on the rim; folders (`dir`) grow live from paths in the stream; hub core |
| `binary` | binary, `binary_argv_echo` | a sealed machine | rotating address ruler + section bands; chip core with pins |
| `system` | System snapshot, `system_shop_stack` | a house with doors | one room per host; brick perimeter wall with a **door per public port**; house core; ports named in the stream become `port` nodes |

**Two reading levels, always both available.** `SMS.explain.level` is `simple`, `both` or
`expert` (toggle: Simple · Both · Expert, key **E**; stored per page). Defaults: demo and
visualizer `both`, console `expert`. Everything that has words has them twice:
* node kinds, rings, families, states: `core/lenses.js` (`KINDS`, `LENS_KINDS`, `rings`), `core/palette.js` (`TEAMS[].kid/kidShort`, `STATE[].kid`);
* phases, beats, verdicts: `stream/narrator.js` (`STAGE`, `BEAT`, `verdict`) with `{entry}`, `{sink}`, `{thing}`… filled from `narrator.context()`.

Show/hide in HTML with classes, never JS: `.x-simple` (simple + both), `.x-expert` (expert +
both), `.x-expert-only`, `.x-simple-only`, `.x-both-only` (css/core/explain.css).
Rules: the plain line must be true (no invented facts), short, and free of jargon; the expert
line must name the real mechanism (exit codes, sinks, ports). Tests fail if a sentence is
missing or has an unfilled `{placeholder}`.

---

## 8. Recipes

### 8.1 Add or rename a backend parameter
1. In `js/options/schema.js`, add an entry to `FIELDS`:
   ```js
   max_depth: { type: 'number', group: 'run', label: 'Max call depth', wire: 'body', def: 6, min: 1, max: 32, step: 1, unit: 'levels', demo: { max: 8 } },
   ```
   * `type` is one of `toggle`, `number`, `text`, `textarea`, `code`, `segmented`, `select`, `file`.
   * `wire: 'body' | 'query' | 'ui'`. Optional: `lockedIf(v)`, `enabledIf(v)`, `validate(val, ctx)`,
     `parse(str)`, `encode(val, v)`, `omitIf(val)`, `optional`, `describe(n)`, and
     `demo: {…}` for overrides on the Demo page.
2. Make it appear and be sent:
   * **Run control (all sources):** add the key to `RUN`. For body params, also add it to each
     `SOURCES[x].run` list whose endpoint accepts it.
   * **Source field:** add it to `SOURCES[source].fields`, and to `REQUIRED[source]` if mandatory.
   * **Demo page:** add it to `DEMO_RUN`/`DEMO_BUILD` in `js/pages/setup-demo.js`.
3. If the shape is special (renamed key, derived value), adjust `compile()` in
   `js/options/compile.js`. Source-specific shaping lives at the bottom of that function.
4. Check the **Request preview** on `prod-setup.html`, then run the tests (section 10). Add an
   assertion in `tools/tests/smoke.js` → `options.compile matches the v2 wire contract`.

### 8.2 Promote a "proposed" control to a real parameter
Remove `proposed: true` and change `group: 'proposed'` to `'run'` (or move it to a source's
`fields`), then follow 8.1 step 2. It will then be sent as a normal key instead of
`ui_options`.

### 8.3 Add a new source mode (e.g. "Container image")
1. In `js/options/schema.js`, add `SOURCES.image = { label, sub, endpoint: () => '/ws/image', fields: [...], body: true, run: [...] }`,
   plus its `FIELDS` and `REQUIRED.image`.
2. In `prod-setup.html`, add a button
   `<button class="s-src c-mode" role="radio" data-mode="image">` to the `.s-sources` grid.
3. In `js/pages/setup-prod.js`, add entries to `TARGET_TITLE`, `LAUNCH_LABEL`, `targetName()`
   and `topoSpec()` (pick a topology, e.g. `{type:'project', spec:{…}}`).
4. Nothing else is needed for streaming: `console.js` opens `launch.request.path` with
   `launch.request.body`. Only add special handling in `start()` if the transport differs
   (like MCP or binary bytes).

### 8.4 The backend changed its wording and stages stopped advancing
Edit `stageOf()` in `js/stream/rules.js`. It is a plain list of `text.includes(...)` checks
mirroring the server's phrases. Keep its return values within `SMS.palette.STAGES`. For the
purple speaker selection, edit `verifierFor()`.

### 8.5 Change how the map reacts to a kind of line
Edit or insert a beat in `js/stream/choreography.js`. Beats are tried in order and the first
`when(c)` that is true wins. Put specific beats above general ones. Inside `run(c)`, set
`c.to`, `c.label` and `c.focus`, and call graph effects (`c.g.flowPath`, `c.g.setState`,
`c.g.guard`, …). Interpreter state lives on `c.it` (`patched`, `compromised`, `stats`,
`_grow()`). Every emitted event records `ev.beat`, so you can see in tests which beat fired.

### 8.6 Add an agent or personality
Add a record to `AGENTS` in `js/core/palette.js`:
`{ id:'Ghost', team:'red', color:'#ff7a8a', glyph:'Gh', personality:'Stealthy', role:'Low-and-slow probes' }`.
* Pick a lighter or darker shade of the family hue.
* Exactly one agent per family has `leader:true`.
* Layout, legend, name detection and colors all update automatically.

### 8.7 Add an agent family / color
Add the family to `TEAMS` (with a `hue` and an `angle` on the orbit) and to `TEAM_ORDER` in
`core/palette.js`. Add its agents (8.6). If backend teams should map to it, update
`TEAM_ALIAS` and `DEFAULT_SPEAKER`. Optionally add a CSS variable in `css/core/tokens.css`
and the `[data-team=...]` color rules in `css/core/hud.css` (terminal/hexdump prompts).

### 8.8 Add a fixture's map
Add a builder to `PROFILES` in `js/model/topo-profiles.js` (copy `node_query_sink`). It must
define `attackPath`, `entryId`, `sinkId` and `guardLink`. Optionally map file extensions in
`guessProfile()`. For fake runs, add a `VOCAB` entry in `js/stream/scenario.js`. For the badge
color, add the key to `BADGES` in `setup-prod.js` and `TARGET_BADGE` in `setup-demo.js`.

### 8.9 Use real topology from the server
Have the backend send `{ "type":"graph", "nodes":[{id,label,kind,parent}], "links":[{source,target,kind}] }`.
`link.js` routes it to `onGraph` in `console.js`, which merges it into the map. To support
it on the demo page as well, add the same `onGraph` handler in `js/pages/demo.js`.

### 8.10 Show a new result field
In `js/ui/result-view.js` → `renderResult()`, add `fact('Label', value, good?)`. Here `good`
is `true` (green), `false` (red) or `undefined` (neutral). For the demo verdict card, edit
`showVerdict()` in `js/pages/demo.js` and the `v-facts` markup in `demo.html`.

### 8.11 Add a page or a module file
Create the file (with the license header). Add it to the right group or page in
`tools/manifest.json` (groups are expanded in order). Then run `python3 tools/sync_assets.py`.
The script refuses to finish if a file is missing or unreferenced.

### 8.12 Change the look
* **Theme colors / fonts:** `css/core/tokens.css`.
* **Canvas colors** are in JS: `core/palette.js` (`TEAMS`, `AGENTS`, `STATE`) and
  `engine/render-*.js`.
* **Ring spacing and limits:** `engine/kit.js` (`RING0`, `RING_STEP`, `MAX_PACKETS`, `MAX_PARTICLES`).
* **Bubble pacing:** `send()` in `engine/effects.js`.
* **Working indicator:** `_drawWorking()` in `engine/render-agents.js`.

### 8.13 Release
Bump `version`/`date` and append to `changes` in `js/core/version.js`. The start page's
Version info panel reads from it.

### 8.14 Wire into the Python server
Serve this folder statically (e.g. at `/static/`) and redirect `/` to `/static/index.html`.
All asset paths are relative. `/api/*`, `/ws/*` and `/mcp` must stay on the same origin.

### 8.15 Add a lens (e.g. "mobile app" or "cloud account")
1. `core/lenses.js`: add the entry to `LENSES` (label, metaphor, simple/expert, rings, words), `ORDER`, and any `LENS_KINDS` overrides; teach `of()` to detect it.
2. `engine/lens.js`: add a backdrop function to the map in `_drawLensBackdrop`, a core outline in `_drawCoreShape`, and shapes/radii for any new node kinds in `_drawLensKind` / `_lensKindRadius`.
3. `stream/narrator.js`: add the lens key to every `STAGE` entry that is lens-specific (or rely on `any`).
4. `ui/explainer.js`: `LENS_ICON[key]` and `KEY_BY_LENS[key]` (which kinds the map key lists).
5. A builder that sets `lens: '<key>'` (a parser in `model/` or a profile in `topo-showcase.js`), a fake-run vocabulary in `stream/scenario.js`, and a scenario in `pages/visualizer.js` `SCENARIOS`.
6. Run the suite: the narrator test checks every lens × phase.

### 8.16 Change the plain-words or expert wording
Edit `stream/narrator.js` (phases, events, verdicts) or `core/lenses.js` (names of things).
Do not put wording in page controllers. Keep `{placeholders}` to the keys `narrator.context()` returns.

### 8.17 Wire the System snapshot source to the backend
The UI already sends `WS /ws/system` with the body in §6 (source `system` in `options/schema.js`,
marked `proposed`). Implement the endpoint to restore the snapshot into an isolated network,
stream the usual `{team,msg}` lines (mention ports as `6379/tcp` so they light up as doors), and
send the usual `result`. To route it elsewhere, change `SOURCES.system.endpoint` only. When it is
real, drop `proposed: true` and the "proposed" wording in `SOURCES.system.sub`.

---

## 9. Asset loading (manifest)

`tools/manifest.json` → `groups` (`@core-css`, `@core`, `@model`, `@engine`, `@stream`,
`@options`, `@ui`, `@ui-console`, `@lib`, …) and `pages` (`styles` + `scripts` per HTML file).
`python3 tools/sync_assets.py` rewrites the block between `<!-- assets:begin -->` and
`<!-- assets:end -->` in each page. Never hand-edit that block. Within a group, order matters:
`kit` before `graph` before mixins, `dom` before widgets, `schema` before `form`/`compile`.

---

## 10. Testing

```bash
cd v3 && python3 -m http.server 8765 &
python3 tools/sync_assets.py --check          # manifest ↔ pages ↔ files
node tools/tests/smoke.js                     # headless suite; add --shots /tmp/shots for screenshots
```

The suite needs Playwright (`require('playwright')`). It mocks `/api/*` and `/ws/*`, so no
backend is required. It covers:
* page loads and the redirect for visual pages opened without a run;
* the request contract;
* interpreter stages, taint, patch and verdict, plus which beats fired;
* ELF parsing;
* the demo and production flows, both fake and live;
* binary bytes reaching the socket;
* visualizer injections;
* lenses (every source → right lens, `/ws/system` request), the services parser, narrator coverage
  for every lens × phase, the Explain switch, each visualizer lens, a system showcase demo with a
  plain-words verdict, and a live System snapshot run.

Add a test with `test('name', async (page, log) => { … }, { live: true })`.

**Manual check after visual changes:** open `visualizer.html`, press Play, then try
*Burst ×20*, *Silence 20s* (look for the `WORKING m:ss` indicator) and *Verdict · pass/fail*.
Repeat at 1280×720 and with the OS set to reduced motion.

---

## 11. Gotchas

* **Explain classes need `body[data-explain]`.** Pages without an `ExplainToggle` set
  `document.body.dataset.explain` themselves (setup pages and the start page use `both`).
* **Showcase targets** (`repo_notes_app`, `system_shop_stack`, and `binary_argv_echo` on the demo
  page) are fake-run only unless `/api/targets` lists the same key; the demo setup dims them in live mode.
* **CSS class collisions.** Page CSS files share one cascade. For example, `.k` is the
  console map-key swatch, which is why the request preview uses `.rk`. Prefix new classes
  (`c-` console, `d-` demo, `s-` setup, `v-` visualizer, `l-` start).
* **The `hidden` attribute.** It is enforced with `[hidden]{display:none!important}`. Toggle
  `el.hidden`, not inline styles.
* **IDs are API.** Page controllers look up elements by `id`. If you rename an id in HTML,
  search `js/pages/` (and `ui/result-view.js`, which targets the console Result pane ids).
* **Side panels use `overflow: clip`,** so focusing a field can't scroll the panel out of
  alignment.
* **The engine is shared by all pages.** Test changes there on `demo.html`, `console.html`
  and `visualizer.html`.
* **`SMS.launch`** lives in sessionStorage, so it is per tab. Binaries live in IndexedDB under
  the key `binary`, and the latest one wins.
* **Opened from `file://`:** `link.probe()` reports offline and only fake runs and
  the visualizer work.
