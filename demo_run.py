#!/usr/bin/env python3
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Zero-argument demo: ingest BrenesRM/insecure-web and run the real purple-team loop.

Runs the same native path as:

    python main.py --ingest-repo <url> --commit-hash <pin> --profile balanced \
        --allow-remote-inference --show-usage --command ... --test-command ...

Nothing is faked: the repo is cloned inside Docker staging at a pinned commit,
red (Muse Spark) looks for a weakness and writes a probe, the probe runs in the
offline sandbox, blue writes a patch, and the probe re-runs on a fresh patched
target. Measured on 2026-11-04: SQL injection in POST /login found, probe
exit 0 -> 1 after the patch, status "verified", 3:35 wall clock, $0.0065.

The sandbox has no network and no Flask, so the "service" is a parse-checked
idle process and the regression check is an ast.parse of app/app.py. Red's
probe exercises the code directly. That is a real limit of this demo target.\nThe --contract text tells red these sandbox facts (an operator input, not a\nbypass): without it Spark sometimes imports flask and the probe is inconclusive.

While a model call is running the core loop is silent, so this wrapper prints a
"[DEMO  ] still working" heartbeat every 5 s with the elapsed time and the last
phase seen. The heartbeat is labelled and is not system output.

Needs: Docker images built (python main.py --init-images) and META_API_KEY in .env.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_URL = "https://github.com/BrenesRM/insecure-web"
COMMIT = "5d1b791bb6c2d1397843f29ee6a0d5c9386dd667"
RUNTIME = [
    "python3",
    "-B",
    "-c",
    'import ast,time;ast.parse(open("app/app.py").read());time.sleep(86400)',
]
REGRESSION = ["python3", "-B", "-c", 'import ast;ast.parse(open("app/app.py").read());print("ok")']
CONTRACT = (
    "Ingest scan of BrenesRM/insecure-web at a pinned commit. Preserve the public "
    "Flask routes. Only sanitize untrusted input. Sandbox facts: offline, Python "
    "3 standard library only, Flask is NOT installed, the working directory is the "
    "repo root. Probes must not import flask: read app/app.py as text, extract the "
    "query-building code, and exercise it with sqlite3 in memory. The probe must "
    "exit 0 when injected input changes the query result, exit 1 when the code "
    "uses parameterized queries (? placeholders) so injection is blocked, and exit "
    "2 only if app/app.py cannot be read. Do not depend on exact line text."
)
HEARTBEAT_S = 5.0


def build_command(root: Path) -> list[str]:
    return [
        sys.executable,
        str(root / "main.py"),
        "--ingest-repo",
        REPO_URL,
        "--commit-hash",
        COMMIT,
        "--profile",
        "balanced",
        "--allow-remote-inference",
        "--show-usage",
        "--command",
        json.dumps(RUNTIME),
        "--test-command",
        json.dumps(REGRESSION),
        "--contract",
        CONTRACT,
    ]


def main() -> int:
    root = Path(__file__).resolve().parent
    start = time.monotonic()
    state = {"last": start, "phase": "starting"}
    done = threading.Event()

    def heartbeat() -> None:
        while not done.wait(1.0):
            now = time.monotonic()
            if now - state["last"] >= HEARTBEAT_S:
                print(
                    f"[DEMO  ] still working ({now - start:5.0f}s) - {state['phase']}",
                    flush=True,
                )
                state["last"] = now

    print(f"[DEMO  ] Target {REPO_URL} @ {COMMIT[:12]}", flush=True)
    proc = subprocess.Popen(
        build_command(root),
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
    )
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
        state["last"] = time.monotonic()
        if "[phase" in line:
            state["phase"] = line.split("[phase", 1)[1].split("]", 1)[0].strip()
    code = proc.wait()
    done.set()
    print(f"[DEMO  ] Finished in {time.monotonic() - start:.0f}s (exit {code})", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
