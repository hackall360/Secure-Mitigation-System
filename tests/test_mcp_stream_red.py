# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: pollable MCP scan-status contract (W1-mcp-surface).

Per W1-mcp-surface, scan execution is final-receipt-only with no progress
streaming. Clients therefore need a pollable status tool so a long Docker
scan does not look hung: `sms_scan_status` in tools/list, callable via
tools/call, returning {scan_id: str, phase: red|blue|verify, done: bool}
without starting Docker. RED until the status tool lands in
modules/services/mcp_bridge.py + the /mcp route.
"""

import pytest
from fastapi.testclient import TestClient

import main as app_module
from modules.core.config import PurpleBoxConfig


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("META_MUSE_API_KEY", "test-key")
    monkeypatch.setattr("main.load_config", lambda: PurpleBoxConfig(meta_api_key="test-key"))
    return TestClient(app_module.create_app(), base_url="http://localhost")


def _rpc(method, params=None, rpc_id=1):
    body: dict = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


def test_scan_status_tool_listed(client):
    """tools/list exposes sms_scan_status (pollable status contract)."""
    resp = client.post("/mcp", json=_rpc("tools/list"))
    assert resp.status_code == 200, resp.text
    names = [t["name"] for t in resp.json()["result"]["tools"]]
    assert "sms_scan_status" in names


def test_scan_status_call_returns_phase_envelope(client):
    """tools/call sms_scan_status answers {scan_id, phase, done} with no Docker."""
    resp = client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "sms_scan_status", "arguments": {}}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "error" not in body, body
    structured = body["result"]["structuredContent"]
    assert isinstance(structured["scan_id"], str) and structured["scan_id"]
    assert structured["phase"] in ("red", "blue", "verify")
    assert isinstance(structured["done"], bool)


def test_scan_status_has_input_output_schema(client):
    """sms_scan_status tools/list entry pins inputSchema + outputSchema."""
    resp = client.post("/mcp", json=_rpc("tools/list"))
    assert resp.status_code == 200, resp.text
    tool = next(t for t in resp.json()["result"]["tools"] if t["name"] == "sms_scan_status")
    assert "inputSchema" in tool
    assert "outputSchema" in tool


def test_scan_status_idle_phase_without_scan(client):
    """With no scan running, status reports an idle phase and done=True."""
    resp = client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "sms_scan_status", "arguments": {}}),
    )
    assert resp.status_code == 200, resp.text
    structured = resp.json()["result"]["structuredContent"]
    assert structured["done"] is True
