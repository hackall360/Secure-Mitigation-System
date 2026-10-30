# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first MCP bridge tests (Milestone 2).

POST /mcp speaks JSON-RPC over Streamable HTTP: initialize, tools/list,
tools/call submit_code_snippet. The tool routes through the existing
evidence-gated red/blue Docker loop and returns the VerdictReceipt +
Docker exit codes. Docker evidence alone decides every verdict.
RED until modules/services/mcp_bridge.py + the /mcp route land.
"""

import json

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


def test_mcp_initialize(client):
    resp = client.post("/mcp", json=_rpc("initialize"))
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert "submit_code_snippet" in json.dumps(result["capabilities"])


def test_mcp_tools_list_exposes_snippet_tool(client):
    resp = client.post("/mcp", json=_rpc("tools/list"))
    assert resp.status_code == 200, resp.text
    tools = resp.json()["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "submit_code_snippet" in names
    for expected in (
        "sms_scan_source",
        "sms_scan_binary",
        "sms_query_vault_stats",
        "sms_verify_receipt",
    ):
        assert expected in names, expected
    tool = next(t for t in tools if t["name"] == "submit_code_snippet")
    assert "inputSchema" in tool
    assert "outputSchema" in tool


def test_mcp_tools_call_returns_receipt_and_exits(client, monkeypatch):
    from modules.workflows.workflow import ScanResult, VerdictReceipt

    async def fake_run(target_key, emit, config=None, **kwargs):
        receipt = VerdictReceipt(
            fixture="mcp_snippet",
            pre_exit_code=0,
            post_exit_code=1,
            regression_passed=True,
            differential_passed=True,
            patch_sha256="abc123",
        )
        return ScanResult(
            target="mcp_snippet",
            status="verified",
            message="ok",
            pre_exit_code=0,
            post_exit_code=1,
            baseline_passed=True,
            regression_passed=True,
            receipt=receipt,
        )

    monkeypatch.setattr("main.execute_mcp_snippet_scan", fake_run)
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "submit_code_snippet",
                "arguments": {
                    "filename": "app.js",
                    "language": "javascript",
                    "source": "const x = 1;",
                    "contract": "Keep behavior; validate inputs.",
                },
            },
        ),
    )
    assert resp.status_code == 200, resp.text
    structured = resp.json()["result"]["structuredContent"]
    assert structured["pre_probe_exit"] == 0
    assert structured["post_probe_exit"] == 1
    assert structured["status"] == "verified"
    assert structured["receipt"]["patch_sha256"] == "abc123"


def test_mcp_tools_call_rejects_unknown_tool(client):
    resp = client.post("/mcp", json=_rpc("tools/call", {"name": "nope", "arguments": {}}))
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_mcp_tools_call_rejects_oversize_source(client):
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "submit_code_snippet",
                "arguments": {
                    "filename": "app.js",
                    "language": "javascript",
                    "source": "x" * (65_537),
                    "contract": "c",
                },
            },
        ),
    )
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_mcp_tools_call_rejects_disallowed_language(client):
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "submit_code_snippet",
                "arguments": {
                    "filename": "run.exe",
                    "language": "x86asm",
                    "source": "MZ...",
                    "contract": "c",
                },
            },
        ),
    )
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_mcp_cli_snippet_flag_reaches_runner(monkeypatch, tmp_path):
    """M2 CLI parity: --mcp-snippet + --snippet-language reach mcp_snippet_runner."""
    import main as _main

    seen = {}

    async def fake_runner(path, **kwargs):
        seen["path"] = path
        seen.update(kwargs)
        return 0

    snippet = tmp_path / "app.js"
    snippet.write_text("const x = 1;")
    monkeypatch.setattr(_main, "mcp_snippet_runner", fake_runner)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--mcp-snippet",
            str(snippet),
            "--snippet-language",
            "javascript",
            "--contract",
            "Keep behavior.",
        ],
    )
    assert _main.main() == 0
    assert seen["path"] == snippet
    assert seen["language"] == "javascript"
    assert seen["contract"] == "Keep behavior."


def test_mcp_cli_snippet_rejects_unknown_suffix(monkeypatch, tmp_path, capsys):
    """M2 CLI parity: unknown suffix without --snippet-language exits 1, no scan."""
    import main as _main

    snippet = tmp_path / "blob.xyz"
    snippet.write_text("data")
    monkeypatch.setattr("sys.argv", ["main.py", "--mcp-snippet", str(snippet)])
    assert _main.main() == 1
    assert "snippet-language" in capsys.readouterr().err.lower()


def test_mcp_dashboard_controls_exist():
    """M2 dashboard parity: MCP mode button + snippet form controls render."""
    from html.parser import HTMLParser
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[1]

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = set()

        def handle_starttag(self, tag, attrs):
            ids = dict(attrs).get("id")
            if ids:
                self.ids.add(ids)

    parser = Elements()
    parser.feed((root / "static/index.html").read_text())
    for control in (
        "mode-mcp",
        "mcp-form",
        "mcp-language",
        "mcp-filename",
        "mcp-source",
        "mcp-contract",
        "mcp-errors",
        "mcp-result",
    ):
        assert control in parser.ids, control


def test_mcp_snippet_baseline_mapping():
    """M2: snippets reuse their language fixture's trusted baseline."""
    from modules.services.mcp_bridge import (
        snippet_baseline_key,
        validate_snippet_arguments,
    )

    js = validate_snippet_arguments(
        {"filename": "a.js", "language": "javascript", "source": "x", "contract": "c"}
    )
    assert snippet_baseline_key(js) == "node_query_sink"
    php = validate_snippet_arguments(
        {"filename": "i.php", "language": "php", "source": "x", "contract": "c"}
    )
    assert snippet_baseline_key(php) == "php_command_sink"


def test_mcp_http_scan_source_live(client, monkeypatch):
    """W2: POST /mcp sms_scan_source runs the live loop via sms_api."""
    from modules.workflows.workflow import ScanResult

    async def fake_scan(target, emit, config=None, max_passes=1):
        assert target == "node_query_sink"
        assert max_passes == 1
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
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {"name": "sms_scan_source", "arguments": {"target": "node_query_sink"}},
        ),
    )
    assert resp.status_code == 200, resp.text
    structured = resp.json()["result"]["structuredContent"]
    assert structured["status"] == "verified"
    assert structured["pre_probe_exit"] == 0
    assert structured["post_probe_exit"] == 1


def test_mcp_http_scan_source_rejects_unknown_target(client):
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {"name": "sms_scan_source", "arguments": {"target": "nope"}},
        ),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "error" in body and body["error"]["code"] == -32602


def test_mcp_http_scan_binary_rejects_bad_blob(client):
    resp = client.post(
        "/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "sms_scan_binary",
                "arguments": {"filename": "x", "blob_b64": "!!!", "contract": "c"},
            },
        ),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["error"]["code"] == -32602


def test_mcp_http_vault_stats_live(client, tmp_path, monkeypatch):
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    resp = client.post(
        "/mcp", json=_rpc("tools/call", {"name": "sms_query_vault_stats", "arguments": {}})
    )
    assert resp.status_code == 200, resp.text
    stats = resp.json()["result"]["structuredContent"]["stats"]
    assert "red" in stats and "tokens_saved_estimate" in stats
