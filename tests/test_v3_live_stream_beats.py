"""Real backend stream -> real v3 interpreter (node vm, no mocks of the unit).

LINES is the verbatim live stream captured from the offline server
(`ui_scan.start_server(offline=True)`, node_query_sink, 2026-11-02): the same
emits as library/workflows/workflow.py (pre-probe :378, blue :451/:467-468,
post-probe :497). The v3 interpreter must count the finding, the patch and
reach the verdict from these lines alone.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

LINES = [
    ["system", "Connected: muse-spark-1.3-contributor vs muse-wonder-1.0 (profile balanced)."],
    [
        "system",
        "[phase baseline] Creating an internal Docker network and immutable target snapshot.",
    ],
    ["system", "[phase baseline] Original fixture is ready; normal-input checks passed."],
    ["red", "[phase red probe] Analyzing app.js with muse-spark-1.3-contributor."],
    ["red", "[phase red probe] Boundary check exited 0."],
    ["blue", "[phase blue patch] Requesting a sanitization patch from muse-wonder-1.0."],
    ["blue", "Known minimal sanitization (offline check)"],
    [
        "blue",
        "--- a/node_query_sink/app.js\n+++ b/node_query_sink/app.js\n@@ -13,6 +13,11 @@\n+  if (!/^[0-9]+$/.test(id)) return;",
    ],
    ["system", "[phase blue patch] Starting a fresh target from the patched snapshot."],
    ["blue", "[phase verify] Post-patch boundary check exited 1."],
    ["system", "[phase cleanup] Session containers, snapshots, and network removed."],
]

HARNESS = r"""
const fs = require('fs'); const vm = require('vm'); const path = require('path');
const [root, files, lines] = [process.argv[1], JSON.parse(process.argv[2]), JSON.parse(process.argv[3])];
const noop = () => {};
const ctx2d = new Proxy({}, { get: (t, k) => (k in t ? t[k] : (k === 'measureText' ? () => ({ width: 10 }) : (k === 'createRadialGradient' || k === 'createLinearGradient' ? () => ({ addColorStop: noop }) : noop))), set: (t, k, v) => { t[k] = v; return true; } });
const el = () => ({ getContext: () => ctx2d, addEventListener: noop, removeEventListener: noop, getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600 }), style: {}, width: 800, height: 600, setAttribute: noop, classList: { add: noop, remove: noop, toggle: noop } });
const ctx = { console, Math, Date, JSON, setTimeout: noop, clearTimeout: noop, setInterval: noop, clearInterval: noop,
  requestAnimationFrame: noop, cancelAnimationFrame: noop, devicePixelRatio: 1, performance: { now: () => 0 },
  matchMedia: () => ({ matches: true, addEventListener: noop }), addEventListener: noop, removeEventListener: noop,
  ResizeObserver: class { observe() {} disconnect() {} },
  document: { createElement: el, addEventListener: noop, body: { dataset: {} }, documentElement: { dataset: {} } },
  location: { protocol: 'http:', host: 'localhost' }, localStorage: { getItem: () => null, setItem: noop }, sessionStorage: { getItem: () => null, setItem: noop } };
ctx.window = ctx; ctx.self = ctx; vm.createContext(ctx);
for (const f of files) vm.runInContext(fs.readFileSync(path.join(root, f), 'utf8'), ctx, { filename: f });
const out = vm.runInContext(`(() => {
  const g = new SMS.SpiderGraph(document.createElement('canvas'), { mode: 'console' });
  const it = new SMS.Interpreter(g);
  it.load(SMS.topology.profile('node_query_sink', {}));
  const beats = ${JSON.stringify(lines)}.map(([t, m]) => { const e = it.line(t, m); return e.beat || null; });
  it.result({ status: 'verified', pre_probe_exit: 0, post_probe_exit: 1 });
  return { findings: it.stats.findings, patches: it.stats.patches, verified: it.stats.verified, patched: !!it.patched, beats, verdict: g.verdict };
})()`, ctx);
process.stdout.write(JSON.stringify(out));
"""


def _scripts():
    m = json.loads((ROOT / "web/tools/manifest.json").read_text())

    def expand(items):
        out = []
        for it in items:
            out += expand(m["groups"][it]) if it.startswith("@") else [it]
        return out

    # Engine + model + stream only: the interpreter's real dependency chain.
    return [s for s in expand(["@core", "@model", "@engine", "@stream"])]


@pytest.mark.skipif(shutil.which("node") is None, reason="node required")
def test_real_backend_stream_counts_finding_patch_and_verdict():
    res = subprocess.run(
        ["node", "-e", HARNESS, str(ROOT / "web"), json.dumps(_scripts()), json.dumps(LINES)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0, res.stderr[-2000:]
    out = json.loads(res.stdout)
    assert out["findings"] == 1, out
    assert out["patches"] == 1, out  # exactly one patch, not one per blue line
    assert out["patched"] is True, out
    assert out["verdict"] == "verified", out
