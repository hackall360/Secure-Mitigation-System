# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): MCP sms_scan_repo parity — explicit runtime_command.

The CLI now accepts --command with --ingest-repo (Q3) and the WS ingest
frame accepts runtime_command, but the MCP sms_scan_repo tool schema has
only repo_url/commit_hash/contract/timeout_s. For repos whose runtime
cannot auto-detect (a JS repo with an unusual entry, a repo needing an
explicit argv), the MCP path dead-ends with no spelling for the argv —
every other surface has one.

Parity contract: sms_scan_repo accepts optional runtime_command (argv
list of 1..16 non-empty strings, each <= 512 chars); when present it is
forwarded to _ingest_repo_to_project as runtime_command (same
explicit-wins rule). Omitted keeps auto-detect. Both transports (HTTP +
stdio) forward it.
"""

from __future__ import annotations


def test_mcp_repo_schema_has_runtime_command():
    from modules.services.mcp_bridge import sms_scan_repo_tool_definition

    tool = sms_scan_repo_tool_definition()
    props = tool["inputSchema"]["properties"]
    assert "runtime_command" in props, "sms_scan_repo must accept runtime_command"
    assert "array" in props["runtime_command"]["type"]
    assert tool["inputSchema"]["additionalProperties"] is False


def test_mcp_repo_args_validate_runtime_command():
    from modules.services.mcp_bridge import validate_scan_repo_arguments

    args = validate_scan_repo_arguments(
        {"repo_url": "https://github.com/example/demo.git", "runtime_command": ["node", "server.js"]}
    )
    assert list(args.runtime_command) == ["node", "server.js"]
    args2 = validate_scan_repo_arguments({"repo_url": "https://github.com/example/demo.git"})
    assert args2.runtime_command is None
    import pytest

    with pytest.raises(ValueError):
        validate_scan_repo_arguments(
            {"repo_url": "https://github.com/example/demo.git", "runtime_command": []}
        )
    with pytest.raises(ValueError):
        validate_scan_repo_arguments(
            {"repo_url": "https://github.com/example/demo.git", "runtime_command": "node server.js"}
        )


def test_both_transports_forward_runtime_command():
    src = open("main.py").read()
    for marker in ("repo_arguments.repo_url", "_args.repo_url"):
        idx = src.find(marker)
        assert idx != -1
        window = src[idx : idx + 3000]
        assert "runtime_command" in window, (
            f"handler at {marker} must forward runtime_command"
        )
