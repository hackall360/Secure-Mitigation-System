<!-- Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use. -->
<!-- https://polyformproject.org/licenses/noncommercial/1.0.0 -->
# Secure Mitigation System · Web UI v3

v3 replaces the v1/v2 stage-strip graph with a **radial "spider web" system map**. It also
splits the UI into a **Demo** page for presenting and a **Console** page for day-to-day use.
Both pages use the same rendering engine and talk to the same orchestrator endpoints as v2.

## Page flow

```
index.html  (start: name, version info, description)
 ├─ 1 Demo mode        → demo-setup.html  → demo.html      (cinematic, lighter runs)
 ├─ 2 Production mode  → prod-setup.html  → console.html   (full controls, workspace)
 └─ 3 Visualizer test  → visualizer.html                   (simulated, no backend)
```

| Page | Role |
|---|---|
| `index.html` | Start page. System name, **Version info** button (version, channel, build date, what's in the build, backend contract), short description, and the three choices. Keys `1` `2` `3`, `V` toggles version info. |
| `demo-setup.html` | Demo selection screen: demo target, event source (live orchestrator or fake run), lighter run settings, live map preview, request preview. **Start** opens the visual page. |
| `prod-setup.html` | Production selection screen: source (fixture, Green build, project, snippet, binary, repo ingest), target fields, operational mode and run controls, proposed controls, live map preview (parsed for snippets and binaries), summary and exact request. **Launch** or **Fake run**. |
| `demo.html` | Full-screen demo view. Starts the chosen run on arrival. Verdict card offers Run again, Change target and Home. |
| `console.html` | Production visual workspace. Starts the chosen run on arrival. A run rail shows the summary plus Stop, Run again, New run and Home. |
| `visualizer.html` | Visual test bench: scenario picker, play/pause/step/restart, speed, loop, event injection (probe, patch, re-probe, intel, discover, Green plants, burst ×20, 20 s silence, pass/fail verdicts) and layer toggles. Shows FPS, packets in flight and particle counts. |

The selection screens hand the compiled run to the visual pages through `js/core/handoff.js`
(sessionStorage; binaries go through IndexedDB because they can exceed storage limits).
Opening `demo.html` or `console.html` directly without a configured run redirects to the
matching setup screen.

## What the map shows

* **Center:** the target, drawn as a page, a city hub, a chip or a house depending on the lens (below).
* **Rings flowing outward:** named per lens (e.g. folders → files → symbols for a repo; hosts → services/ports → data for a system). Nodes
  that appear mid-run spawn at their parent and float out to their ring.
* **Data flow:** particles run along the program's paths (entry → handler → sink). When a probe
  exits `0`, the attack path turns red. After the patch, a blue shield sits on the guarded edge
  and particles stop there. On a verified verdict, everything locks purple.
* **Agents** orbit the web in six color families. Each agent in a family is a lighter or darker
  shade of the family color, one per personality:

| Family | Color | Agents (personality) |
|---|---|---|
| Offense | red | Warlord (commander), Breakwater (methodical), Lockpick (opportunist), Bloodhound (tracker), Sparkler (chaotic), Cartographer (mapper) |
| Defense | blue | Warden (commander), Bastion (hardener), Stitch (surgeon), Librarian (archivist), Sentinel (watcher), Proofreader (reviewer) |
| Verification | purple | Arbiter (judge), Notary (receipt custody), Mirror (differential) |
| Builder | green | Greenhouse (builder), Seedling (scaffolder) |
| Intel | yellow | Almanac (CVE/OSV/GHSA/EPSS), Lantern (scanners) |
| Orchestrator | orange | Conductor (sandbox lifecycle), Gauge (telemetry), Courier (ingest) |

* **Communication:** every orchestrator line becomes a labelled bubble that flies from the
  speaking agent to the agent or node it concerns, with a comet trail and an arrival ping. The
  same event also shows up in the comms feed, the typed terminal, the hexdump strip (the real
  bytes of the message) and the timeline.

## Four lenses, two reading levels

The same map changes its look depending on **what** is being checked, so anyone can tell at a
glance, and every phase is narrated twice: once in plain words, once in expert terms.

| Lens | Used for | In plain words | On the map |
|---|---|---|---|
| Single file | fixtures, Green build, snippets | a recipe card | ruled page with line numbers and a reading line; page-shaped center |
| Project / repo | local projects, repo ingest | a little city | a district per folder (named on the rim), files as buildings, folders grow as the stream names paths |
| Compiled binary | ELF / PE / Mach-O | a sealed machine | address ruler and section bands (a memory map); chip-shaped center |
| System snapshot | a clone or snapshot of a running system | a house with doors | a room per host, a brick wall with a door per public port; house-shaped center |

**Explain: Simple · Both · Expert** (key `E`) sits in the caption on the demo and visualizer
pages and above the map in the console. *Simple* swaps ring, family and node names for plain
ones (“A door”, “The safe”, “Attackers”, “Referees”), shows the “How to read this map” key, and
tells the story (“Red tried the door handle on the copy. If it opens, the lock is broken.”).
*Expert* shows exit codes, sinks, ports and the raw stream. *Both* shows both, which is the default
for presenting. The verdict card always gets an “In plain words” summary.

**System snapshot source** (production): describe the services, one per line —
`name image ports [public] [-> talks-to]` — and the map shows rooms, doors and the safe as you
type. It sends `WS /ws/system` (a proposed endpoint; see AGENTS.md §8.17).

**Showcase targets** so every lens can be shown: `repo_notes_app` (an ORDER BY injection that
crosses three files) and `system_shop_stack` (Redis left reachable from outside with no
password). They run as fake runs until the orchestrator lists the same keys.

## Topology sources (shown on the map as "provenance")

* **parsed · Snippet mode:** the pasted source is parsed in the browser (functions, routes,
  request inputs, imports, dangerous sinks). A candidate path input → function → sink is drawn
  as you type.
* **parsed · Binary mode:** ELF headers, sections, `.symtab`/`.dynsym` functions and imports are
  parsed in the browser. Dangerous imports (`strcpy`, `printf`, `system`, …) are flagged as
  sinks. Call edges are inferred, not disassembled. PE and Mach-O files fall back to a
  string-table scan.
* **modelled · Fixture/Project/Ingest modes:** a profile skeleton. Files, `functions()`,
  `VERB /routes` and CVE/GHSA ids named in the live stream are added to the map as they appear.
* **server · optional:** if the orchestrator sends `{"type":"graph","nodes":[…],"links":[…]}`
  on the socket, those nodes and links are merged in. No backend change is required to run v3.

## Backend contract (unchanged from v2)

`GET /api/health`, `GET /api/targets`, `WS /ws/combat/:target`, `WS /ws/project`, `WS /ws/demo`,
`WS /ws/binary`, `POST /mcp` (`tools/call submit_code_snippet`). Messages are `{team, msg}`,
`{type:"result", …}`, `{type:"busy"|"invalid", msg}`. The stage rules are the v2 `advanceStage()`
rules.

The six families are a visual mapping of the backend `team` values:
`red→red`, `blue→blue`, `green→green`, `research→yellow`, `system/telemetry/ingest→orange`.
Verification lines (fresh target, regression, receipt, differential) are drawn as purple.
Named agents in a message become the speaker and the recipient. Unnamed lines are attributed to
the family lead.

## Real time

Live runs on both pages render the orchestrator stream at its real pace. Nothing is sped up,
slowed down or buffered.

* **Bursts:** message bubbles are staggered and shortened while many are in flight, so a burst
  of events stays readable. Text panels (comms, activity, terminal) update immediately.
* **Quiet stretches:** model calls and Docker builds can go minutes without an event. The
  agent that spoke last gets a spinning ring, a live tether to the node it was working on,
  and a `WORKING m:ss` counter. The demo caption says who is busy and for how long.
* **Stream meter:** shown in both top bars. It reports connection state, events per minute
  and time since the last event, and turns orange after 45 s of silence.
* **Timestamps:** if a socket message carries `ts`, `time` or `timestamp` (seconds,
  milliseconds or ISO), that is used as the event time. Otherwise arrival time is used. The
  Console timeline inserts gap spacers sized by the real time between events (`+1:12`).

## Run controls (`js/options/`)

Every switch, text input, +/− stepper and operational mode is declared once in
`js/options/schema.js` (rendered by `js/options/form.js`, compiled by `js/options/compile.js`). Both pages render their controls from it, and it compiles the exact request
the orchestrator receives.

* **Operational modes:** Extra light → Ultra heavy, plus Custom. Cycles come from the mode;
  `/api/health.scan_profiles` overrides cycles and descriptions. Agent counts unlock in
  Ultra heavy, and cycles unlock in Custom (same rules as v2).
* **Controls:** switches (threat intel, scanners, consent, offline build), steppers with
  press-and-hold and Shift+↑/↓ ×10 (cycles, red/blue agents, context budget, sweep depth,
  flaw count, seed), text fields (paths, images, briefs, contracts, JSON argv), and
  segmented selectors.
* **Badges:** `query` marks settings sent as URL parameters. `not used` marks settings the
  chosen source's endpoint doesn't accept (fixture sockets take no body, for example).
* **Request preview** (Console): the exact WS path and JSON body that **Run** will send.
* **Proposed runtime controls** (Console): max runtime, probe timeout, parallel probes,
  require-regression, auto-rollback, stream verbosity and run label. These are **not part of
  the current backend contract**. They are UI-only unless **Send proposed controls** is on.
  Then they are sent as `body.ui_options{}`, or as `?opt_<key>=` when the endpoint has no
  body. To make one a real parameter, change its `group`/`proposed` entry in `FIELDS`.
* **Demo limits:** the Demo page uses the same schema with lighter limits. Only Extra light
  and Light modes, at most 3 cycles, sweep depth ≤ 2 and flaw count ≤ 3, plus fixed 5/5
  agents and a 32k budget for Green builds. The Console has the full range.
* **Saved settings:** values persist per source in `localStorage`. Pasted snippet source and
  binaries are never stored.

## Fake run

**Fake run** (both pages) plays scripted events through the same interpreter, so you can see
the visuals without a backend. It is always labelled `FAKE RUN · scripted` in the UI and in
the verdict. Only fake runs have a speed control (1× / 2× / 4×). Live runs are always real
time.

## Serving

All paths are relative. Serve this folder as static files:

* `python3 -m http.server` from this folder gives you fake runs only (no orchestrator), or
* drop it into the server's web directory: it is served at `/web/` with `/` redirecting to `/web/index.html`. v2
  served `index.html` at `/` with absolute `/static/...` assets, and v3's relative paths need
  the page URL to sit next to the assets.

Opening `demo.html` straight from disk (`file://`) works for fake runs.

## Keyboard

Demo: `1`–`5` target · `Enter` run · `Space` pause (fake run) · `→` step while paused ·
`D` director camera · `L` all labels · `F` fullscreen · `P` presenting (panels more opaque) ·
`Esc` stop.
Console: `Ctrl/⌘+Enter` run · `Esc` stop / clear selection · `0` fit map. Map: drag to pan,
scroll to zoom, double-click to dive in, click a node or agent to inspect it.

## Files

See **AGENTS.md** for the full directory map, data flow, API reference and step-by-step
recipes (adding parameters, sources, agents, fixtures and beats, and wiring the backend).
In short:

```
css/core/*        design system (tokens, surfaces, HUD, forms, motion)   css/pages/*  per-page layout
js/core/*         palette (agents/colors), version info, page hand-off
js/model/*        topology: fixture profiles, snippet + ELF parsers, live entity extraction
js/engine/*       SpiderGraph canvas engine (class + mixins)
js/stream/*       rules (backend wording), choreography beats, interpreter, fake runs, backend link
js/options/*      run-control schema, form renderer, request compiler
js/ui/*           HUD widgets and console views
js/pages/*        one controller per page
tools/            manifest.json + sync_assets.py (script/style tags), tests/smoke.js (headless suite)
```

No dependencies or build step. Canvas 2D only, no `innerHTML`/`eval`/inline scripts
(CSP-safe). DPR-aware, and honors `prefers-reduced-motion`.
