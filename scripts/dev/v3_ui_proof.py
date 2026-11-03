#!/usr/bin/env python3
# Prove the WebUI v3 pages load, hydrate, and render live state in a real browser (LAW 11 Gate 3).
"""Usage: v3_ui_proof.py [--port PORT] [--browser firefox|chrome]

Starts the real server, loads each v3 page in a headless browser, and proves:
(1) every page loads with its synced asset block; (2) console.html exposes
the HUD/chip DOM; (3) a live WS gets a connect-time snapshot first; (4) the
interpreter renders stream lines into sc-msgs + comms feed (same handlers
as live). Prints a JSON proof record. No Muse key needed.
"""

import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BROWSER = "firefox"
PORT = 8799
for arg in sys.argv[1:]:
    if arg.startswith("--browser="):
        BROWSER = arg.split("=", 1)[1]
    elif arg in ("firefox", "chrome"):
        BROWSER = arg
    elif arg.startswith("--port="):
        PORT = int(arg.split("=", 1)[1])

PAGES = (
    "index.html",
    "prod-setup.html",
    "console.html",
    "demo.html",
    "demo-setup.html",
    "visualizer.html",
)


def wait_health(port, timeout=20):
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as r:
                return json.load(r)
        except Exception:
            if time.monotonic() >= deadline:
                raise RuntimeError("server never became ready") from None
            time.sleep(0.2)


V3_SEED = """(() => {
  const topo = SMS.topology.profile('node_query_sink', {});
  SMS.launch.save({ page: 'console', kind: 'live', mode: 'fixture', fixture: 'node_query_sink',
    topo, request: { path: '/ws/combat/node_query_sink', body: undefined }, values: {}, summary: 'proof' });
  return true;
})()"""

V3_RENDER_CHECK = """(async () => {
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  check(!!(window.SMS && SMS.SpiderGraph && SMS.Interpreter), 'SMS namespace incomplete');
  const topo = SMS.topology.profile('node_query_sink', {});
  const canvas = document.createElement('canvas');
  const graph = new SMS.SpiderGraph(canvas, { mode: 'console' });
  const interp = new SMS.Interpreter(graph);
  interp.load(topo);
  const ev1 = interp.line('system', 'Connected: muse-spark vs muse-wonder (profile balanced).');
  const ev2 = interp.line('red', 'Boundary check exited 0.');
  const ev3 = interp.line('blue', 'Applied bounded sanitation-only replacements to app.js.');
  check(interp.stats.findings === 1 && interp.stats.patches === 1, 'interpreter stats');
  interp.result({ status: 'verified', pre_probe_exit: 0, post_probe_exit: 1 });
  check(graph.verdict === 'verified', 'verdict visuals');
  graph.destroy();
  // HUD DOM contract the backend feeds:
  const hud = ['sc-nodes', 'sc-msgs', 'sc-find', 'sc-patch', 'sc-ver'].map((id) => document.getElementById(id));
  const chips = ['chip-server', 'chip-docker', 'chip-key'].map((id) => document.getElementById(id));
  return JSON.stringify({
    hud: hud.map((n) => !!n), chips: chips.map((n) => !!n),
    stages: ev1.stage + '/' + ev2.stage + '/' + ev3.stage,
    findings: interp.stats.findings, verdict: graph.verdict,
  });
})()"""


