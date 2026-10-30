# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: live /mcp must serve sms_verify_receipt (W7 demo E2E gap).

Live proof 2026-10-30 (keyless server, port 18080): tools/list advertises
6 tools incl. sms_verify_receipt, but POST /mcp tools/call
sms_verify_receipt answered -32602 "Unknown tool". The offline dispatcher
(mcp_bridge.handle_mcp_request) serves it; the live mcp_endpoint intercepts
tools/call first and has no verify branch, so the request never reaches the
shared dispatcher. RED until the live route answers verify offline.
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


def _receipt_args(**over):
    args = {
        "fixture": "node_query_sink",
        "pre_exit_code": 0,
        "post_exit_code": 1,
        "regression_passed": True,
        "differential_passed": True,
        "patch_sha256": "ab" * 32,
    }
    args.update(over)
    return args


def test_live_verify_receipt_valid_shape(client):
    resp = client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "sms_verify_receipt", "arguments": _receipt_args()}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "result" in body, body
    assert body["result"]["structuredContent"]["valid"] is True


def test_live_verify_receipt_rejects_tampered_digest(client):
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {"name": "sms_verify_receipt", "arguments": _receipt_args(patch_sha256="zz")},
        ),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "result" in body, body
    assert body["result"]["structuredContent"]["valid"] is False
