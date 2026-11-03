# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Parity wave W6 RED: MCP ops/showcase status tools (offline dispatch).

TWO new offline tools in ``modules.services.mcp_bridge``:

- ``sms_ops_status`` (no args): docker state + missing images + leftover
  containers + cleanup preview + effective knobs + showcase presence —
  same payload shape as CLI ``--ops-status --format json``.
- ``sms_showcase_status`` (no args): TTS/capture/music/render static
  presence (file checks only; nothing started, no servers).

Fail closed: daemon-unreachable (``docker.state == "unavailable"``) or any
exception → JSON-RPC ``-32603`` with a message, never raises. Docker fakes
are injected by monkeypatching ``modules.services.sms_api.docker_health``
(etc.) at the ``sms_api`` module level — the same pattern the CLI parity
tests use. ``showcase_status`` is static only (no servers).

RED-first: tools/list must contain both tools; ops dispatch with a faked
daemon returns the full payload; unreachable daemon → -32603.
"""

from modules.services import mcp_bridge
from modules.services.mcp_bridge import handle_mcp_request


def _rpc(method, params=None, rpc_id=1):
    body: dict = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


def _ready_docker():
    return {"state": "ready", "missing_images": [], "leftover_containers": 0}


def _patch_ops_fakes(monkeypatch):
    from modules.services import sms_api

    monkeypatch.setattr(sms_api, "docker_health", lambda *a, **k: _ready_docker())
    monkeypatch.setattr(
        sms_api,
        "cleanup_preview",
        lambda *a, **k: {"containers": [], "networks": [], "images": []},
    )
    monkeypatch.setattr(
        sms_api,
        "effective_knobs",
        lambda *a, **k: {
            "timeout_seconds": 60,
            "max_tokens": 4096,
            "reasoning_effort": "medium",
            "verifier_timeout": 120,
            "research_scanners": [],
        },
    )
    monkeypatch.setattr(
        sms_api,
        "showcase_status",
        lambda *a, **k: {
            "tts": {
                "present": True,
                "port": 8002,
                "health_url": "http://127.0.0.1:8002/healthz",
            },
            "capture": {"present": False, "scripts": []},
            "music": {"present": False, "final_bed": None},
            "render": {"script_present": False, "bash_syntax_ok": False},
        },
    )


def test_tools_list_contains_ops_and_showcase_status():
    body = handle_mcp_request(_rpc("tools/list"))
    names = [t["name"] for t in body["result"]["tools"]]
    assert "sms_ops_status" in names
    assert "sms_showcase_status" in names
    for tool in body["result"]["tools"]:
        if tool["name"] in ("sms_ops_status", "sms_showcase_status"):
            assert tool["inputSchema"]["properties"] == {}
            assert "outputSchema" in tool


def test_ops_status_returns_cli_json_payload_shape(monkeypatch):
    _patch_ops_fakes(monkeypatch)
    body = handle_mcp_request(_rpc("tools/call", {"name": "sms_ops_status", "arguments": {}}))
    assert "error" not in body, body
    structured = body["result"]["structuredContent"]
    # Same payload shape as CLI --ops-status --format json.
    assert {"docker", "cleanup_preview", "knobs", "showcase"} <= set(structured)
    assert structured["docker"]["state"] == "ready"
    assert structured["docker"]["missing_images"] == []
    assert structured["docker"]["leftover_containers"] == 0
    assert "timeout_seconds" in structured["knobs"]
    assert {"tts", "capture", "music", "render"} <= set(structured["showcase"])


def test_ops_status_daemon_unreachable_fails_closed(monkeypatch):
    from modules.services import sms_api

    _patch_ops_fakes(monkeypatch)
    monkeypatch.setattr(
        sms_api,
        "docker_health",
        lambda *a, **k: {
            "state": "unavailable",
            "missing_images": [],
            "leftover_containers": 0,
        },
    )
    body = handle_mcp_request(_rpc("tools/call", {"name": "sms_ops_status", "arguments": {}}))
    assert body["error"]["code"] == -32603
    assert body["error"]["message"]


def test_ops_status_exception_never_raises(monkeypatch):
    from modules.services import sms_api

    _patch_ops_fakes(monkeypatch)

    def _boom(*a, **k):
        raise RuntimeError("daemon down")

    monkeypatch.setattr(sms_api, "docker_health", _boom)
    body = handle_mcp_request(_rpc("tools/call", {"name": "sms_ops_status", "arguments": {}}))
    assert body["error"]["code"] == -32603


def test_showcase_status_returns_static_presence(monkeypatch):
    _patch_ops_fakes(monkeypatch)
    body = handle_mcp_request(_rpc("tools/call", {"name": "sms_showcase_status", "arguments": {}}))
    assert "error" not in body, body
    structured = body["result"]["structuredContent"]
    # Static presence only: TTS/capture/music/render, nothing started.
    assert {"tts", "capture", "music", "render"} <= set(structured)
    assert structured["tts"]["present"] is True
    assert structured["tts"]["port"] == 8002


def test_showcase_status_exception_never_raises(monkeypatch):
    from modules.services import sms_api

    _patch_ops_fakes(monkeypatch)

    def _boom(*a, **k):
        raise RuntimeError("no root")

    monkeypatch.setattr(sms_api, "showcase_status", _boom)
    body = handle_mcp_request(_rpc("tools/call", {"name": "sms_showcase_status", "arguments": {}}))
    assert body["error"]["code"] == -32603


def test_bridge_registry_lists_both_tools():
    names = [t["name"] for t in mcp_bridge.MCP_TOOLS]
    assert "sms_ops_status" in names
    assert "sms_showcase_status" in names
