# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): keyboard-operated stepper must echo the new value while focused.

Failing behavior (found live 2026-11-02, headless Firefox): focus the Sweep
depth spinbutton on prod-setup (project mode), press ArrowUp — the state
advances (1 -> 2) but the focused input keeps showing "1" until blur, because
OptionForm._sync skips the focused input (`document.activeElement !== i`).
A keyboard-only user gets no feedback and double-presses into a wrong value.

Gate 3 vehicle: real headless Firefox via geckodriver (repo venv lacks
selenium/playwright by design; the stdlib WebDriver path in
scripts/dev/ui_scan.py is the house way). Skips cleanly without geckodriver.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

from ui_scan import start_server, wd_request  # noqa: E402

GD_PORT = 19601
pytestmark = pytest.mark.skipif(
    shutil.which("geckodriver") is None,
    reason="geckodriver required for real-browser stepper proof",
)

STEP_SCRIPT = """(() => {
  const proj = [...document.querySelectorAll('.c-mode')].find((b) => b.dataset.mode === 'project');
  proj.click();
  const input = document.querySelector('[data-key="sweep_passes"] input');
  input.focus();
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true, cancelable: true }));
  return JSON.stringify({ display: input.value, focused: document.activeElement === input });
})()"""


def _drive(port: int) -> dict:
    import json as _json

    gecko = shutil.which("geckodriver")
    driver = subprocess.Popen(
        [gecko, "--port", str(GD_PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    session = None
    try:
        base = f"http://127.0.0.1:{GD_PORT}"
        for _ in range(50):
            try:
                if wd_request(base, "GET", "/status")["value"].get("ready"):
                    break
            except OSError:
                time.sleep(0.2)
        session = wd_request(
            base,
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "browserName": "firefox",
                        "moz:firefoxOptions": {"args": ["-headless"]},
                    }
                }
            },
        )["value"]["sessionId"]

        def run_js(script: str):
            return wd_request(
                base, "POST", f"/session/{session}/execute/sync", {"script": script, "args": []}
            )["value"]

        run_js(
            f"window.location.href = 'http://127.0.0.1:{port}/web/prod-setup.html'; return true;"
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if run_js(
                "return document.querySelector('[data-key=\"sweep_passes\"] input') !== null"
            ):
                break
            time.sleep(0.5)
        return _json.loads(run_js(f"return ({STEP_SCRIPT})"))
    finally:
        if session is not None:
            try:
                wd_request(base, "DELETE", f"/session/{session}")
            except OSError:
                pass
        driver.terminate()
        driver.wait(timeout=15)


def test_keyboard_stepper_echoes_value_while_focused():
    server = start_server(8798, offline=True)
    try:
        result = _drive(8798)
    finally:
        server.terminate()
        server.wait(timeout=15)
    assert result["focused"] is True
    assert result["display"] == "2", (
        f"focused stepper must echo the bumped value, got {result['display']!r}"
    )
