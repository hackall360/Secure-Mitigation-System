# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: /ws/demo hostile-JSON inf must fall back, never raise (task-011).

json.loads decodes Infinity/-Infinity/1e999 to float inf (allow_nan default),
and the __demo__ parsing block's int() guards catch (TypeError, ValueError)
only -> OverflowError escapes into run_socket's generic handler (a bare
"Scan failed" error result, or worse, a dropped socket) instead of the
documented fail-closed defaults. Post-fix: inf takes the same fallback path
as garbage strings (cycles/flaw/seed None, red/blue/budget defaults).
"""

import json as _json

from fastapi.testclient import TestClient

import main as _main
from modules.core.config import PurpleBoxConfig


def _run_demo_with(payload_text, monkeypatch):
    seen = {}

    async def fake_build(emit, config, **kwargs):
        seen.update(kwargs)
        await emit("green", "done")
        return {"status": "no_findings", "message": "probe", "project": "ai-demo"}

    monkeypatch.setattr(_main, "run_demo_build", fake_build)
    monkeypatch.setenv("META_MUSE_API_KEY", "test-key")
    monkeypatch.setattr(_main, "load_config", lambda: PurpleBoxConfig(meta_api_key="test-key"))
    app = _main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        headers = {"origin": "http://localhost"}
        with client.websocket_connect("ws://localhost/ws/demo", headers=headers) as socket:
            socket.send_text(payload_text)
            while True:
                event = socket.receive_json()
                if event["type"] in ("result", "invalid", "error"):
                    return event, seen


def test_demo_request_survives_infinity_json(monkeypatch):
    hostile = (
        '{"theme": "xss", "cycles": Infinity, "red_agents": Infinity,'
        ' "blue_agents": -Infinity, "context_budget": Infinity,'
        ' "flaw_count": Infinity, "seed": Infinity}'
    )
    event, seen = _run_demo_with(hostile, monkeypatch)
    assert event["type"] == "result", event
    assert seen.get("cycles") is None, seen
    assert (seen.get("red_agents"), seen.get("blue_agents")) == (5, 5), seen
    assert seen.get("context_budget") == 32768, seen
    assert seen.get("flaw_count") is None, seen
    assert seen.get("seed") is None, seen


def test_demo_request_survives_overflow_float_json(monkeypatch):
    hostile = _json.dumps(
        {
            "theme": "xss",
            "cycles": 1e999,
            "red_agents": 1e999,
            "context_budget": 1e999,
            "flaw_count": 1e999,
            "seed": 1e999,
        }
    )
    event, seen = _run_demo_with(hostile, monkeypatch)
    assert event["type"] == "result", event
    assert seen.get("cycles") is None, seen
    assert seen.get("red_agents") == 5, seen
    assert seen.get("context_budget") == 32768, seen
