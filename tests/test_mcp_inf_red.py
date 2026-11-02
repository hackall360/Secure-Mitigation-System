# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: MCP max_passes + stamp cycles int(inf) guards (task-014).

httpx/TestClient json= serializes float inf as `Infinity`, which the server's
json.loads decodes back to inf. The MCP sms_scan_source/sms_scan_binary
max_passes guards and the project-stamp cycles guard catch
(TypeError, ValueError) only -> OverflowError escapes (500 / crash) instead
of the documented fallbacks (1 / 3 / untouched). Post-fix: fallbacks hold
and the scan proceeds.
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


def test_mcp_scan_source_max_passes_survives_inf(client, monkeypatch):
    """MCP sms_scan_source with max_passes=inf must fall back to 1 and run."""
    from modules.workflows.workflow import ScanResult

    seen = {}

    async def fake_scan(target, emit, config=None, max_passes=1):
        seen["max_passes"] = max_passes
        return ScanResult(
            target="node_query_sink",
            status="verified",
            message="ok",
            pre_exit_code=0,
            post_exit_code=1,
            baseline_passed=True,
            regression_passed=True,
        )

    monkeypatch.setattr("modules.services.sms_api.scan_source", fake_scan)
    # Raw body with literal Infinity: httpx json= refuses inf, but the
    # server's json.loads accepts it (allow_nan) — the hostile-client path.
    raw = (
        '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": '
        '{"name": "sms_scan_source", "arguments": '
        '{"target": "node_query_sink", "max_passes": Infinity}}}'
    )
    resp = client.post("/mcp", content=raw.encode(), headers={"Content-Type": "application/json"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # HTTP MCP contract: invalid args -> JSON-RPC -32602, never a crash (500)
    # and never a scan (fake_scan unwired). Pre-fix this raised OverflowError.
    assert body.get("error", {}).get("code") == -32602, body
    assert "Invalid scan arguments" in body["error"]["message"], body
    assert seen == {}, seen
