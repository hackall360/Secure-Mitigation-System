#!/usr/bin/env python3
# Click-through live E2E for WebUI v3: real server + real Docker (Muse = KnownMuse), Launch in setup page, assert live verdict renders.
"""Usage: v3_live_e2e.py [--browser firefox|chrome] [--page prod|demo] [--port 8798] [--target KEY]

Starts the offline server exactly like `ui_scan.py --offline` (only Muse is
replaced by KnownMuse; workflow, Docker, cleanup are real), opens
/ (must redirect to the v3 start page), then the v3 setup page, clicks the
fixture + Launch like a user, and waits on the visual page (console.html or
demo.html) for the LIVE verdict rendered from the real WebSocket stream.
Asserts: no FAKE RUN label, stream lines rendered, findings counted, verdict
shown, pre/post exits. Prints one JSON proof record. Never touches port 8000.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".jcode" / "tools"))
import ui_scan  # noqa: E402  (reuse server + browser helpers, no re-derivation)

# Evaluated in-page; returns JSON once the live verdict lands, else null.
PROBE = {
    "prod": """(() => {
      const r = document.getElementById('result');
      if (!r || r.hidden) return null;
      const t = (id) => (document.getElementById(id) || {}).textContent || '';
      // Poll until the live verdict line propagates into the HUD counters.
      if (t('sc-ver') === '0') return null;
      return JSON.stringify({ page: location.pathname, title: t('r-title'), msg: t('r-msg'),
        facts: t('r-facts'), msgs: t('sc-msgs'), find: t('sc-find'), patch: t('sc-patch'),
        ver: t('sc-ver'), comms: document.getElementById('comms').childElementCount,
        fake: document.body.textContent.includes('FAKE RUN') });
    })()""",
    "demo": """(() => {
      const v = document.getElementById('verdict');
      if (!v || v.hidden) return null;
      const t = (id) => (document.getElementById(id) || {}).textContent || '';
      if (t('st-ver') === '0') return null;
      return JSON.stringify({ page: location.pathname, title: t('v-title'), pre: t('v-pre'),
        post: t('v-post'), reg: t('v-reg'), sha: t('v-sha'), msgs: t('st-msgs'),
        find: t('st-find'), patch: t('st-patch'), ver: t('st-ver'),
        comms: document.getElementById('comms').childElementCount,
        fake: document.body.textContent.includes('FAKE RUN') });
    })()""",
}

SETUP = {"prod": "prod-setup.html", "demo": "demo-setup.html"}


def click_script(page, target):
    card = ".c-fx" if page == "prod" else ".s-tcard"
    live = "" if page == "prod" else "document.getElementById('src-live').click();"
    return f"""(() => {{
      {live}
      const c = [...document.querySelectorAll('{card}')].find((b) => b.dataset.key === '{target}');
      if (!c) return 'no-card';
      c.click();
      const l = document.getElementById('launch');
      if (l.disabled) return 'launch-disabled';
      l.click();
      return 'clicked';
    }})()"""


class Firefox:
    def __init__(self):
        self.base = "http://127.0.0.1:14445"
        self.driver = subprocess.Popen(
            ["geckodriver", "--port", "14445", "--host", "127.0.0.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            try:
                if ui_scan.wd_request(self.base, "GET", "/status")["value"].get("ready"):
                    break
            except OSError:
                time.sleep(0.2)
        caps = {"browserName": "firefox", "moz:firefoxOptions": {"args": ["-headless"]}}
        self.sid = ui_scan.wd_request(
            self.base, "POST", "/session", {"capabilities": {"alwaysMatch": caps}}
        )["value"]["sessionId"]

    def go(self, url):
        ui_scan.wd_request(self.base, "POST", f"/session/{self.sid}/url", {"url": url})

    def url(self):
        return ui_scan.wd_request(self.base, "GET", f"/session/{self.sid}/url")["value"]

    def js(self, expr):
        return ui_scan.wd_request(
            self.base,
            "POST",
            f"/session/{self.sid}/execute/sync",
            {"script": f"return ({expr})", "args": []},
        )["value"]

    def close(self):
        try:
            ui_scan.wd_request(self.base, "DELETE", f"/session/{self.sid}")
        finally:
            self.driver.terminate()
            self.driver.wait(timeout=10)


class Chrome:
    """Minimal sync CDP over websockets (same mechanics as ui_scan.drive)."""

    def __init__(self, devtools=9337):
        import asyncio

        import websockets

        self.asyncio, self.websockets = asyncio, websockets
        self.profile = tempfile.mkdtemp(prefix="v3-e2e-")
        binary = ui_scan.find_browser_binary("chrome", ui_scan.CHROME_CANDIDATES["chrome"])
        self.proc = subprocess.Popen(
            [
                binary,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                f"--remote-debugging-port={devtools}",
                f"--user-data-dir={self.profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        tabs = None
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{devtools}/json"))
                break
            except OSError:
                time.sleep(0.2)
        self.ws_url = next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"]
        self.loop = asyncio.new_event_loop()
        self.ws = self.loop.run_until_complete(websockets.connect(self.ws_url, max_size=None))
        self.n = 0

    def _call(self, method, **params):
        async def go():
            self.n += 1
            ident = self.n
            await self.ws.send(json.dumps({"id": ident, "method": method, "params": params}))
            while True:
                msg = json.loads(await self.ws.recv())
                if msg.get("id") == ident:
                    return msg.get("result", msg)

        return self.loop.run_until_complete(go())

    def go(self, url):
        self._call("Page.navigate", url=url)

    def url(self):
        return self.js("location.href")

    def js(self, expr):
        res = self._call("Runtime.evaluate", expression=expr, returnByValue=True)
        if "exceptionDetails" in res:
            return None
        return res["result"].get("value")

    def close(self):
        try:
            self.loop.run_until_complete(self.ws.close())
        finally:
            self.proc.terminate()
            self.proc.wait(timeout=10)


def docker_leftovers():
    out = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "label=purplebox.session"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    return len(out.stdout.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", choices=("firefox", "chrome"), default="firefox")
    ap.add_argument("--page", choices=("prod", "demo"), default="prod")
    ap.add_argument("--port", type=int, default=8798)
    ap.add_argument("--target", default="node_query_sink")
    ap.add_argument("--timeout", type=int, default=420)
    args = ap.parse_args()
    if args.port == 8000:
        raise SystemExit("Port 8000 belongs to a foreign process here; pick another (LAW 7).")
    before = docker_leftovers()
    server = ui_scan.start_server(args.port, offline=True)
    browser = Firefox() if args.browser == "firefox" else Chrome()
    base = f"http://localhost:{args.port}"
    record = {"browser": args.browser, "page": args.page, "target": args.target}
    try:
        browser.go(base + "/")
        time.sleep(1.5)
        record["root_lands_on"] = browser.url()
        browser.go(f"{base}/web/{SETUP[args.page]}")
        clicked = None
        for _ in range(40):  # wait for probe() hydration to enable Launch
            time.sleep(0.5)
            clicked = browser.js(click_script(args.page, args.target))
            if clicked == "clicked":
                break
        record["launch"] = clicked
        if clicked != "clicked":
            raise RuntimeError(f"could not launch from setup page: {clicked}")
        deadline = time.monotonic() + args.timeout
        result = None
        while time.monotonic() < deadline:
            time.sleep(2)
            raw = browser.js(PROBE[args.page])
            if raw:
                result = json.loads(raw)
                break
        if result is None:
            raise RuntimeError("live verdict never rendered")
        record["result"] = result
    finally:
        browser.close()
        server.terminate()
        server.wait(timeout=15)
    time.sleep(2)
    record["docker_leftovers_delta"] = docker_leftovers() - before
    r = record["result"]
    checks = {
        "root_redirects_to_v3": record["root_lands_on"].endswith("/web/index.html"),
        "live_not_fake": r["fake"] is False,
        "stream_rendered": r["comms"] > 0 and int(r["msgs"] or 0) > 0,
        "finding_counted": int(r["find"] or 0) >= 1,
        "patch_counted": int(r["patch"] or 0) >= 1,
        "verified_counted": int(r["ver"] or 0) >= 1,
        "cleanup_zero_leftovers": record["docker_leftovers_delta"] <= 0,
    }
    record["checks"] = checks
    record["pass"] = all(checks.values())
    print(json.dumps(record, indent=2))
    return 0 if record["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
