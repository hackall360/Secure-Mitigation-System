#!/usr/bin/env python3
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Scale run: ingest the large hackall360/AnyCam repo with red early exit on.

Same native path as demo_run.py (python main.py --ingest-repo ...), plus two
environment knobs that matter on big trees:

  PURPLEBOX_RED_EARLY_EXIT_HIGH=1      after 1 high-confidence red candidate,
                                       evidence batches that have not started
                                       are skipped (no model call). The report's
                                       coverage notes say how many were skipped.
  PURPLEBOX_RED_EVIDENCE_PARALLELISM=4 at most 4 red evidence calls at once.

Already-running batches finish. This saves calls and money on big repos, and it
means coverage is partial by design. It is not a security guarantee.

Usage: python scale_run.py [--early-exit N] [--parallelism K] [--commit SHA]
Needs: Docker images built and META_API_KEY in .env. Costs real API money.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/hackall360/AnyCam"
COMMIT = "67155481c6ffeda5a670c72bcb9f3bea984347d1"
# The offline sandbox cannot start AnyCam's camera server, so the "service" is
# a parse-checked idle process and the regression check is ast.parse of
# anycam.py. Red's probes must exercise code directly (stated in --contract).
RUNTIME = [
    "python3",
    "-B",
    "-c",
    'import ast,time;ast.parse(open("anycam.py").read());time.sleep(86400)',
]
REGRESSION = ["python3", "-B", "-c", 'import ast;ast.parse(open("anycam.py").read());print("ok")']
CONTRACT = (
    "Ingest scan of hackall360/AnyCam at a pinned commit. Preserve the public API. "
    "Only sanitize untrusted input. Sandbox facts: offline, Python 3 standard "
    "library only, no camera hardware, the working directory is the repo root. "
    "Probes must read source as text or import pure helpers, and must exit 0 when "
    "the weakness is reachable, 1 when it is blocked, 2 if the check cannot run."
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--early-exit", type=int, default=1, help="0 disables (default 1)")
    parser.add_argument("--parallelism", type=int, default=4)
    parser.add_argument("--commit", default=COMMIT, help="40-hex commit (default: pinned)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    env = os.environ.copy()
    env["PURPLEBOX_RED_EARLY_EXIT_HIGH"] = str(args.early_exit)
    env["PURPLEBOX_RED_EVIDENCE_PARALLELISM"] = str(args.parallelism)
    command = [
        sys.executable,
        str(root / "main.py"),
        "--ingest-repo",
        REPO_URL,
        "--profile",
        "balanced",
        "--allow-remote-inference",
        "--show-usage",
        "--commit-hash",
        args.commit,
        "--command",
        json.dumps(RUNTIME),
        "--test-command",
        json.dumps(REGRESSION),
        "--contract",
        CONTRACT,
    ]
    print(
        f"[SCALE ] {REPO_URL} early_exit={args.early_exit} parallelism={args.parallelism}",
        flush=True,
    )
    return subprocess.call(command, cwd=root, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
