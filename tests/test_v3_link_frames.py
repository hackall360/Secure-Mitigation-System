"""v3 link.js frame routing against the REAL server frame shapes (node vm, no mocks of link.js).

Server sends build_snapshot() on connect and telemetry_batch bursts; the v3
client must route them as state / per-event lines, never as blank stream lines.
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
const calls = [];
class FakeWS { constructor(url) { this.url = url; this.readyState = 1; FakeWS.last = this; } send() {} close() {} }
FakeWS.OPEN = 1;
const ctx = { window: {}, location: { protocol: 'http:', host: 'localhost' }, WebSocket: FakeWS, console };
ctx.window = ctx; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
new ctx.SMS.link.Session('/ws/combat/node_query_sink', undefined, {
  onLine: (t, m) => calls.push(['line', t, m]),
  onSnapshot: (p) => calls.push(['snapshot', p.type]),
  onResult: (p) => calls.push(['result', p.status]),
});
frames.forEach((f) => FakeWS.last.onmessage({ data: JSON.stringify(f) }));
process.stdout.write(JSON.stringify(calls));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node required (gate runs node --check)")
def test_server_frames_route_to_state_and_real_lines():
    frames = [
        build_snapshot(targets={"node_query_sink": {}}, docker_state="ready", key_ok=True),
        {
            "type": "telemetry_batch",
            "team": "telemetry",
            "count": 2,
            "events": [
                {"team": "telemetry", "msg": "vault indexed 1"},
                {"team": "telemetry", "msg": "vault indexed 2"},
            ],
        },
        {"team": "red", "msg": "Analyzing app.js.", "type": "log", "ts": 1.0},
        {"type": "result", "status": "verified"},
    ]
    out = subprocess.run(
        ["node", "-e", HARNESS, str(ROOT / "web/js/stream/link.js"), json.dumps(frames)],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    calls = json.loads(out.stdout)
    assert calls == [
        ["snapshot", "snapshot"],
        ["line", "telemetry", "vault indexed 1"],
        ["line", "telemetry", "vault indexed 2"],
        ["line", "red", "Analyzing app.js."],
        ["result", "verified"],
    ]
    # No blank/undefined stream line ever reaches the interpreter.
    assert not any(c[0] == "line" and not c[2] for c in calls)
