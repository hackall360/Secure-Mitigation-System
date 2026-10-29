#!/usr/bin/env python3
# Run one real scan by driving the dashboard in a headless browser; prints the result card as JSON and saves a screenshot.
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Usage: ui_scan.py TARGET [--profile economy|balanced|quality] [--port 8797] [--shot PATH] [--offline]
       [--browser auto|chrome|chromium|edge|brave|firefox] [--geckodriver-port PORT]

Starts the real server (only META_MUSE_API_KEY from .env, all other settings default),
opens the dashboard in the requested headless browser, selects TARGET, clicks Run
verification, waits for the result card and prints it. --offline swaps only
MetaMuseClient for the known fixture outputs (no API cost). Real mode spends Meta API
credit (about $0.05-0.15).

Chrome-family browsers are driven over the DevTools protocol. Firefox speaks no CDP,
so it is driven over WebDriver via a local geckodriver (stdlib urllib only).
Chrome/Chromium/Edge/Brave share the CDP path; Edge and Brave are found by their
usual binary names when installed.
"""

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

# Chrome-family binaries by variant. PATH lookup first, then the usual absolute
# locations (Windows install dirs, macOS .app bundles). All of these speak CDP,
# so any found binary can drive the existing DevTools path.
CHROME_CANDIDATES = {
    "chrome": [
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "chrome.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ],
    "chromium": [
        "chromium",
        "chromium-browser",
        "chromium.exe",
        r"C:\Program Files\Chromium\Application\chrome.exe",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "edge": [
        "microsoft-edge",
        "microsoft-edge-stable",
        "msedge",
        "msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ],
    "brave": [
        "brave-browser",
        "brave-browser-stable",
        "brave",
        "brave.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ],
}

# Firefox binaries for the WebDriver path (binary location is passed to
# geckodriver only when found off PATH; geckodriver finds PATH installs itself).
FIREFOX_CANDIDATES = [
    "firefox",
    "firefox.exe",
    r"C:\Program Files\Mozilla Firefox\firefox.exe",
    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    "/Applications/Firefox.app/Contents/MacOS/firefox",
]


def find_browser_binary(variant: str, candidates: list[str]) -> str | None:
    for name in candidates:
        if (os.sep not in name and "/" not in name) or name.startswith("."):
            found = shutil.which(name)
            if found:
                return found
        elif Path(name).is_file():
            return name
    return None


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


# Real-page assertions shared by both browser engines, before starting the scan.
DESIGN_CHECK = """(async () => {
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const mode = document.getElementById('mode-demo');
  mode.click(); mode.focus();
  mode.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
  check(document.getElementById('mode-demo-build').getAttribute('aria-checked') === 'true',
    'ArrowRight must select Green build');
  check(document.activeElement.id === 'mode-demo-build', 'Arrow navigation must retain radio focus');
  check(!document.getElementById('demo-build-config').hidden, 'Green fields must be visible');
  document.getElementById('mode-project').click();
  check(!document.getElementById('project-form').hidden, 'Project fields must be visible');
  document.getElementById('mode-demo').click();
  check(!document.getElementById('demo-config').hidden, 'Demo targets must be restored');
  check([...document.querySelectorAll('.mode')].filter(n => n.tabIndex === 0).length === 1,
    'Mode switch needs one tab stop');
  for (const link of document.querySelectorAll('.workspace-rail nav a')) {
    const section = document.querySelector(link.getAttribute('href'));
    check(section, 'Navigation target must exist');
    link.click();
    await new Promise(resolve => setTimeout(resolve, 50));
    check(location.hash === link.hash, 'Navigation must reach its actual section');
  }
  check(document.querySelectorAll('.workspace-rail nav a').length === 4, 'Four section links');
  for (const id of ['red-log', 'blue-log', 'sys-log', 'comms-log']) {
    const log = document.getElementById(id);
    log.focus(); check(document.activeElement === log, 'Logs must accept keyboard focus');
  }
  document.getElementById('mode-demo').focus();
  window.scrollTo({top: 0, behavior: 'instant'});
  return true;
})()"""

LAYOUT_CHECK = """(() => {
  const width = document.documentElement.clientWidth;
  if (document.documentElement.scrollWidth > width + 1) throw new Error('Page overflows');
  for (const selector of ['.mode', '.target', '.workspace-rail nav a', '#run-btn']) {
    for (const node of document.querySelectorAll(selector)) {
      const r = node.getBoundingClientRect();
      if (r.width < 1 || r.left < -1 || r.right > width + 1)
        throw new Error('Unreachable control: ' + selector);
    }
  }
  for (const mode of ['demo-build', 'project', 'demo']) {
    document.querySelector('[data-mode="' + mode + '"]').click();
    for (const node of document.querySelectorAll('.field input, .field select, .field textarea')) {
      if (!node.getClientRects().length) continue;
      const r = node.getBoundingClientRect();
      if (r.left < -1 || r.right > width + 1) throw new Error('Form control overflows: ' + node.id);
    }
  }
  window.scrollTo({top: 0, behavior: 'instant'});
  return true;
})()"""

OFFLINE_SERVER = """
import sys
sys.path.insert(0, {root!r}); sys.path.insert(0, {tools!r})
import uvicorn, main
from modules.workflows import workflow
from modules.core.config import PurpleBoxConfig
from offline_scan import KnownMuse
real = workflow.execute_purple_workflow
main.execute_purple_workflow = lambda key, emit, **kw: real(
    key, emit, muse_factory=lambda s: KnownMuse(key), **kw)
