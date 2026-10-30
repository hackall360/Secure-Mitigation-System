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

import uuid
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
SCAN_STATUS_TOOL_NAME = "sms_scan_status"

#: Scan phases the status tool may report. Live scans advance
#: red -> blue -> verify; the sink reports whichever marker arrived last.
SCAN_PHASES: tuple[str, ...] = ("red", "blue", "verify")

#: Emit teams that mark each scan phase. Live emit callables post team
#: strings like "red", "blue", "green", "system", "research"; the tracking
#: sink maps them onto the pollable red|blue|verify phase contract.
TEAM_TO_SCAN_PHASE: dict[str, str] = {
    "red": "red",
    "research": "red",
    "blue": "blue",
    "green": "blue",
    "verify": "verify",
    "system": "verify",
}

#: Idle envelope when no scan has started in this process yet.
SCAN_STATUS_IDLE_SCAN_ID = "none"

#: Server-side scan registry: scan_id -> {"scan_id", "phase", "done"}.
#: Populated by the live /mcp route when scans start/finish; the status
#: tool only reads it (no Docker, no I/O, never raises).
_SCAN_REGISTRY: dict[str, dict[str, Any]] = {}


def scan_status_register(scan_id: str, phase: str = "red", done: bool = False) -> dict[str, Any]:
    """Record (or refresh) a scan entry; returns the stored envelope."""
    entry = {"scan_id": scan_id, "phase": phase, "done": bool(done)}
    _SCAN_REGISTRY[scan_id] = entry
    return dict(entry)


def scan_status_mark_phase(scan_id: str, phase: str) -> dict[str, Any]:
    """Advance a scan entry to a new phase (still running)."""
    return scan_status_register(scan_id, phase=phase, done=False)


def scan_status_mark_done(scan_id: str, phase: str = "verify") -> dict[str, Any]:
    """Mark a scan entry finished; unknown ids fail closed as a done idle entry."""
    return scan_status_register(scan_id, phase=phase, done=True)


def scan_status_latest() -> dict[str, Any]:
    """Newest registry entry, or the idle envelope when no scan has started."""
    if not _SCAN_REGISTRY:
        return {
            "scan_id": SCAN_STATUS_IDLE_SCAN_ID,
            "phase": "verify",
            "done": True,
        }
    return dict(next(reversed(_SCAN_REGISTRY.values())))


def scan_status_for(scan_id: str | None = None) -> dict[str, Any]:
    """Envelope for one scan id (or the latest); unknown ids fail closed."""
    if not scan_id:
        return scan_status_latest()
    entry = _SCAN_REGISTRY.get(scan_id)
    if entry is None:
        return {"scan_id": scan_id, "phase": "verify", "done": True}
    return dict(entry)


def new_scan_id() -> str:
    """Fresh hex scan id for a live scan about to start."""
    return uuid.uuid4().hex


def scan_status_sink(scan_id: str):
    """Bare tracking emit: marks the registry phase per team, stores nothing.

    Unknown teams leave the phase untouched. Never raises, performs no
    I/O, so status stays pollable mid-scan.
    """

    async def _emit(team: str, message: str) -> None:
        phase = TEAM_TO_SCAN_PHASE.get(str(team).strip().lower())
        if phase in SCAN_PHASES:
            scan_status_mark_phase(scan_id, phase)

    return _emit


def scan_status_phase_sink(scan_id: str, emit):
    """Wrap an existing emit callable with phase tracking (never raises)."""

    async def _emit(team: str, message: str) -> None:
        try:
            await emit(team, message)
        finally:
            phase = TEAM_TO_SCAN_PHASE.get(str(team).strip().lower())
            if phase in SCAN_PHASES:
                scan_status_mark_phase(scan_id, phase)

    return _emit


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


def sms_scan_source_tool_definition() -> dict[str, Any]:
    """MCP tools/list entry for sms_scan_source (fixture scan)."""
    return {
        "name": "sms_scan_source",
        "title": "Scan a bundled source fixture",
        "description": (
            "Run the evidence-gated red/blue cycle (or 3-pass sweep) over a "
            "bundled fixture key. Docker evidence alone decides the verdict."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "maxLength": 64},
                "max_passes": {"type": "integer", "minimum": 1, "maximum": 3},
            },
            "required": ["target"],
            "additionalProperties": False,
        },
        "outputSchema": snippet_output_schema(),
    }


def sms_scan_binary_tool_definition() -> dict[str, Any]:
    """MCP tools/list entry for sms_scan_binary (binary harness sweep)."""
    return {
        "name": "sms_scan_binary",
        "title": "Sweep a compiled binary through the trusted harness",
        "description": (
            "Submit base64 binary bytes (ELF/Mach-O/PE, max 8 MiB) plus a "
            "behavior contract; the air-gapped harness loop probes and "
            "mitigates it. Docker evidence alone decides the verdict."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "maxLength": 128},
                "blob_b64": {"type": "string"},
                "contract": {"type": "string", "maxLength": 8192},
                "max_passes": {"type": "integer", "minimum": 1, "maximum": 3},
            },
            "required": ["filename", "blob_b64", "contract"],
            "additionalProperties": False,
        },
        "outputSchema": snippet_output_schema(),
    }


