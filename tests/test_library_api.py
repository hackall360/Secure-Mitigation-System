# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first library API + extended MCP tool tests (Subsystem E, Y5).

RED per LAW 9: written BEFORE modules/services/sms_api.py and the three
new MCP tools land. Pins: programmatic scan_source/scan_binary entry
points, vault stats + receipt verification helpers, and MCP tool
definitions/dispatch for sms_scan_source, sms_scan_binary,
sms_query_vault_stats, sms_verify_receipt on both transports.
"""


def test_library_api_importable():
    import modules.services.sms_api as api

    for name in (
        "scan_source",
        "scan_binary",
        "query_vault_stats",
        "verify_receipt",
        "ApiScanRequest",
    ):
        assert hasattr(api, name), name


def test_verify_receipt_accepts_real_receipt():
    from modules.services.sms_api import verify_receipt
    from modules.workflows.workflow import build_verdict_receipt

    receipt = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="patched content",
    )
    verdict = verify_receipt(receipt.model_dump())
    assert verdict["valid"] is True
    assert verdict["fixture"] == "node_query_sink"


def test_verify_receipt_rejects_tampered_digest():
    from modules.services.sms_api import verify_receipt
    from modules.workflows.workflow import build_verdict_receipt

    receipt = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="patched content",
    )
    tampered = receipt.model_dump()
    tampered["patch_sha256"] = "not-a-digest"
    verdict = verify_receipt(tampered)
    assert verdict["valid"] is False


def test_verify_receipt_rejects_malformed():
    from modules.services.sms_api import verify_receipt

    verdict = verify_receipt({"not": "a receipt"})
    assert verdict["valid"] is False


def test_query_vault_stats_redacted(tmp_path, monkeypatch):
    import json

    from modules.services.sms_api import query_vault_stats

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    stats = query_vault_stats()
    assert json.dumps(stats)
    assert "red" in stats and "blue" in stats and "green" in stats
    assert "tokens_saved_estimate" in stats


def test_mcp_tool_definitions_cover_four_tools():
    from modules.services.mcp_bridge import MCP_TOOLS

    names = [tool["name"] for tool in MCP_TOOLS]
    for expected in (
        "submit_code_snippet",
        "sms_scan_source",
        "sms_scan_binary",
        "sms_query_vault_stats",
        "sms_verify_receipt",
    ):
        assert expected in names, expected
    for tool in MCP_TOOLS:
        assert "inputSchema" in tool and "outputSchema" in tool


def test_mcp_dispatch_lists_all_tools():
    from modules.services.mcp_bridge import handle_mcp_request

    response = handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [tool["name"] for tool in response["result"]["tools"]]
    assert "sms_scan_source" in names
    assert "sms_scan_binary" in names
    assert "sms_query_vault_stats" in names
    assert "sms_verify_receipt" in names


def test_mcp_query_vault_stats_call(tmp_path, monkeypatch):
    from modules.services.mcp_bridge import handle_mcp_request

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    response = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "sms_query_vault_stats", "arguments": {}},
        }
    )
    assert "result" in response
    structured = response["result"]["structuredContent"]
    assert "red" in structured["stats"]


def test_mcp_verify_receipt_call():
    from modules.services.mcp_bridge import handle_mcp_request
    from modules.workflows.workflow import build_verdict_receipt

    receipt = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="patched content",
    )
    response = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "sms_verify_receipt", "arguments": receipt.model_dump()},
        }
    )
    assert response["result"]["structuredContent"]["valid"] is True
