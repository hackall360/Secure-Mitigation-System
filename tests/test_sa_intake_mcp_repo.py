# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: MCP sms_scan_repo repo-intake scan tool (D6).

The sms_scan_repo tool scans a remote git repo (repo_url + optional
commit_hash + contract) through the evidence-gated project loop. The tool
call is the explicit remote-inference grant: the built spec carries
allow_remote_inference=True. FAKE intake: tests monkeypatch
main._ingest_repo_to_project; never real Docker.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import main as app_module
from modules.core.config import PurpleBoxConfig

COMMIT = "a" * 40
URL = "https://github.com/example/demo.git"


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


def _fake_result(**over):
    from types import SimpleNamespace

    payload = {
        "status": "verified",
        "message": "ok",
        "pre_exit_code": 0,
        "post_exit_code": 1,
        "regression_passed": True,
        "cleanup_ok": True,
        "receipt": None,
    }
    payload.update(over)
    return SimpleNamespace(**payload)


def _fake_project():
    from types import SimpleNamespace

    return SimpleNamespace(allow_remote_inference=True)


def _patch_intake(monkeypatch, seen):
    async def fake_ingest(repo_url, commit_hash, emit, settings=None, **kwargs):
        seen.append((repo_url, commit_hash))
        return _fake_project()

    monkeypatch.setattr(app_module, "_ingest_repo_to_project", fake_ingest)


def _patch_workflow(monkeypatch, seen):
    from types import SimpleNamespace

    async def fake_workflow(spec, emit, **kwargs):
        seen.append(spec)
        receipt = SimpleNamespace(
            model_dump=lambda: {"patch_sha256": "abc123"},
        )
        return _fake_result(receipt=receipt)

    monkeypatch.setattr(app_module, "execute_project_workflow", fake_workflow)


# ---------- schema ----------


def test_scan_repo_schema_accepts_repo_only():
    from library.services.mcp_bridge import validate_scan_repo_arguments

    args = validate_scan_repo_arguments({"repo_url": URL})
    assert args.repo_url == URL
    assert args.commit_hash is None
    assert args.contract == ""


def test_scan_repo_schema_accepts_full_args():
    from library.services.mcp_bridge import validate_scan_repo_arguments

    args = validate_scan_repo_arguments(
        {"repo_url": URL, "commit_hash": COMMIT, "contract": "Harden inputs."}
    )
    assert args.commit_hash == COMMIT


def test_scan_repo_schema_rejects_bad_commit():
    from library.services.mcp_bridge import validate_scan_repo_arguments

    with pytest.raises(ValueError):
        validate_scan_repo_arguments({"repo_url": URL, "commit_hash": "short"})


def test_scan_repo_schema_rejects_userinfo_url():
    from library.services.mcp_bridge import validate_scan_repo_arguments

    with pytest.raises(ValueError):
        validate_scan_repo_arguments({"repo_url": "https://user:pass@github.com/a/b.git"})


def test_scan_repo_schema_rejects_extra_fields():
    from library.services.mcp_bridge import validate_scan_repo_arguments

    with pytest.raises(ValueError):
        validate_scan_repo_arguments({"repo_url": URL, "host_path": "/etc/passwd"})


def test_tools_list_exposes_scan_repo(client):
    resp = client.post("/mcp", json=_rpc("tools/list"))
    assert resp.status_code == 200, resp.text
    tools = resp.json()["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "sms_scan_repo" in names
    tool = next(t for t in tools if t["name"] == "sms_scan_repo")
    assert "inputSchema" in tool and "outputSchema" in tool
    assert len(tools) == 11


# ---------- HTTP live ----------


def test_mcp_http_scan_repo_live(client, monkeypatch):
    seen_ingest: list = []
    seen_workflow: list = []
    _patch_intake(monkeypatch, seen_ingest)
    _patch_workflow(monkeypatch, seen_workflow)
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "sms_scan_repo",
                "arguments": {"repo_url": URL, "commit_hash": COMMIT},
            },
        ),
    )
    assert resp.status_code == 200, resp.text
    structured = resp.json()["result"]["structuredContent"]
    assert structured["status"] == "verified"
    assert structured["pre_probe_exit"] == 0
    assert structured["post_probe_exit"] == 1
    assert seen_ingest == [(URL, COMMIT)]
    assert seen_workflow and seen_workflow[0].allow_remote_inference is True


