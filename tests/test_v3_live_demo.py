"""v3 demo.html consumes LIVE server frames (node vm against the real demo.js / setup-demo.js).

Graph/topology frames must grow the map, the connect-time snapshot must hydrate
HUD counters without becoming a stream line, and a live launch must open a real
link.Session (never a scripted Replay).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from library.services.telemetry_hub import build_snapshot

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
const fs = require('fs'); const vm = require('vm');
const frames = JSON.parse(process.argv[2]);
const out = { sessions: 0, replays: 0, lines: [], nodes: [], links: [], els: {} };
const anyObj = () => new Proxy(function () {}, { get: (t, k) => k === 'then' ? undefined : anyObj(), apply: () => anyObj(), construct: () => anyObj() });
const els = {};
function el(id) {
  if (!els[id]) els[id] = { id, dataset: {}, textContent: '', hidden: false, style: {}, lastChild: { textContent: '' },
    addEventListener() {}, setAttribute() {}, getAttribute: () => 'true', getBoundingClientRect: () => ({ right: 0, left: 0, top: 0, bottom: 0 }),
    classList: { add() {}, remove() {}, toggle() {} }, appendChild() {}, querySelector: () => null, offsetParent: null };
  return els[id];
}
class Graph { constructor() { this.nodes = new Map(); this.lens = 'file'; }
  addNode(n) { this.nodes.set(n.id, n); out.nodes.push(n.id); } link(a, b, k) { out.links.push([a, b, k]); }
  setInsets() {} setDirector() {} setExplain() {} select() {} }
class Interp { constructor(g) { this.g = g; this.stats = { findings: 0, patches: 0, verified: 0 }; }
  load() {} on() {} line(team, msg) { out.lines.push([team, msg]); return { team, msg }; } }
let handlers = null;
const SMS = {
  hud: new Proxy({ h: () => anyObj(), lensBadge() {}, toast() {}, elapsed: () => '00:00', scramble() {},
    counter: (e, v) => { e.textContent = String(v); e.dataset.v = String(v); } }, { get: (t, k) => k in t ? t[k] : class { constructor() { return anyObj(); } } }),
  narrator: new Proxy({ context: () => ({}), intro: () => '' }, { get: (t, k) => k in t ? t[k] : () => null }), palette: { STAGE_META: {}, AGENTS: [] }, explain: { on() {} },
  launch: { load: () => ({ page: 'demo', kind: 'live', title: 'T', filename: 'app.js', request: { path: '/ws/combat/node_query_sink' } }),
    topology: async () => ({ topo: { type: 'profile' } }) },
  SpiderGraph: Graph, Interpreter: Interp,
  link: { Session: class { constructor(p, b, h) { out.sessions++; handlers = h; } } },
  scenario: { Replay: class { constructor() { out.replays++; } start() { return this; } setSpeed() {} }, script() {}, result: () => ({}) },
};
const ctx = { SMS, console, setTimeout, clearTimeout, setInterval: () => 0, clearInterval() {}, requestAnimationFrame() {},
  innerWidth: 1000, innerHeight: 800, addEventListener() {}, getComputedStyle: () => ({ display: 'block' }),
  location: { replace() {}, href: '' }, localStorage: { getItem: () => null, setItem() {} },
  document: { getElementById: el, querySelector: () => ({ dataset: { speed: '1' }, getBoundingClientRect: () => ({}), offsetParent: null }), querySelectorAll: () => [], addEventListener() {}, body: { dataset: {}, classList: { toggle() {} } } } };
ctx.window = ctx; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
setTimeout(() => {
  frames.forEach((f) => {
    if (f.type === 'graph' || f.type === 'topology') handlers.onGraph && handlers.onGraph(f);
    else if (f.type === 'snapshot') handlers.onSnapshot && handlers.onSnapshot(f);
  });
  out.hasGraph = !!handlers.onGraph; out.hasSnapshot = !!handlers.onSnapshot;
  ['st-nodes', 'st-msgs', 'st-find', 'st-patch', 'st-ver'].forEach((k) => { out.els[k] = el(k).textContent; });
  process.stdout.write(JSON.stringify(out));
}, 50);
"""

node = pytest.mark.skipif(shutil.which("node") is None, reason="node required")


def _run(frames):
    res = subprocess.run(
        ["node", "-e", HARNESS, str(ROOT / "web/js/pages/demo.js"), json.dumps(frames)],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    return json.loads(res.stdout)


@node
def test_live_launch_opens_real_session_not_replay():
    out = _run([])
    assert out["sessions"] == 1 and out["replays"] == 0


@node
def test_graph_frames_add_nodes_and_links():
    out = _run(
        [
            {
                "type": "graph",
                "nodes": [
                    {"id": "fn:login", "label": "login", "kind": "function", "parent": "app.js"}
                ],
                "links": [{"source": "fn:login", "target": "app.js"}],
            },
            {
                "type": "topology",
                "nodes": [{"id": "db", "label": "db", "kind": "service"}],
                "links": [],
            },
        ]
    )
    assert out["hasGraph"]
    assert out["nodes"] == ["fn:login", "db"]
    assert out["links"] == [["fn:login", "app.js", "call"]]
    assert out["els"]["st-nodes"] == "2"


@node
def test_snapshot_hydrates_counters_without_stream_line():
    snap = build_snapshot(targets={"node_query_sink": {}}, docker_state="ready", key_ok=True)
    snap["hud"].update({"findings": 3, "patches": 2, "verified": 1})
    out = _run([snap])
    assert out["hasSnapshot"]
    assert out["lines"] == []
    assert out["els"]["st-find"] == "3"
    assert out["els"]["st-patch"] == "2"
    assert out["els"]["st-ver"] == "1"
    # Roster nodes in the snapshot are targets list, not this run's map.
    assert out["nodes"] == []


def test_setup_demo_defaults_live_when_ready():
    src = (ROOT / "web/js/pages/setup-demo.js").read_text()
    assert "setSource(link.ready ? 'live' : 'fake')" in src
    demo = (ROOT / "web/js/pages/demo.js").read_text()
    assert "state.launch.kind === 'live' ? 'live' : 'fake'" in demo
