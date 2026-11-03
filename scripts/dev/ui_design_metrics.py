#!/usr/bin/env python3
# Compare rendered dashboard readability, layout, focusability and motion against a Git baseline.
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Use project Python. Static presentation measurements complement ui_scan.py's live E2E."""

import argparse
import asyncio
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
MEASURE = """(() => {
  document.getElementById('project-form').hidden = false;
  const input = document.getElementById('project-path');
  const color = getComputedStyle(input, '::placeholder').color;
  const background = getComputedStyle(input).backgroundColor;
  const logs = ['red-log', 'blue-log', 'sys-log', 'comms-log'];
  let focusable = 0;
  for (const id of logs) {
    document.activeElement.blur();
    document.getElementById(id).focus();
    if (document.activeElement.id === id) focusable++;
  }
  const rows = new Set([...document.querySelectorAll('.mode')]
    .map(n => Math.round(n.getBoundingClientRect().top))).size;
  const decorative = '.orb, .scanline, .gradient, .hype-chip, .empty-icon, .backdrop';
  const animations = document.getAnimations().filter(a => {
    const n = a.effect && a.effect.target;
    return n && n.matches(decorative) && n.getClientRects().length;
  }).length;
  return {viewport: innerWidth, placeholderColor: color, inputBackground: background,
    modeRows: rows, focusableLogs: focusable, decorativeAnimations: animations,
    sectionLinks: document.querySelectorAll('.workspace-rail nav a').length};
})()"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def contrast(foreground, background):
    def luminance(color):
        values = [float(v) / 255 for v in re.findall(r"[\d.]+", color)[:3]]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    a, b = sorted((luminance(foreground), luminance(background)))
    return round((b + 0.05) / (a + 0.05), 2)


async def measure(ws_url, base_url):
    async with websockets.connect(ws_url, max_size=2**22) as ws:
        sequence = 0

        async def call(method, **params):
            nonlocal sequence
            sequence += 1
            await ws.send(json.dumps({"id": sequence, "method": method, "params": params}))
            while True:
                answer = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if answer.get("id") == sequence:
                    if "error" in answer:
                        raise RuntimeError(answer["error"])
                    return answer["result"]

        target = await call("Target.createTarget", url="about:blank")
        attached = await call("Target.attachToTarget", targetId=target["targetId"], flatten=True)
        session = attached["sessionId"]

        async def page(method, **params):
            nonlocal sequence
            sequence += 1
            await ws.send(
                json.dumps(
                    {"id": sequence, "sessionId": session, "method": method, "params": params}
                )
            )
            while True:
                answer = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if answer.get("id") == sequence:
                    if "error" in answer:
                        raise RuntimeError(answer["error"])
                    return answer["result"]

        results = {}
        for version in ("before", "after"):
            results[version] = {}
            for width in (1440, 390):
                await page(
                    "Emulation.setDeviceMetricsOverride",
                    width=width,
                    height=1000,
                    deviceScaleFactor=1,
                    mobile=False,
                )
                await page("Page.navigate", url=f"{base_url}/{version}/index.html")
                for _ in range(40):
                    await asyncio.sleep(0.05)
                    state = await page("Runtime.evaluate", expression="document.readyState")
                    if state.get("result", {}).get("value") == "complete":
                        break
                data = await page("Runtime.evaluate", expression=MEASURE, returnByValue=True)
                if "exceptionDetails" in data:
                    raise RuntimeError(data["exceptionDetails"])
                metrics = data["result"]["value"]
                metrics["placeholderContrast"] = contrast(
                    metrics["placeholderColor"], metrics["inputBackground"]
                )
                results[version][str(width)] = metrics
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="d7763fa")
    args = parser.parse_args()
    chrome = shutil.which("google-chrome")
    if not chrome:
        raise SystemExit("google-chrome must be on PATH")
    scratch = Path(os.environ.get("JCODE_SCRATCH_DIR", ROOT / "reports"))
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ui-metrics-", dir=scratch) as temp:
        folder = Path(temp)
        for label in ("before", "after"):
            dest = folder / label / "static"
            dest.mkdir(parents=True)
            for filename in ("index.html", "app.css"):
                if label == "before":
                    content = subprocess.check_output(
                        ["git", "show", f"{args.baseline}:static/{filename}"],
                        cwd=ROOT,
                        text=True,
                        timeout=10,
                    )
                else:
                    content = (ROOT / "static" / filename).read_text()
                if filename == "index.html":
                    # Isolate actual markup/CSS, never execute scan logic or fetch API data.
                    content = re.sub(r"<script\b[^>]*>.*?</script>", "", content, flags=re.S)
                    content = content.replace('href="/static/', f'href="/{label}/static/')
                    (folder / label / filename).write_text(content)
                else:
                    (dest / filename).write_text(content)
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(folder))
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        profile = folder / "profile"
        proc = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--remote-debugging-port=0",
                f"--user-data-dir={profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            import time

            active = profile / "DevToolsActivePort"
            for _ in range(100):
                if active.exists():
                    break
                if proc.poll() is not None:
                    raise RuntimeError("Chrome exited before debugger startup")
                time.sleep(0.05)
            port, endpoint = active.read_text().splitlines()[:2]
            results = asyncio.run(
                asyncio.wait_for(
                    measure(
                        f"ws://127.0.0.1:{port}{endpoint}", f"http://127.0.0.1:{server.server_port}"
                    ),
                    timeout=30,
                )
            )
            print(json.dumps(results, indent=2))
            for width in ("1440", "390"):
                before, after = results["before"][width], results["after"][width]
                assert after["placeholderContrast"] >= 4.5 > before["placeholderContrast"]
                assert after["modeRows"] == 1 < before["modeRows"]
                assert after["focusableLogs"] == 4 > before["focusableLogs"]
                assert after["decorativeAnimations"] == 0 < before["decorativeAnimations"]
                assert after["sectionLinks"] == 4 > before["sectionLinks"]
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
