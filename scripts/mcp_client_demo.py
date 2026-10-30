# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Demo MCP client: submit a snippet to POST /mcp without a browser (Wave 6 HUD).

Stdlib only (``urllib``); localhost + short timeout on every I/O call per
LAW 10I. Used by the HUD demo to drive the same ``submit_code_snippet``
JSON-RPC tool the dashboard calls from ``submitMcp()``, and to print the
``{status, pre_probe_exit, post_probe_exit, receipt_sha}`` result contract.

LAW 4: snippet source is read from an explicit local file argument only;
oversize sources are rejected client-side before any HTTP is attempted, and
the demo never logs payload content (lengths + exit codes only).
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

#: Client-side mirror of the server snippet cap (mcp_bridge.MCP_SNIPPET_MAX_BYTES).
MAX_SOURCE_BYTES = 65_536

#: Demo client talks to loopback only; short timeout bounds every I/O call.
DEFAULT_TIMEOUT = 10.0


def _post_rpc(base_url: str, payload: dict, *, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """POST one JSON-RPC envelope to ``<base_url>/mcp`` and return the envelope.

    Raises ``ConnectionError`` (fail closed) when the server is unreachable
    or refuses the connection, ``TimeoutError`` on a slow read, and
    ``ValueError`` when either side speaks non-JSON.
    """
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(f"demo client connects to localhost only, got {base_url!r}")
    url = base_url.rstrip("/") + "/mcp"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.URLError as exc:
        reason = exc.reason
        detail = str(reason) if reason is not None else str(exc)
        lowered = detail.lower()
        if "refused" in lowered:
            raise ConnectionError(f"connection refused at {url} ({detail})") from exc
        if "timed out" in lowered or isinstance(reason, TimeoutError):
            raise TimeoutError(f"MCP call timed out after {timeout}s at {url}") from exc
        raise ConnectionError(f"MCP endpoint unreachable at {url} ({detail})") from exc
    except TimeoutError as exc:
        raise TimeoutError(f"MCP call timed out after {timeout}s at {url}") from exc
    except OSError as exc:
        raise ConnectionError(f"MCP endpoint failed at {url} ({exc})") from exc
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"MCP endpoint returned non-JSON at {url}") from exc
    if not isinstance(envelope, dict):
        raise ValueError(f"MCP endpoint returned a non-object envelope at {url}")
    return envelope


def run_demo(
    base_url: str,
    filename: str,
    language: str,
    source: str,
) -> dict:
    """Submit one snippet via ``submit_code_snippet`` and return the result contract.

    Returns ``{"status", "pre_probe_exit", "post_probe_exit", "receipt_sha"}``.
    Oversize sources raise ``ValueError`` before any HTTP is attempted.
    Transport failures raise ``ConnectionError``/``TimeoutError``/``ValueError``
    (fail closed); callers map those to a non-zero exit.
    """
    encoded = source.encode("utf-8")
    if len(encoded) > MAX_SOURCE_BYTES:
        raise ValueError(
            f"snippet source is {len(encoded)} bytes, over the {MAX_SOURCE_BYTES}-byte "
            "client cap; shrink it before submitting"
        )
    envelope = _post_rpc(
        base_url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "submit_code_snippet",
                "arguments": {
                    "filename": filename,
                    "language": language,
                    "source": source,
                    "contract": "HUD demo: preserve normal behavior; sanitize untrusted inputs only.",
                },
            },
        },
    )
    if "error" in envelope:
        message = envelope["error"]
        if isinstance(message, dict):
            message = message.get("message", message)
        raise RuntimeError(f"MCP call failed: {message}")
    result = envelope.get("result", {})
    structured = result.get("structuredContent", {}) if isinstance(result, dict) else {}
    receipt = structured.get("receipt") if isinstance(structured, dict) else None
    receipt_sha = None
    if isinstance(receipt, dict):
        receipt_sha = receipt.get("patch_sha256")
    return {
        "status": structured.get("status", "error") if isinstance(structured, dict) else "error",
        "pre_probe_exit": structured.get("pre_probe_exit")
        if isinstance(structured, dict)
        else None,
        "post_probe_exit": structured.get("post_probe_exit")
        if isinstance(structured, dict)
        else None,
        "receipt_sha": receipt_sha,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Submit a snippet file to the Secure Mitigation System MCP endpoint "
        "and print the {status, pre_probe_exit, post_probe_exit, receipt_sha} contract.",
        epilog="MCP endpoint: POST <base-url>/mcp (JSON-RPC tools/call, submit_code_snippet). "
        "Localhost only; oversize sources are rejected before any HTTP.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Dashboard base URL (localhost only; default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--file",
        default="",
        help="Snippet file to submit (default: inline demo snippet)",
    )
    parser.add_argument(
        "--filename",
        default="",
        help="Filename reported to the snippet tool (default: basename of --file)",
    )
    parser.add_argument(
        "--language",
        choices=["javascript", "python", "php"],
        default="python",
        help="Snippet language (default: python)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Seconds per MCP HTTP call (default: {DEFAULT_TIMEOUT:g})",
    )
    return parser


_DEMO_SOURCE = "import subprocess\n\nsubprocess.call('ls ' + user_input, shell=True)\n"


def main(argv: list[str] | None = None) -> int:
    """CLI entry: submit the snippet, print the contract, exit non-zero on failure.

    Raises ``SystemExit`` with the exit code (instead of returning it) so
    embedding harnesses observe the same fail-closed signal as the shell.
    """
    args = _build_parser().parse_args(argv)
    if args.file:
        try:
            source = Path(args.file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"demo failed: cannot read {args.file} ({exc})")
            raise SystemExit(1) from exc
        filename = args.filename or Path(args.file).name
    else:
        source = _DEMO_SOURCE
        filename = args.filename or "demo_snippet.py"
    try:
        result = run_demo(args.base_url, filename, args.language, source)
    except ValueError as exc:
        print(f"demo failed: {exc}")
        raise SystemExit(1) from exc
    except TimeoutError as exc:
        print(f"demo failed: unreachable ({exc})")
        raise SystemExit(1) from exc
    except (ConnectionError, RuntimeError, OSError) as exc:
        print(f"demo failed: {exc}")
        raise SystemExit(1) from exc
    print(
        "status={status} pre_probe_exit={pre} post_probe_exit={post} receipt_sha={sha}".format(
            status=result["status"],
            pre=result["pre_probe_exit"],
            post=result["post_probe_exit"],
            sha=result["receipt_sha"] or "none",
        )
    )
    raise SystemExit(0)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