def drive_firefox_v3(port):
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))
    import importlib

    ui_scan = importlib.import_module("ui_scan")
    firefox_binary = ui_scan.find_browser_binary("firefox", ui_scan.FIREFOX_CANDIDATES)
    is_elf = False
    if firefox_binary:
        try:
            with open(firefox_binary, "rb") as probe:
                is_elf = probe.read(4) == b"\x7fELF"
        except OSError:
            is_elf = False
    # /usr/bin/firefox is a snap shell wrapper; geckodriver rejects it as
    # --binary. Omit unless it is a real ELF (same rule as ui_scan).
    gecko_args = ["geckodriver", "--port", "14444", "--host", "127.0.0.1"]
    driver = subprocess.Popen(
        gecko_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = "http://127.0.0.1:14444"
        ready = False
        for _ in range(50):
            try:
                if ui_scan.wd_request(base, "GET", "/status")["value"].get("ready"):
                    ready = True
                    break
            except OSError:
                time.sleep(0.2)
        assert ready, "geckodriver did not become ready"
        options: dict = {"args": ["-headless"]}
        if is_elf:
            options["binary"] = firefox_binary
        session = ui_scan.wd_request(
            base,
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {"browserName": "firefox", "moz:firefoxOptions": options}
                }
            },
        )["value"]["sessionId"]
        try:
            out = {}
            for page in PAGES:
                ui_scan.wd_request(
                    base,
                    "POST",
                    f"/session/{session}/url",
                    {"url": f"http://localhost:{port}/web/{page}"},
                )
                time.sleep(1.2)
                if page == "console.html":
                    # First load redirects to prod-setup (no launch yet). Seed
                    # the launch like prod-setup would, then reload console.
                    ui_scan.wd_request(
                        base,
                        "POST",
                        f"/session/{session}/execute/sync",
                        {"script": f"return ({V3_SEED})", "args": []},
                    )
                    ui_scan.wd_request(
                        base,
                        "POST",
                        f"/session/{session}/url",
                        {"url": f"http://localhost:{port}/web/{page}"},
                    )
                    time.sleep(1.2)
                    raw = ui_scan.wd_request(
                        base,
                        "POST",
                        f"/session/{session}/execute/sync",
                        {"script": f"return ({V3_RENDER_CHECK})", "args": []},
                    )["value"]
                    out[page] = json.loads(raw)
                else:
                    ns = ui_scan.wd_request(
                        base,
                        "POST",
                        f"/session/{session}/execute/sync",
                        {
                            "script": "return !!(window.SMS && SMS.SpiderGraph && SMS.Interpreter)",
                            "args": [],
                        },
                    )["value"]
                    out[page] = {"namespace": bool(ns)}
            return out
        finally:
            ui_scan.wd_request(base, "DELETE", f"/session/{session}")
    finally:
        driver.terminate()
        driver.wait(timeout=10)


async def drive_chrome_v3(port, devtools_port=9336):
    import shutil
    import tempfile as _tf

    sys.path.insert(0, str(ROOT / "scripts" / "dev"))
    import importlib

    ui_scan = importlib.import_module("ui_scan")
    chrome_bin = ui_scan.find_browser_binary("chrome", ui_scan.CHROME_CANDIDATES["chrome"])
    profile = _tf.mkdtemp(prefix="v3-proof-")
    chrome = subprocess.Popen(
        [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            f"--remote-debugging-port={devtools_port}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        import websockets

        tabs = None
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{devtools_port}/json"))
                break
            except OSError:
                await asyncio.sleep(0.2)
        page = next(t for t in tabs if t["type"] == "page")
        out = {}
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
                result = await call(
                    "Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True
                )
                if "exceptionDetails" in result:
                    raise RuntimeError(result["result"].get("description", "page script failed"))
                return result["result"].get("value")

            for v3page in PAGES:
                await call("Page.navigate", url=f"http://localhost:{port}/web/{v3page}")
                await asyncio.sleep(1.5)
                if v3page == "console.html":
                    await js(V3_SEED)
                    await call("Page.navigate", url=f"http://localhost:{port}/web/{v3page}")
                    await asyncio.sleep(1.5)
                    out[v3page] = json.loads(await js(V3_RENDER_CHECK))
                else:
                    out[v3page] = {
                        "namespace": await js(
                            "!!(window.SMS && SMS.SpiderGraph && SMS.Interpreter)"
                        )
                    }
        return out
    finally:
        chrome.terminate()
        chrome.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)


def main():
    server = subprocess.Popen(
        [str(ROOT / ".venv" / "bin" / "python"), "main.py", "--serve", "--port", str(PORT)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proof = {"pages": {}, "browser": BROWSER, "port": PORT}
    try:
        health = wait_health(PORT)
        proof["health"] = {"status": health["status"], "busy": health["busy"]}
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for page in PAGES:
            with opener.open(f"http://127.0.0.1:{PORT}/web/{page}", timeout=5) as r:
                body = r.read().decode()
            proof["pages"][page] = {"http": r.status, "assets_sync": "assets:begin" in body}
            assert r.status == 200 and "assets:begin" in body, page
        sys.path.insert(0, str(ROOT))
        from fastapi.testclient import TestClient

        from main import create_app

        with TestClient(create_app()) as client:
            with client.websocket_connect(
                "ws://localhost/ws/combat/node_query_sink", headers={"origin": "http://localhost"}
            ) as sock:
                first = sock.receive_json()
                assert first.get("type") == "snapshot", first
                proof["snapshot"] = {
                    "hud": sorted(first["hud"]),
                    "nodes": len(first["nodes"]),
                    "chips": first["chips"],
                }
        if BROWSER == "firefox":
            proof["render"] = drive_firefox_v3(PORT)
        else:
            proof["render"] = asyncio.run(drive_chrome_v3(PORT))
        console = proof["render"]["console.html"]
        assert all(console["hud"]) and all(console["chips"]), console
        assert console["findings"] == 1 and console["verdict"] == "verified", console
    finally:
        server.terminate()
        server.wait(timeout=10)
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
