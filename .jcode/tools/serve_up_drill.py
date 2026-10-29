#!/usr/bin/env python3
# Live LAW 7 drill: start a keyless server, run serve_up, prove keyed restart.
"""Spawns keyless main.py on --port, registers the handle as own-tracked,
then calls dev.serve_up and asserts /api/health flips to keyed. Cleans up."""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".jcode/tools"))
import dev  # noqa: E402


def health(port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=3) as r:
        return json.load(r)


def wait_until(port, predicate, timeout, label):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = health(port)
            if predicate(last):
                return last
        except OSError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"drill timeout waiting for {label}: {last}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18011)
    args = parser.parse_args()

    key = dev.read_env_key()
    assert key and key != "", "drill needs a non-empty META_MUSE_API_KEY in .env"

    stale_env = {"PATH": __import__("os").environ["PATH"]}
    stale = subprocess.Popen(
        [str(dev.PYTHON), "main.py", "--serve", "--port", str(args.port)],
        cwd=dev.ROOT,
        env=stale_env,
    )
    dev._TRACKED[args.port] = stale  # our own spawn, so serve_up may stop it
    try:
        before = wait_until(
            args.port,
            lambda h: h.get("status") == "ok",
            25,
            "keyless server",
        )
        print(f"BEFORE: {dev.summarize_health(before)} pid={stale.pid}")
        assert before["api_key_configured"] is False, before
        assert stale.poll() is None

        handle = dev.serve_up(port=args.port, restart=True, timeout=30)
        after = health(args.port)
        print(f"AFTER: {dev.summarize_health(after)} pid={handle.pid}")
        assert after["status"] == "ok", after
        assert after["api_key_configured"] is True, after
        assert after["inference_ready"] is True, after
        assert stale.poll() is not None, "stale own handle must be terminated"
        assert handle is not None and handle.poll() is None
        print("DRILL PASS: stale keyless -> own-handle restart -> keyed ready")
    finally:
        for proc in (dev._TRACKED.pop(args.port, None), stale):
            if proc is not None and proc.poll() is None:
                dev.stop_handle(proc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