uvicorn.run(main.create_app(PurpleBoxConfig(meta_api_key="offline-check-not-a-key")),
            host="127.0.0.1", port={port}, log_level="warning")
"""


def start_server(port: int, offline: bool) -> subprocess.Popen:
    env = {"PATH": os.environ["PATH"]}
    if "HOME" in os.environ:  # absent in some Windows service contexts
        env["HOME"] = os.environ["HOME"]
    if offline:
        code = OFFLINE_SERVER.format(root=str(ROOT), tools=str(ROOT / ".jcode/tools"), port=port)
        cmd = [str(PYTHON), "-c", code]
    else:
        env_file = ROOT / ".env"
        keys = [
            line.split("=", 1)[1].strip()
            for line in env_file.read_text(encoding="utf-8").splitlines()
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


async def drive(
    port: int,
    target: str,
    shot: Path,
    devtools: int,
    profile: str | None,
    design_check: bool = False,
) -> dict:
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
            result = await call(
                "Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True
            )
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
        if design_check:
            await js(DESIGN_CHECK)
            for width in (1440, 768, 390, 320):
                await call(
                    "Emulation.setDeviceMetricsOverride",
                    width=width,
                    height=1000,
                    deviceScaleFactor=1,
                    mobile=False,
                )
                await asyncio.sleep(0.2)
                await js(LAYOUT_CHECK)
                height = await js("document.documentElement.scrollHeight")
                image = await call(
                    "Page.captureScreenshot",
                    format="png",
                    captureBeyondViewport=True,
                    clip={"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
                )
                shot.with_stem(shot.stem + f"-{width}").write_bytes(base64.b64decode(image["data"]))
            await call(
                "Emulation.setEmulatedMedia",
                features=[{"name": "prefers-reduced-motion", "value": "reduce"}],
            )
            await js(
                "if (getComputedStyle(document.querySelector('.node')).animationName !== 'none') "
                "throw new Error('Reduced motion not honored')"
            )
            await call(
                "Emulation.setDeviceMetricsOverride",
                width=1440,
                height=2200,
                deviceScaleFactor=1,
                mobile=False,
            )
        await js(f"document.querySelector('.target[data-key=\"{target}\"]').click()")
        if profile:
            await js(f"document.querySelector('.profile[data-key=\"{profile}\"]').click()")
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


def wd_request(driver_base: str, method: str, path: str, body: dict | None = None) -> dict:
    """Minimal stdlib WebDriver client. No selenium dependency on purpose."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        driver_base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = json.load(error).get("value", {})
        raise RuntimeError(f"WebDriver {detail.get('error')}: {detail.get('message')}") from error


