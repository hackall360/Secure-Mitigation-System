# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""MCP bridge: submit_code_snippet tool over the evidence-gated Docker loop.

An external MCP client (Claude Code, Cursor) submits a bounded source
snippet. The bridge validates it (language allowlist, size caps, no path
escapes), runs it through the EXISTING red/blue Docker loop via a fixture
registry extension, and returns the VerdictReceipt + Docker exit codes.

Docker evidence alone decides every verdict. Inconclusive probes fail
closed. No new sandbox primitives: isolation (internal=True, non-root,
read-only roots) is untouched.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from modules.core.registry import TARGETS_REGISTRY, Target

MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_SNIPPET_MAX_BYTES = 65_536
MCP_CONTRACT_MAX_CHARS = 8_192

# Languages the bundled target/verifier images can actually execute.
# Each snippet reuses the runtime + trusted baseline of the bundled fixture
# for its language, so the regression gate checks real behavior (the
# snippet contract narrows it further at the red/blue layer). The snippet
# key stays "mcp_snippet" so receipts identify the external submission;
# execute_mcp_snippet_scan maps the baseline script for that key only.
MCP_ALLOWED_LANGUAGES: tuple[str, ...] = ("javascript", "python", "php")
_MCP_LANGUAGE_BASELINE_KEY: dict[str, str] = {
    "javascript": "node_query_sink",
    "python": "node_query_sink",
    "php": "php_command_sink",
}


def snippet_baseline_key(arguments: McpSnippetArguments) -> str:
    """Bundled fixture key whose runtime + baseline this snippet reuses."""
    return _MCP_LANGUAGE_BASELINE_KEY[arguments.normalized_language()]


_MCP_LANGUAGE_FILENAME: dict[str, str] = {
    "javascript": "app.js",
    "python": "app.py",
    "php": "index.php",
}
_MCP_LANGUAGE_COMMAND: dict[str, tuple[str, ...]] = {
    "javascript": ("node", "/workspace/app.js"),
    "python": ("python3", "/workspace/app.py"),
    "php": ("php", "-S", "0.0.0.0:8080", "-t", "/workspace"),
}
SNIPPET_TOOL_NAME = "submit_code_snippet"


class McpSnippetArguments(BaseModel):
    """Validated tool arguments for submit_code_snippet."""

    model_config = ConfigDict(extra="forbid", strict=True)

    filename: str = Field(min_length=1, max_length=128)
    language: str = Field(min_length=1, max_length=32)
    source: str = Field(min_length=1, max_length=MCP_SNIPPET_MAX_BYTES)
    contract: str = Field(min_length=1, max_length=MCP_CONTRACT_MAX_CHARS)

    def normalized_language(self) -> str:
        return self.language.strip().lower()


def snippet_input_schema() -> dict[str, Any]:
    """JSON Schema for the submit_code_snippet tool input."""
    return {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "maxLength": 128},
            "language": {
                "type": "string",
                "enum": list(MCP_ALLOWED_LANGUAGES),
            },
            "source": {"type": "string", "maxLength": MCP_SNIPPET_MAX_BYTES},
            "contract": {"type": "string", "maxLength": MCP_CONTRACT_MAX_CHARS},
        },
        "required": ["filename", "language", "source", "contract"],
        "additionalProperties": False,
    }


def snippet_output_schema() -> dict[str, Any]:
    """JSON Schema for the submit_code_snippet structured result."""
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "message": {"type": "string"},
            "pre_probe_exit": {"type": ["integer", "null"]},
            "post_probe_exit": {"type": ["integer", "null"]},
            "regression_passed": {"type": "boolean"},
            "cleanup_ok": {"type": "boolean"},
            "receipt": {"type": ["object", "null"]},
        },
        "required": ["status", "pre_probe_exit", "post_probe_exit"],
        "additionalProperties": False,
    }


def snippet_tool_definition() -> dict[str, Any]:
    """MCP tools/list entry for submit_code_snippet."""
    return {
        "name": SNIPPET_TOOL_NAME,
        "title": "Submit code snippet for red/blue Docker verification",
        "description": (
            "Submit a bounded source snippet (javascript, python, or php). "
            "The Secure Mitigation System runs it through the evidence-gated "
            "red/blue Docker loop and returns the VerdictReceipt plus the "
            "pre/post probe Docker exit codes. Docker evidence alone decides "
            "the verdict; inconclusive probes fail closed."
        ),
        "inputSchema": snippet_input_schema(),
        "outputSchema": snippet_output_schema(),
    }


