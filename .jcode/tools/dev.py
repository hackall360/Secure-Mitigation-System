#!/usr/bin/env python3
# Bootstrap, validate, and run the repository-local PurpleBox development environment.
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Run from any directory. API calls are never part of these commands."""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(*args):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def python(*args):
    if not PYTHON.exists():
        raise RuntimeError("Run the setup command first to create .venv.")
    run(PYTHON, *args)


def setup():
    if not shutil.which("uv"):
        raise RuntimeError(
            "Install uv first: https://docs.astral.sh/uv/getting-started/installation/"
        )
    if not PYTHON.exists():
        run("uv", "venv", "--python", "3.12", ROOT / ".venv")
    run("uv", "pip", "sync", "--python", PYTHON, "--require-hashes", "requirements-dev.lock")
    run("uv", "pip", "check", "--python", PYTHON)
    env = ROOT / ".env"
    if not env.exists():
        # Exclusive creation never overwrites an existing developer configuration.
        with env.open("x", encoding="utf-8") as output:
            output.write((ROOT / "example.env").read_text(encoding="utf-8"))
        if os.name != "nt":
            env.chmod(0o600)
        print("Created ignored .env template. No key configured or exported.")


def check():
    python("-m", "pytest", "-q")
    python("-m", "ruff", "check", ".", ".jcode/tools")
    python("-m", "ruff", "format", "--check", ".", ".jcode/tools")
    python("-m", "compileall", "-q", "-x", r"/(\.git|\.venv)/", ".")
    for script in ("static/app.js", "targets/node_query_sink/app.js"):
        run("node", "--check", script)
    python("test_harness.py")
    python("main.py", "--list-targets")


def smoke():
    if not PYTHON.exists():
        raise RuntimeError("Run setup first.")
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    # This smoke test must never use a developer's inference credentials.
    env = os.environ.copy()
    env.pop("META_MUSE_API_KEY", None)
    process = subprocess.Popen(
        [str(PYTHON), "main.py", "--serve", "--port", str(port)], cwd=ROOT, env=env
    )
    base = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                with opener.open(base + "/api/health", timeout=1) as response:
                    health = json.load(response)
                break
            except (OSError, urllib.error.URLError):
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Development server failed to become ready.") from None
                time.sleep(0.1)
        if health["status"] != "ok" or health["api_key_configured"]:
            raise RuntimeError("Unexpected key-free health response.")
        for path in (
            "/",
            "/api/targets",
            "/static/app.js",
            "/static/app.css",
            "/static/favicon.svg",
        ):
            with opener.open(base + path, timeout=3) as response:
                body = response.read()
                if response.status != 200 or not body:
                    raise RuntimeError(f"Empty or unsuccessful response: {path}")
                if path == "/api/targets":
                    expected = {"node_query_sink", "php_command_sink", "mysql_insecure_conf"}
                    if set(json.loads(body)) != expected:
                        raise RuntimeError("Development server returned unexpected fixtures.")
            print(f"PASS: GET {path}")
        print("PASS: real localhost server, key-free health, dashboard and static assets")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def doctor():
    """Preflight that cannot fail out: reports every prerequisite with fix commands."""
    import shutil as _sh

    checks = []
    checks.append(("python3", bool(_sh.which("python3"))))
    checks.append(("uv", bool(_sh.which("uv"))))
    checks.append(("node", bool(_sh.which("node"))))
    checks.append((".venv", PYTHON.exists()))
    try:
        probe = subprocess.run(
            [str(PYTHON), "-c", "import docker; docker.from_env(timeout=3).ping()"],
            cwd=ROOT,
            capture_output=True,
            timeout=15,
        )
        checks.append(("docker-daemon", probe.returncode == 0))
    except Exception:
        checks.append(("docker-daemon", False))
    try:
        checks.append((".env", (ROOT / ".env").exists()))
    except Exception:
        checks.append((".env", False))
    all_ok = True
    for name, ok in checks:
        print(f"{'OK  ' if ok else 'FAIL'}  {name}", flush=True)
        all_ok = all_ok and ok
    if not all_ok:
        print(
            "Fix: python3 .jcode/tools/dev.py setup && python3 .jcode/tools/dev.py images",
            flush=True,
        )
        raise RuntimeError("Preflight found missing prerequisites (see FAIL lines above).")
    print("Doctor: all prerequisites present. Next: python3 .jcode/tools/dev.py smoke", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "setup",
            "check",
            "images",
            "rebuild-images",
            "docker-status",
            "docker-cleanup",
            "docker-test",
            "doctor",
            "offline-scan",
            "serve",
            "smoke",
            "lock",
        ),
    )
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "setup":
        setup()
    elif args.command == "check":
        check()
    elif args.command == "images":
        python("main.py", "--init-images")
        python("main.py", "--docker-status")
    elif args.command == "doctor":
        doctor()
    elif args.command == "rebuild-images":
        python("main.py", "--rebuild-images")
    elif args.command == "docker-status":
        python("main.py", "--docker-status")
    elif args.command == "docker-cleanup":
        python("main.py", "--cleanup")
    elif args.command == "docker-test":
        python("test_harness.py", "--docker")
    elif args.command == "offline-scan":
        python(".jcode/tools/offline_scan.py")
    elif args.command == "serve":
        python("main.py", "--serve", "--port", str(args.port))
    elif args.command == "smoke":
        smoke()
    else:
        run(
            "uv",
            "pip",
            "compile",
            "--python",
            PYTHON,
            "requirements-dev.txt",
            "--generate-hashes",
            "--output-file",
            "requirements-dev.lock",
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Development command failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
