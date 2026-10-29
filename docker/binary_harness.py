# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Trusted binary-execution harness. Runs ONLY inside the air-gapped sandbox.

The harness serves HTTP on 127.0.0.1:8080 *inside* its container (the
isolated network exposes it as target-service:8080 to verifier probes).
Each request executes the staged binary as a subprocess with bounded argv
and stdin, a 5-second timeout, and no network. A mitigation rule file
(written by the blue pass as plain `reject:` prefix lines) pre-rejects
inputs before the binary runs; re-running the probe through the mitigated
harness is the binary analog of patch verification.

Untrusted bytes (the binary, probe inputs) never run on the host.
"""

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

WORKSPACE = Path("/workspace")
BINARY_PATH = WORKSPACE / "target.bin"
MITIGATION_PATH = WORKSPACE / "mitigation.txt"
MAX_OUTPUT_BYTES = 8 * 1024
EXEC_TIMEOUT_SECONDS = 5
MAX_ARG_COUNT = 16
MAX_ARG_BYTES = 4 * 1024


def load_mitigation_rules() -> list[str]:
    """Plain `reject:<prefix>` lines; anything else is ignored (fail-closed)."""
    try:
        text = MITIGATION_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rules = []
    for line in text.splitlines():
        if line.startswith("reject:"):
            rules.append(line[len("reject:") :])
    return rules


def mitigated(reason: str) -> tuple[int, dict]:
    """A mitigation rejection: deterministic, auditable, no binary contact."""
    return 400, {"status": "mitigated", "reason": reason}


class Handler(BaseHTTPRequestHandler):
    server_version = "BinaryHarness/1.0"

    def log_message(self, *args):  # quiet: verifier evidence comes from bodies
        return

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler naming)
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        argv = query.get("argv", [""])[0]
        stdin_text = query.get("stdin", [""])[0]
        if len(argv) > MAX_ARG_BYTES * (MAX_ARG_COUNT + 1) or len(stdin_text) > 65536:
            self._send(400, {"status": "rejected", "reason": "input budget exceeded"})
            return
        args = argv.split("\x00")[:MAX_ARG_COUNT]
        for rule in load_mitigation_rules():
            if rule and (argv.startswith(rule) or stdin_text.startswith(rule)):
                code, payload = mitigated(f"mitigation rule matched: {rule[:64]}")
                self._send(code, payload)
                return
        try:
            completed = subprocess.run(
                [str(BINARY_PATH), *args],
                input=stdin_text.encode("utf-8", errors="replace"),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=EXEC_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            self._send(200, {"status": "timeout", "exit_code": None, "output": ""})
            return
        except OSError as exc:
            self._send(
                200, {"status": "exec_error", "exit_code": None, "output": type(exc).__name__}
            )
            return
        output = completed.stdout[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        self._send(
            200,
            {"status": "ok", "exit_code": completed.returncode, "output": output},
        )


if __name__ == "__main__":
    if not BINARY_PATH.exists():
        sys.exit("harness: no staged binary at /workspace/target.bin")
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()
