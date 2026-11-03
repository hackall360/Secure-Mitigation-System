# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED-FIRST parity W6: MCP vault browse + replay tools (tmp_path only, LAW 4)."""

TOOL_NAMESPACES = "sms_list_vault_namespaces"
TOOL_REPLAY = "sms_replay_vault_record"


def _rpc(name, arguments, rpc_id=1):
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def _commit(vault_dir, namespace: str = "red", marker: str = "SECRET-MARKER-XYZ") -> str:
    from modules.intel import sms_vault as vault

    return vault.commit_verified(
        namespace=vault.VaultNamespace(namespace),
        source="query($x) { user(id: $x) { name } }",
        payload={"kind": "probe-shape", "secret_blob": marker, "api_key": "KEY-MATERIAL-ABC"},
        vault_dir=vault_dir,
    )


def test_tools_list_contains_vault_tools():
    from library.services.mcp_bridge import handle_mcp_request

    body = handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in body["result"]["tools"]}
    assert TOOL_NAMESPACES in names
    assert TOOL_REPLAY in names


def test_offline_dispatch_namespaces_seeded_tmp_vault(tmp_path, monkeypatch):
    from library.services.mcp_bridge import handle_mcp_request

    vault_dir = tmp_path / "vault"
    _commit(vault_dir)
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(vault_dir))
    resp = handle_mcp_request(_rpc(TOOL_NAMESPACES, {}))
    assert "result" in resp, resp
    namespaces = resp["result"]["structuredContent"]["namespaces"]
    assert {"namespace": "red", "record_count": 1} in namespaces


def test_offline_dispatch_replay_roundtrip_redacted(tmp_path, monkeypatch):
    from library.services.mcp_bridge import handle_mcp_request

    vault_dir = tmp_path / "vault"
    record_id = _commit(vault_dir)
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(vault_dir))
    resp = handle_mcp_request(_rpc(TOOL_REPLAY, {"namespace": "red", "record_id": record_id}))
    assert "result" in resp, resp
    summary = resp["result"]["structuredContent"]
    assert summary["id"] == record_id
    assert set(summary) == {"id", "fingerprint_prefix", "status", "created"}
    leaked = str(resp)
    for forbidden in (
        "SECRET-MARKER-XYZ",
        "KEY-MATERIAL-ABC",
        "secret_blob",
        "api_key",
        "payload",
        "ciphertext",
        "nonce",
    ):
        assert forbidden not in leaked, forbidden


def test_offline_dispatch_replay_bad_id_fail_closed(tmp_path, monkeypatch):
    from library.services.mcp_bridge import handle_mcp_request

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    resp = handle_mcp_request(_rpc(TOOL_REPLAY, {"namespace": "red", "record_id": "0" * 32}))
    assert "error" in resp, resp
    assert resp["error"]["code"] == -32603


def test_snippet_offline_returns_needs_live_transport():
    """Surface MCP observation: snippet had no offline branch (-32602)."""
    from library.services import mcp_bridge as B

    body = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "submit_code_snippet", "arguments": {}},
    }
    resp = B.handle_mcp_request(body)
    assert resp["error"]["code"] == -32001, resp
