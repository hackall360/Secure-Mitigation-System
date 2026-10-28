#!/usr/bin/env python3
# Run one real scan by clicking the dashboard in headless Chrome; prints the result card as JSON and saves a screenshot.
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Usage: ui_scan.py TARGET [--profile economy|balanced|quality] [--port 8797] [--shot PATH] [--offline]

Starts the real server (only META_MUSE_API_KEY from .env, all other settings default),
opens Chrome via the DevTools protocol, selects TARGET, clicks Run verification, waits
for the result card and prints it. --offline swaps only MetaMuseClient for the known
fixture outputs (no API cost). Real mode spends Meta API credit (about $0.05-0.15).
"""

import argparse
import asyncio
import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "bin" / "python"

# Built with String.fromCharCode(10) on purpose: a "\n" here would be turned into a real
# newline by Python and break the JavaScript regular expression (a real bug hit once).
READOUT = """JSON.stringify({
  status: document.getElementById('status').textContent,
  stages: [...document.querySelectorAll('#pipeline li')].map((l) => l.dataset.state || '-'),
  facts: [...document.querySelectorAll('.facts dd')].map((d) => d.textContent),
  diff: document.getElementById('diff-stats').textContent,
  elapsed: document.getElementById('elapsed').textContent,
  profile: (document.querySelector('.profile[aria-checked="true"]') || {}).dataset?.key || null,
  cost: document.getElementById('usage-cost').textContent,
  tokens: document.getElementById('usage-tokens').textContent,
  calls: [...document.querySelectorAll('#usage-calls li')].map(
    (l) => l.innerText.split(String.fromCharCode(10)).join(' | ')),
})"""

OFFLINE_SERVER = """
import sys
sys.path.insert(0, {root!r}); sys.path.insert(0, {tools!r})
import uvicorn, main, workflow
from config import PurpleBoxConfig
from offline_scan import KnownMuse
real = workflow.execute_purple_workflow
main.execute_purple_workflow = lambda key, emit, **kw: real(
    key, emit, muse_factory=lambda s: KnownMuse(key), **kw)
uvicorn.run(main.create_app(PurpleBoxConfig(meta_api_key="offline-check-not-a-key")),
            host="127.0.0.1", port={port}, log_level="warning")
"""


def start_server(port: int, offline: bool) -> subprocess.Popen:
    env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"]}
    if offline:
        code = OFFLINE_SERVER.format(root=str(ROOT), tools=str(ROOT / ".jcode/tools"), port=port)
        cmd = [str(PYTHON), "-c", code]
    else:
        env_file = ROOT / ".env"
        keys = [
            line.split("=", 1)[1].strip()
            for line in env_file.read_text().splitlines()
            if line.startswith("META_MUSE_API_KEY=")
        ]
        if not keys or not keys[0]:
            raise SystemExit("META_MUSE_API_KEY is empty in .env; use --offline or set the key.")
        env["META_MUSE_API_KEY"] = keys[0]
        cmd = [str(PYTHON), "main.py", "--serve", "--port", str(port)]
    proc = subprocess.Popen(
        cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
            return proc
        except OSError:
            if proc.poll() is not None:
                raise SystemExit(f"Server exited early; is port {port} free?") from None
            time.sleep(0.5)
    raise SystemExit("Server did not become ready.")


async def drive(port: int, target: str, shot: Path, devtools: int, profile: str | None) -> dict:
    import websockets  # installed in the project venv

    tabs = None
    for _ in range(50):
        try:
            tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{devtools}/json"))
            break
        except OSError:
            await asyncio.sleep(0.2)
    page = next(t for t in tabs if t["type"] == "page")
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=None) as ws:
        counter = 0

        async def call(method, **params):
            nonlocal counter
            counter += 1
            ident = counter
            await ws.send(json.dumps({"id": ident, "method": method, "params": params}))
            while True:
                message = json.loads(await ws.recv())
                if message.get("id") == ident:
                    return message.get("result", message)

        async def js(expression):
            result = await call("Runtime.evaluate", expression=expression, returnByValue=True)
            if "exceptionDetails" in result:
                raise RuntimeError(result["result"].get("description", "page script failed"))
            return result["result"].get("value")

        await call(
            "Emulation.setDeviceMetricsOverride",
            width=1440,
            height=2200,
            deviceScaleFactor=1,
            mobile=False,
        )
        await call("Page.navigate", url=f"http://localhost:{port}/")
        await asyncio.sleep(2)
        await js(f"document.querySelector('.target[data-key={target}]').click()")
        if profile:
            await js(f"document.querySelector('.profile[data-key={profile}]').click()")
        if await js("document.getElementById('run-btn').disabled"):
            raise SystemExit("Run button is disabled; check the API key and Docker chips.")
        await js("document.getElementById('run-btn').click()")
        for _ in range(600):
            await asyncio.sleep(1)
            if not await js("document.getElementById('result-panel').hidden"):
                break
        result = json.loads(await js(READOUT))
        image = await call("Page.captureScreenshot", format="png", captureBeyondViewport=True)
        shot.write_bytes(base64.b64decode(image["data"]))
        return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("target")
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--devtools-port", type=int, default=9335)
    parser.add_argument("--shot", type=Path, default=Path(tempfile.gettempdir()) / "ui-scan.png")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--profile", choices=["economy", "balanced", "quality"])
    args = parser.parse_args()
    chrome_bin = shutil.which("google-chrome") or shutil.which("chromium-browser")
    if not chrome_bin:
        raise SystemExit("Chrome or Chromium is required.")
    server = start_server(args.port, args.offline)
    profile = tempfile.mkdtemp(prefix="ui-scan-")
    chrome = subprocess.Popen(
        [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            f"--remote-debugging-port={args.devtools_port}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        result = asyncio.run(
            asyncio.wait_for(
                drive(args.port, args.target, args.shot, args.devtools_port, args.profile),
                timeout=660,
            )
        )
        print(json.dumps(result, indent=2))
        print(f"Screenshot: {args.shot}", file=sys.stderr)
        return 0 if result["status"] == "Boundary check passed" else 1
    finally:
        for proc, how in ((chrome, signal.SIGTERM), (server, signal.SIGINT)):
            proc.send_signal(how)
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
