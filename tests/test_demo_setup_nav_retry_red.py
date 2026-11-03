# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): demo/setup bugs found live 2026-11-03.

Bug 1 — segmented up/down dead (web/js/options/form.js): the segmented
radiogroup keydown map only knows ArrowRight/ArrowLeft. On the demo setup
"Operational mode" control (extra_light/light), ArrowUp/ArrowDown do
nothing — the WAI-ARIA radio-group pattern expects all four arrows to
move. A keyboard-only user is stuck left/right only.

Bug 2 — single transport blip kills the whole scan (library/core/agents.py):
_request retries transient HTTP statuses (429/502/503/504) but an
httpx.HTTPError (timeout, DNS hiccup, connection reset) raises AgentError
immediately on attempt 0 — the second attempt never runs. One blip ends
the run as status=error ("Scan could not complete / The run ended before
we could decide. Nothing was changed"), exactly the demo failure.

Bug 2 fix shape (bounded, policy-safe): retry the transport error ONCE
(attempt 0 only, same bound as the status path), then fail with the same
no-fallback message. No fallback provider is added (SPEC strict model
lock); only the wasted attempt is reclaimed.
"""

from __future__ import annotations

import json as _json
import subprocess

import httpx
import pytest

import main  # noqa: F401  (import surface for MetaMuseClient config)
from library.core.agents import AgentError, MetaMuseClient
from library.core.config import PurpleBoxConfig

# ---------- Bug 1: segmented up/down (node --check vehicle) ----------

SEG_SCRIPT = """(() => {
  const src = require('fs').readFileSync('web/js/options/form.js', 'utf8');
  const i = src.indexOf("seg.addEventListener('keydown'");
  const map = src.slice(i, i + 600);
  const has = (k) => map.includes(k);
  process.stdout.write(JSON.stringify({ up: has('ArrowUp'), down: has('ArrowDown'), right: has('ArrowRight'), left: has('ArrowLeft') }));
})()"""


def test_segmented_handles_all_four_arrows():
    out = subprocess.run(["node", "-e", SEG_SCRIPT], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, f"node probe failed: {out.stderr[:200]}"
    got = _json.loads(out.stdout.strip())
    assert got["right"] and got["left"], f"left/right must keep working: {got}"
    assert got["up"] and got["down"], (
        f"segmented radiogroup must move on ArrowUp/ArrowDown (WAI-ARIA), got {got}"
    )


# ---------- Bug 2: transient transport error retried once ----------

FINDING = {
    "vulnerability_class": "input validation",
    "sink_location": "app.js:15",
    "analysis_summary": "An unexpected type reaches an expression.",
    "verification_script_python": "import sys\nsys.exit(0)\n",
}


def _ok_response():
    return httpx.Response(
        200, json={"choices": [{"message": {"content": __import__("json").dumps(FINDING)}}]}
    )


@pytest.mark.asyncio
async def test_transport_blip_retried_once_then_succeeds():
    """One timeout followed by success must NOT kill the scan."""
    calls = []

    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("dns hiccup")
        return _ok_response()

    client = MetaMuseClient(
        PurpleBoxConfig(meta_api_key="unit-test-key"),
        transport=httpx.MockTransport(handle),
    )
    try:
        result = await client.run_red_team_analysis("app.js", "source")
        assert result.sink_location == "app.js:15"
        assert len(calls) == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_persistent_transport_failure_still_fails_closed_no_fallback():
    """Two blips in a row: fail with the same no-fallback message (SPEC lock holds)."""
    calls = []

    def handle(request):
        calls.append(request)
        raise httpx.ConnectTimeout("still down")

    client = MetaMuseClient(
        PurpleBoxConfig(meta_api_key="unit-test-key"),
        transport=httpx.MockTransport(handle),
    )
    try:
        with pytest.raises(AgentError, match="no fallback provider"):
            await client.run_red_team_analysis("app.js", "source")
        assert len(calls) == 2, f"bounded retry = exactly 2 attempts, got {len(calls)}"
    finally:
        await client.aclose()
