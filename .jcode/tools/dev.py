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
        # Owner-only mode so the template is never world-readable, even on
        # platforms where chmod is a no-op (Windows ACLs inherit from the dir).
        fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
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


_TRACKED: dict[int, subprocess.Popen] = {}


def read_env_key(name="META_MUSE_API_KEY"):
    """Source one KEY=value line from the owner-only .env (never the shell)."""
    env_file = ROOT / ".env"
    if not env_file.is_file():
        raise RuntimeError(f"{env_file} is missing; run the setup command first.")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            value = line.split("=", 1)[1].strip().strip("'\"")
            if value:
                return value
    raise RuntimeError(f"{name} is empty in {env_file}; set it before serving.")


def keyed_env():
    """Server environment: minimal PATH/HOME plus the key sourced from .env."""
    env = {"PATH": os.environ["PATH"]}
    if "HOME" in os.environ:  # absent in some Windows service contexts
        env["HOME"] = os.environ["HOME"]
    env["META_MUSE_API_KEY"] = read_env_key()
    return env


def probe_health(port):
    """Return parsed /api/health dict, or None when nothing answers."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            return json.load(response)
    except (OSError, urllib.error.URLError, ValueError):
        return None


def summarize_health(health):
    return (
        f"status={health.get('status')} "
        f"api_key_configured={health.get('api_key_configured')} "
        f"inference_ready={health.get('inference_ready')}"
    )


def stop_handle(handle, timeout=10):
    """Terminate ONLY a Popen handle this tool spawned. Never pkill."""
    handle.terminate()
    try:
        handle.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        handle.kill()
        handle.wait()


def wait_for_keyed_health(port, process, timeout=20.0):
    """Wait for /api/health with key+ready true; fail on keyless ok or exit."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    last = None
    while True:
        if process.poll() is not None:
            raise RuntimeError(
                f"Server exited early (code {process.returncode}); is port {port} free? "
                "A live foreign server answers health while a fresh uvicorn "
                "bounces off EADDRINUSE — check `curl` before restarting."
            )
        try:
            with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                last = json.load(response)
            if (
                last.get("status") == "ok"
                and last.get("api_key_configured") is True
                and last.get("inference_ready") is True
            ):
                return last
        except (OSError, urllib.error.URLError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Server on port {port} never reported a keyed health: "
                f"{summarize_health(last) if last else 'no health answer'}. "
                "Suspect a stale keyless process holding the port."
            )
        time.sleep(0.5)


def serve_up(port=8000, restart=True, timeout=20.0):
    """LAW 7: probe, terminate only own handle, restart with .env, verify key.

    Probes /api/health on the port. A live server owns the port: with
    restart=True an own tracked Popen handle for that port is terminated
    (never a broad pkill — the port may belong to an unrelated process)
    and a fresh server is started with META_MUSE_API_KEY sourced from the
    owner-only .env; with restart=False a live server is left alone.
    Declares up only when /api/health reports api_key_configured AND
    inference_ready, which catches the stale-keyless EADDRINUSE failure
    mode (dashboard loads, scans fail). Returns the Popen handle (or
    None when an already-keyed foreign server was left running).
    """
    live = probe_health(port)
    if live is not None:
        print(f"Port {port} is held by a live server: {summarize_health(live)}")
        keyed = bool(live.get("api_key_configured")) and bool(live.get("inference_ready"))
        if not restart:
            if keyed and live.get("status") == "ok":
                print(f"Server on {port} already keyed; leaving it alone (--no-restart).")
                return None
            raise RuntimeError(
                f"Port {port} answers but is not keyed; "
                "re-run without --no-restart to restart it with .env sourced."
            )
        handle = _TRACKED.pop(port, None)
        if handle is None:
            raise RuntimeError(
                f"Port {port} answers but this tool did not spawn it; refusing to "
                "kill a foreign process (LAW 4/LAW 7). Stop it yourself, then re-run."
            )
        print(f"Terminating own server handle (pid={handle.pid}) on port {port}.")
        stop_handle(handle)
    env = keyed_env()
    if not PYTHON.exists():
        raise RuntimeError("Run the setup command first to create .venv.")
    print(f"Starting server on port {port} with .env sourced.")
    process = subprocess.Popen(
        [str(PYTHON), "main.py", "--serve", "--port", str(port)], cwd=ROOT, env=env
    )
    _TRACKED[port] = process
    try:
        health = wait_for_keyed_health(port, process, timeout=timeout)
    except Exception:
        stop_handle(process)
        _TRACKED.pop(port, None)
        raise
    print(
        f"Server up on port {port}: status=ok "
        f"api_key_configured={health['api_key_configured']} "
        f"inference_ready={health['inference_ready']}"
    )
    return process


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
            "serve-up",
            "smoke",
            "lock",
        ),
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="serve-up: leave a live server alone instead of restarting it.",
    )
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
    elif args.command == "serve-up":
        handle = serve_up(args.port, restart=not args.no_restart)
        if handle is not None:
            try:
                handle.wait()
            except KeyboardInterrupt:
                stop_handle(handle)
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