def validate_snippet_arguments(raw: dict[str, Any]) -> McpSnippetArguments:
    """Validate raw tool arguments; raises ValueError with a safe message."""
    try:
        args = McpSnippetArguments.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"Invalid snippet arguments: {type(exc).__name__}.") from exc
    language = args.normalized_language()
    if language not in MCP_ALLOWED_LANGUAGES:
        raise ValueError(
            f"Unsupported language {args.language!r}; "
            f"choose one of {', '.join(MCP_ALLOWED_LANGUAGES)}."
        )
    if "/" in args.filename or "\\" in args.filename or args.filename.startswith("."):
        raise ValueError("Filename must be a bare filename, no paths.")
    if len(args.source.encode("utf-8")) > MCP_SNIPPET_MAX_BYTES:
        raise ValueError("Source exceeds the 64 KiB snippet budget.")
    return args


def snippet_target(args: McpSnippetArguments) -> Target:
    """Build an ephemeral fixture Target for the snippet.

    Reuses the existing Target contract: immutable source bytes, bounded
    size, explicit mutable lines, trusted normal-input contract. The
    workflow treats it exactly like a bundled fixture.
    """
    language = args.normalized_language()
    return Target(
        key="mcp_snippet",
        filename=_MCP_LANGUAGE_FILENAME[language],
        title="MCP snippet submission",
        description="External MCP client snippet; Docker evidence decides.",
        command=_MCP_LANGUAGE_COMMAND[language],
        mutable_prefixes=(),
        contract=args.contract,
    )


def snippet_target_source(args: McpSnippetArguments) -> str:
    """Source bytes the workflow injects for the snippet target."""
    return args.source


def mcp_registry_with_snippet(args: McpSnippetArguments) -> dict:
    """Fixture registry extended with the ephemeral snippet target."""
    registry = dict(TARGETS_REGISTRY)
    registry["mcp_snippet"] = snippet_target(args)
    return registry


def structured_result(result: Any) -> dict[str, Any]:
    """Structured tool output: verdict + exit codes + receipt (or nulls)."""
    receipt = getattr(result, "receipt", None)
    return {
        "status": getattr(result, "status", "error"),
        "message": getattr(result, "message", "Scan did not complete."),
        "pre_probe_exit": getattr(result, "pre_exit_code", None),
        "post_probe_exit": getattr(result, "post_exit_code", None),
        "regression_passed": bool(getattr(result, "regression_passed", False)),
        "cleanup_ok": bool(getattr(result, "cleanup_ok", True)),
        "receipt": receipt.model_dump() if receipt is not None else None,
    }


def jsonrpc_result(rpc_id: Any, result: Any) -> dict[str, Any]:
    """Wrap a JSON-RPC success envelope."""
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def jsonrpc_error(rpc_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    """Wrap a JSON-RPC error envelope (transport-level, never raises)."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": rpc_id, "error": error}


def handle_mcp_request(body: dict[str, Any]) -> dict[str, Any]:
    """Pure JSON-RPC dispatch for initialize/tools-list (no I/O, never raises)."""
    rpc_id = body.get("id")
    if body.get("jsonrpc") != "2.0" or not isinstance(body.get("method"), str):
        return jsonrpc_error(rpc_id, -32600, "Invalid Request.")
    method = body["method"]
    if method == "initialize":
        return jsonrpc_result(
            rpc_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"submit_code_snippet": True}},
                "serverInfo": {
                    "name": "secure-mitigation-system",
                    "version": "0.5.0",
                },
            },
        )
    if method == "notifications/initialized":
        return jsonrpc_result(rpc_id, {})
    if method == "tools/list":
        return jsonrpc_result(rpc_id, {"tools": [snippet_tool_definition()]})
    if method == "ping":
        return jsonrpc_result(rpc_id, {})
    return jsonrpc_error(rpc_id, -32601, f"Method not found: {method}.")


McpToolKind = Literal["submit_code_snippet"]