def drive_firefox(
    port: int,
    target: str,
    shot: Path,
    profile: str | None,
    gd_port: int,
    firefox_binary: str | None,
    design_check: bool = False,
) -> dict:
    """Drive the dashboard in headless Firefox via local geckodriver.

    Mirrors the CDP drive() step for step: navigate, pick target/profile, click
    run, poll the result panel, read the same result card, screenshot.
    geckodriver is spawned on 127.0.0.1 and terminated afterwards; the only
    requirement is a geckodriver binary on PATH (ships with the Firefox snap,
    `snap install firefox`, or https://github.com/mozilla/geckodriver).

    Cleanup only touches what this function spawned: its own WebDriver session
    (DELETE closes the headless Firefox geckodriver started) and its own
    geckodriver Popen handle. Never broad-kills; a user's running Firefox is
    a separate process with its own profile and is left alone.
    """
    gecko = shutil.which("geckodriver")
    if not gecko:
        raise SystemExit("geckodriver is required for --browser firefox (PATH).")
    driver = subprocess.Popen(
        [gecko, "--port", str(gd_port), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    session: str | None = None
    try:
        base = f"http://127.0.0.1:{gd_port}"
        for _ in range(50):
            try:
                if wd_request(base, "GET", "/status")["value"].get("ready"):
                    break
            except OSError:
                if driver.poll() is not None:
                    raise SystemExit("geckodriver exited before becoming ready.") from None
                time.sleep(0.2)
        else:
            raise SystemExit("geckodriver did not become ready.")
        options: dict = {"args": ["-headless"]}
        # /usr/bin/firefox on some distros is a shell wrapper (snap/apt
        # redirect), which geckodriver rejects as "binary is not a Firefox
        # executable". Pass the binary only when it looks like a real ELF.
        if firefox_binary and not Path(firefox_binary).name.lower().endswith(".exe"):
            try:
                with open(firefox_binary, "rb") as probe:
                    is_elf = probe.read(4) == b"\x7fELF"
            except OSError:
                is_elf = False
            if is_elf:
                options["binary"] = firefox_binary
            # else: omit; geckodriver finds Firefox on PATH by itself.
        session = wd_request(
            base,
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "browserName": "firefox",
                        "moz:firefoxOptions": options,
                    }
                }
            },
        )["value"]["sessionId"]

        def execute(script: str):
            return wd_request(
                base, "POST", f"/session/{session}/execute/sync", {"script": script, "args": []}
            )["value"]

        wd_request(base, "POST", f"/session/{session}/url", {"url": f"http://localhost:{port}/"})
        deadline = time.time() + 60
        while time.time() < deadline:
            if execute("return document.getElementById('run-btn') !== null"):
                break
            time.sleep(0.5)
        if design_check:
            checked = wd_request(
                base,
                "POST",
                f"/session/{session}/execute/async",
                {
                    "script": "const done = arguments[0]; ("
                    + DESIGN_CHECK
                    + ").then(() => done({ok: true}), e => done({error: e.message}));",
                    "args": [],
                },
            )["value"]
            if checked.get("error"):
                raise RuntimeError(checked["error"])
            for width in (1440, 768, 390, 320):
                wd_request(
                    base,
                    "POST",
                    f"/session/{session}/window/rect",
                    {"width": width, "height": 1000},
                )
                execute("return " + LAYOUT_CHECK)
                shot.with_stem(shot.stem + f"-{width}").write_bytes(
                    base64.b64decode(
                        wd_request(base, "GET", f"/session/{session}/screenshot")["value"]
                    )
                )
            wd_request(
                base, "POST", f"/session/{session}/window/rect", {"width": 1440, "height": 2200}
            )
        execute(f"document.querySelector('.target[data-key=\"{target}\"]').click()")
        if profile:
            execute(f"document.querySelector('.profile[data-key=\"{profile}\"]').click()")
        if execute("return document.getElementById('run-btn').disabled"):
            raise SystemExit("Run button is disabled; check the API key and Docker chips.")
        execute("document.getElementById('run-btn').click()")
        for _ in range(600):
            time.sleep(1)
            if execute("return !document.getElementById('result-panel').hidden"):
                break
        else:
            raise SystemExit("Result panel never appeared (600s).")
        result = json.loads(execute(f"return ({READOUT})"))
        shot.write_bytes(
            base64.b64decode(wd_request(base, "GET", f"/session/{session}/screenshot")["value"])
        )
        return result
    finally:
        if session is not None:
            try:
                wd_request(base, "DELETE", f"/session/{session}")
            except OSError:
                pass
        try:
            driver.terminate()
        except Exception:
            pass
        try:
            driver.wait(15)
        except subprocess.TimeoutExpired:
            try:
                driver.kill()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("target")
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--devtools-port", type=int, default=9335)
    parser.add_argument("--shot", type=Path, default=Path(tempfile.gettempdir()) / "ui-scan.png")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--design-check",
        action="store_true",
        help="Check keyboard navigation and responsive layouts before the scan",
    )
    parser.add_argument("--profile", choices=["economy", "balanced", "quality"])
    parser.add_argument(
        "--browser",
        default="auto",
        choices=["auto", "chrome", "chromium", "edge", "brave", "firefox"],
        help="Chrome, Chromium, Edge and Brave share the DevTools path; "
        "firefox is driven over WebDriver via a local geckodriver. "
        "'auto' tries each Chrome-family binary, then Firefox.",
    )
    parser.add_argument("--geckodriver-port", type=int, default=4444)
    args = parser.parse_args()
    server = start_server(args.port, args.offline)
    requested = args.browser
    # 'auto' prefers any Chrome-family binary (CDP path), then Firefox.
    # Explicit --browser values skip straight to that engine; a missing
    # binary is a hard error, never a silent fallback to another engine.
    if requested == "auto":
        for variant in ("chrome", "chromium", "edge", "brave"):
            if find_browser_binary(variant, CHROME_CANDIDATES[variant]):
                requested = variant
                break
        else:
            requested = "firefox"
    if requested == "firefox":
        firefox_binary = find_browser_binary("firefox", FIREFOX_CANDIDATES)
        if firefox_binary is None and not shutil.which("firefox"):
            raise SystemExit("Firefox was requested but no install was found.")
        try:
            result = drive_firefox(
                args.port,
                args.target,
                args.shot,
                args.profile,
                args.geckodriver_port,
                firefox_binary,
                args.design_check,
            )
        finally:
            try:
                server.terminate()
            except Exception:
                pass
            try:
                server.wait(15)
            except subprocess.TimeoutExpired:
                try:
                    server.kill()
                except Exception:
                    pass
        print(json.dumps(result, indent=2))
        print(f"Screenshot: {args.shot}", file=sys.stderr)
        return 0 if result["status"] == "Boundary check passed" else 1
    chrome_bin = find_browser_binary(requested, CHROME_CANDIDATES[requested])
    if not chrome_bin:
        raise SystemExit(
            f"{requested} was requested but no install was found "
            "(checked PATH plus the usual install directories)."
        )
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
                drive(
                    args.port,
                    args.target,
                    args.shot,
                    args.devtools_port,
                    args.profile,
                    args.design_check,
                ),
                timeout=660,
            )
        )
        print(json.dumps(result, indent=2))
        print(f"Screenshot: {args.shot}", file=sys.stderr)
        return 0 if result["status"] == "Boundary check passed" else 1
    finally:
        for proc in (chrome, server):
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