def sms_query_vault_stats_tool_definition() -> dict[str, Any]:
    """MCP tools/list entry for sms_query_vault_stats (redacted telemetry)."""
    return {
        "name": "sms_query_vault_stats",
        "title": "Query encrypted vault telemetry",
        "description": (
            "Redacted counts per vault namespace (red/blue/green) plus a "
            "token-savings estimate. Never returns payload material."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {"stats": {"type": "object"}},
            "required": ["stats"],
            "additionalProperties": False,
        },
    }


def sms_verify_receipt_tool_definition() -> dict[str, Any]:
    """MCP tools/list entry for sms_verify_receipt (digest validation)."""
    return {
        "name": "sms_verify_receipt",
        "title": "Validate a VerdictReceipt digest",
        "description": (
            "Structural validation of a VerdictReceipt digest (schema, "
            "64-hex sha, sane exit codes). Docker evidence earns receipts; "
            "this tool only checks their shape."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "fixture": {"type": "string"},
                "pre_exit_code": {"type": "integer"},
                "post_exit_code": {"type": "integer"},
                "regression_passed": {"type": "boolean"},
                "differential_passed": {"type": "boolean"},
                "patch_sha256": {"type": "string"},
            },
            "required": ["fixture", "pre_exit_code", "post_exit_code", "patch_sha256"],
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "fixture": {"type": ["string", "null"]},
                "reason": {"type": ["string", "null"]},
            },
            "required": ["valid"],
            "additionalProperties": False,
        },
    }


def sms_scan_status_tool_definition() -> dict[str, Any]:
    """MCP tools/list entry for sms_scan_status (pollable scan status)."""
    return {
        "name": SCAN_STATUS_TOOL_NAME,
        "title": "Poll the running scan's phase",
        "description": (
            "Pollable status for the single-flight live scan: returns "
            "{scan_id, phase, done} with phase one of red|blue|verify. "
            "Starts no Docker; unknown scan ids fail closed as done."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scan_id": {"type": "string", "maxLength": 64},
            },
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "scan_id": {"type": "string"},
                "phase": {"type": "string", "enum": list(SCAN_PHASES)},
                "done": {"type": "boolean"},
            },
            "required": ["scan_id", "phase", "done"],
            "additionalProperties": False,
        },
    }


MCP_TOOLS: list[dict[str, Any]] = [
    snippet_tool_definition(),
    sms_scan_source_tool_definition(),
    sms_scan_binary_tool_definition(),
    sms_query_vault_stats_tool_definition(),
    sms_verify_receipt_tool_definition(),
    sms_scan_status_tool_definition(),
]


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


def _wrap_tool_result(rpc_id: Any, structured: dict[str, Any]) -> dict[str, Any]:
    """Wrap a structured tool result in the MCP content envelope."""
    text = " ".join(f"{key}={value}" for key, value in structured.items() if value is not None)
    return jsonrpc_result(
        rpc_id,
        {
            "content": [{"type": "text", "text": text or "ok"}],
            "structuredContent": structured,
        },
    )


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
                "capabilities": {
                    "tools": {tool["name"]: True for tool in MCP_TOOLS},
                },
                "serverInfo": {
                    "name": "secure-mitigation-system",
                    "version": "0.8.0",
                },
            },
        )
    if method == "notifications/initialized":
        return jsonrpc_result(rpc_id, {})
    if method == "tools/list":
        return jsonrpc_result(rpc_id, {"tools": MCP_TOOLS})
    if method == "ping":
        return jsonrpc_result(rpc_id, {})
    if method == "tools/call":
        params = body.get("params") or {}
        name = params.get("name") if isinstance(params, dict) else None
        arguments = params.get("arguments") if isinstance(params, dict) else None
        arguments = arguments if isinstance(arguments, dict) else {}
        if name == "sms_query_vault_stats":
            try:
                from modules.services.sms_api import query_vault_stats

                return _wrap_tool_result(rpc_id, {"stats": query_vault_stats()})
            except Exception as exc:
                return jsonrpc_error(rpc_id, -32603, f"Vault stats failed ({type(exc).__name__}).")
        if name == "sms_verify_receipt":
            try:
                from modules.services.sms_api import verify_receipt

                return _wrap_tool_result(rpc_id, verify_receipt(arguments))
            except Exception as exc:
                return jsonrpc_error(
                    rpc_id, -32603, f"Receipt check failed ({type(exc).__name__})."
                )
        if name == "sms_scan_status":
            # Pollable status: registry read only. No Docker, no lock, no
            # config: answers even while a live scan holds the scan lock.
            try:
                raw_id = arguments.get("scan_id")
                scan_id = str(raw_id)[:64] if raw_id is not None else None
                return _wrap_tool_result(rpc_id, scan_status_for(scan_id))
            except Exception as exc:
                return jsonrpc_error(rpc_id, -32603, f"Scan status failed ({type(exc).__name__}).")
        if name in ("sms_scan_source", "sms_scan_binary"):
            return jsonrpc_error(
                rpc_id,
                -32001,
                f"Tool {name} runs Docker scans; call it over the live /mcp HTTP "
                "endpoint or --mcp STDIO transport, not the offline dispatcher.",
            )
        return jsonrpc_error(rpc_id, -32602, f"Unknown tool: {name}.")
    return jsonrpc_error(rpc_id, -32601, f"Method not found: {method}.")


McpToolKind = Literal[
    "submit_code_snippet",
    "sms_scan_source",
    "sms_scan_binary",
    "sms_query_vault_stats",
    "sms_verify_receipt",
    "sms_scan_status",
]