def test_mcp_http_scan_repo_repo_only(client, monkeypatch):
    seen_ingest: list = []
    seen_workflow: list = []
    _patch_intake(monkeypatch, seen_ingest)
    _patch_workflow(monkeypatch, seen_workflow)
    resp = client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "sms_scan_repo", "arguments": {"repo_url": URL}}),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["result"]["structuredContent"]["status"] == "verified"
    assert seen_ingest == [(URL, None)]


def test_mcp_http_scan_repo_rejects_bad_commit(client):
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {"name": "sms_scan_repo", "arguments": {"repo_url": URL, "commit_hash": "nope"}},
        ),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["error"]["code"] == -32602


def test_mcp_http_scan_repo_rejects_extra_args(client):
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "sms_scan_repo",
                "arguments": {"repo_url": URL, "host_path": "/etc/passwd"},
            },
        ),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["error"]["code"] == -32602


def test_mcp_http_scan_repo_keyless_guidance(client, monkeypatch):
    """Key/config failure: established -32603 envelope with guidance."""
    seen_ingest: list = []

    async def fake_ingest(repo_url, commit_hash, emit, settings=None, **kwargs):
        seen_ingest.append(repo_url)
        from modules.core.config import ConfigurationError

        raise ConfigurationError(
            "META_MUSE_API_KEY is required for scans. Secure Mitigation System uses Meta Muse only."
        )

    monkeypatch.setattr(app_module, "_ingest_repo_to_project", fake_ingest)
    resp = client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "sms_scan_repo", "arguments": {"repo_url": URL}}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["error"]["code"] == -32603
    assert "META_MUSE_API_KEY" in body["error"]["message"]


def test_mcp_http_scan_repo_busy(monkeypatch):
    """Busy gate: second caller gets -32001 with the lock held across validation."""
    import asyncio

    monkeypatch.setenv("META_MUSE_API_KEY", "test-key")
    monkeypatch.setattr("main.load_config", lambda: PurpleBoxConfig(meta_api_key="test-key"))
    app = app_module.create_app()
    held = asyncio.Lock()
    asyncio.run(held.acquire())
    monkeypatch.setattr(app.state, "scan_lock", held)
    seen_ingest: list = []
    _patch_intake(monkeypatch, seen_ingest)
    seen_workflow: list = []
    _patch_workflow(monkeypatch, seen_workflow)
    with TestClient(app, base_url="http://localhost") as busy_client:
        resp = busy_client.post(
            "/mcp",
            json=_rpc(
                "tools/call",
                {"name": "sms_scan_repo", "arguments": {"repo_url": URL}},
            ),
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["error"]["code"] == -32001
    assert seen_ingest == [] and seen_workflow == []


# ---------- stdio ----------


def _stdio_call(monkeypatch, request):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request) + "\n"))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    app_module._mcp_stdio_loop()
    return json.loads(out.getvalue().strip().splitlines()[-1])


def test_mcp_stdio_scan_repo_live(monkeypatch):
    monkeypatch.setenv("META_MUSE_API_KEY", "test-key")
    seen_ingest: list = []
    seen_workflow: list = []
    _patch_intake(monkeypatch, seen_ingest)
    _patch_workflow(monkeypatch, seen_workflow)
    reply = _stdio_call(
        monkeypatch,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "sms_scan_repo", "arguments": {"repo_url": URL}},
        },
    )
    structured = reply["result"]["structuredContent"]
    assert structured["status"] == "verified"
    assert seen_workflow and seen_workflow[0].allow_remote_inference is True


def test_mcp_stdio_scan_repo_keyless_guidance(monkeypatch):
    """Keyless/config failure: -32603 envelope carrying the guidance."""
    from modules.core.config import ConfigurationError

    async def fake_ingest(repo_url, commit_hash, emit, settings=None, **kwargs):
        raise ConfigurationError(
            "META_MUSE_API_KEY is required for scans. Secure Mitigation System uses Meta Muse only."
        )

    monkeypatch.setattr(app_module, "_ingest_repo_to_project", fake_ingest)
    reply = _stdio_call(
        monkeypatch,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "sms_scan_repo", "arguments": {"repo_url": URL}},
        },
    )
    assert reply["error"]["code"] == -32603, reply
    assert "META_MUSE_API_KEY" in reply["error"]["message"]


# ---------- offline dispatcher ----------


def test_offline_dispatcher_refuses_scan_repo():
    from library.services.mcp_bridge import handle_mcp_request

    body = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "sms_scan_repo", "arguments": {"repo_url": URL}},
    }
    resp = handle_mcp_request(body)
    assert resp["error"]["code"] == -32001, resp
