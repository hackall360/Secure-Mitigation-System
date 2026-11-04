# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Slice E RED pins: additive live-feedback emits for long scans.

Goal (Slice E):
1. Per-phase progress logs: red batch i/N, blue attempt index, sandbox
   verify start/done. Same ``[phase ...]`` shape; never break existing
   parsers (tests/test_v3_live_console.py, tests/test_v3_live_stream_beats.py).
2. Chatter hooks while awaiting model calls: persona-voice lines wired into
   the await gaps, rate-limited so they cannot flood.
3. WS backpressure: emit can never block cleanup (make_log swallows; prove
   under test). UI caps bound long-run feeds (comms 120 / activity 1500 /
   timeline 900 / events 2000 — additive only, no UI change here).

This file is RED-first: every test FAILS pre-change for a functional reason
(missing progress line, missing rate limit, emit blocking cleanup). No
mocks of the unit under test — real workflow code, faked Docker + model
boundaries only (tests/helpers.py doubles).
"""

from __future__ import annotations

import re

import pytest
from helpers import TEST_CONFIG as CONFIG
from helpers import FakeFixtureMuse as FakeFixtureMuse
from helpers import FakeFixtureSandbox as FakeFixtureSandbox
from helpers import FakeProjectMuse as FakeProjectMuse
from helpers import FakeProjectSandbox
from helpers import project_verification as verification
from helpers import run_fixture_workflow as run_fixture

from modules.workflows.project_workflow import ProjectWorkflowInput


def _lines(events):
    return [message for _, message in events]


async def test_progress_red_batch_fraction_observed_per_batch(tmp_path, monkeypatch):
    """Long project scans emit one red batch progress line per source batch.

    RED: project_workflow emits no ``[phase red review] batch i/N`` line today.
    """
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    events: list[tuple[str, str]] = []

    async def emit(team, message):
        events.append((team, message))

    from modules.workflows.project_workflow import execute_project_workflow

    project = ProjectWorkflowInput(
        name="demo",
        files={
            # Two chunky files force >= 2 batches at a small batch bound.
            "src/a.py": "x = input()\n" * 400,
            "src/b.py": "y = input()\n" * 400,
        },
        regression_command=["pytest", "-q"],
    )
    from modules.workflows.project_workflow import ProjectWorkflowLimits

    muse = FakeProjectMuse(red_outcomes=["no_finding"])
    sandbox = FakeProjectSandbox([verification(1)])
    await execute_project_workflow(
        project,
        emit,
        config=CONFIG,
        limits=ProjectWorkflowLimits(max_batch_bytes=2048),
        sandbox_factory=lambda _settings: sandbox,
        muse_factory=lambda _settings: muse,
    )
    red_batch = [m for m in _lines(events) if "[phase red review] batch " in m]
    assert red_batch, "expected per-batch red progress lines, got none"


async def test_progress_blue_attempt_index_observed(tmp_path, monkeypatch):
    """Blue proposal batches carry an attempt index so long runs show progress.

    RED: propose_blue batches emit no ``attempt i/N`` progress today.
    """
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    events: list[tuple[str, str]] = []

    async def emit(team, message):
        events.append((team, message))

    muse = FakeProjectMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeProjectSandbox([verification(1), verification(0), verification(1)])
    from modules.workflows.project_workflow import ProjectWorkflowInput, execute_project_workflow

    project = ProjectWorkflowInput(
        name="demo",
        files={"src/app.py": "value = input()\nprint(value)\n"},
        regression_command=["pytest", "-q"],
    )
    await execute_project_workflow(
        project,
        emit,
        config=CONFIG,
        sandbox_factory=lambda _settings: sandbox,
        muse_factory=lambda _settings: muse,
    )
    blue_attempt = [m for _, m in events if "attempt" in m and "[phase blue patch]" in m]
    assert blue_attempt, "expected blue attempt-index progress lines, got none"


async def test_progress_sandbox_verify_start_done_pair(tmp_path, monkeypatch):
    """Each sandbox verify is bracketed by start/done progress lines.

    RED: today the fixture loop emits only the exit-code line; there is no
    ``[phase verify] start`` / ``[phase verify] done`` pair around it.
    """
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    events: list[tuple[str, str]] = []

    async def emit(team, message):
        events.append((team, message))

    await run_fixture([0, 0, 0, 1, 0], emit=emit)
    messages = _lines(events)
    starts = [m for m in messages if "[phase verify] start" in m]
    dones = [m for m in messages if "[phase verify] done" in m]
    assert starts and dones, f"expected verify start/done pairs, got {messages!r}"
    assert len(starts) == len(dones), "every verify start needs a done"


async def test_chatter_rate_limit_respected_on_long_runs():
    """Chatter hooks into model-await gaps but never floods: hard cap per run.

    RED: no CHATTER_EVERY / cap constant exists today.
    """
    from modules.shared import sms_progress as pa

    cap = getattr(pa, "CHATTER_MAX_PER_RUN", None)
    every = getattr(pa, "CHATTER_EVERY_N_BATCHES", None)
    assert isinstance(cap, int) and cap > 0, "expected CHATTER_MAX_PER_RUN positive int"
    assert isinstance(every, int) and every > 0, "expected CHATTER_EVERY_N_BATCHES positive int"


async def test_chatter_await_gap_lines_are_rate_limited(tmp_path, monkeypatch):
    """A many-batch red review emits chatter but stays under the per-run cap.

    RED: no await-gap chatter exists today, so zero chatter lines appear.
    """
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    from modules.shared import sms_progress as pa

    cap = getattr(pa, "CHATTER_MAX_PER_RUN", 8)
    events: list[tuple[str, str]] = []

    async def emit(team, message):
        events.append((team, message))

    from modules.workflows.project_workflow import (
        ProjectWorkflowLimits,
        execute_project_workflow,
    )

    project = ProjectWorkflowInput(
        name="demo",
        files={f"src/f{i}.py": "x = input()\n" * 200 for i in range(12)},
        regression_command=["pytest", "-q"],
    )
    muse = FakeProjectMuse(red_outcomes=["no_finding"])
    sandbox = FakeProjectSandbox([verification(1)])
    await execute_project_workflow(
        project,
        emit,
        config=CONFIG,
        limits=ProjectWorkflowLimits(max_batch_bytes=2048),
        sandbox_factory=lambda _settings: sandbox,
        muse_factory=lambda _settings: muse,
    )
    assert len(muse.calls) > cap, f"test needs more model calls than the cap, got {len(muse.calls)}"
    chatter_lines = [m for _, m in events if "Breakwater" in m or "Bastion" in m]
    assert chatter_lines, "expected await-gap chatter lines"
    assert len(chatter_lines) <= cap, f"chatter flooded: {len(chatter_lines)} > {cap}"


async def test_slow_emit_cannot_block_cleanup():
    """WS backpressure: a hanging emit never stalls the scan tail or cleanup.

    make_log already swallows emit *errors*; per-emit latency is bounded too
    (EMIT_TIMEOUT_S), so a backpressured socket degrades to dropped frames —
    every pre-cleanup emit resolves and cleanup always runs. Post-change the
    full not-confirmed path completes in ~7 s (14 emits x 0.5 s bound).
    RED: pre-change this hangs forever (every emit awaits the dead socket).
    """
    import asyncio

    from modules.workflows.workflow import execute_purple_workflow

    async def hanging_emit(team, message):
        await asyncio.sleep(30)

    sandbox = FakeFixtureSandbox([0, 1])
    muse = FakeFixtureMuse()
    result = await asyncio.wait_for(
        execute_purple_workflow(
            "node_query_sink",
            hanging_emit,
            config=CONFIG,
            sandbox_factory=lambda settings: sandbox,
            muse_factory=lambda settings: muse,
        ),
        timeout=30,
    )
    assert result.status == "not_confirmed", result.message
    assert sandbox.closed, "cleanup must complete under backpressure"


async def test_make_log_swallows_emit_failure_during_cleanup():
    """A raising emit (closed UI socket) still lets cleanup complete.

    Pins the existing make_log error-swallow contract at the leaf. Passes
    pre-change (documents the floor the latency fix must preserve).
    """
    from modules.shared.sms_async import make_log

    async def dead_emit(team, message):
        raise ConnectionError("socket closed")

    log = make_log(dead_emit)
    await log("system", "[phase cleanup] Session containers removed.")
    await log("red", "[phase red review] batch 1/2.")


async def test_make_log_bounds_emit_latency():
    """make_log never lets one slow emit stall the scan: bounded latency.

    RED: make_log today awaits the raw emit with no timeout, so a slow
    consumer serializes every downstream line and cleanup behind it. Post-fix
    each log call returns within EMIT_TIMEOUT_S even when emit hangs.
    """
    import asyncio
    import time

    from modules.shared import sms_async as sms

    timeout = getattr(sms, "EMIT_TIMEOUT_S", None)
    assert isinstance(timeout, (int, float)) and 0 < timeout < 5, (
        "expected EMIT_TIMEOUT_S bound, got %r" % (timeout,)
    )

    async def hanging_emit(team, message):
        await asyncio.sleep(30)

    log = sms.make_log(hanging_emit)
    started = time.monotonic()
    await log("system", "[phase cleanup] Session containers removed.")
    elapsed = time.monotonic() - started
    assert elapsed < timeout + 1.0, f"log call stalled: {elapsed:.2f}s"


def test_ui_feed_caps_bound_long_runs():
    """UI backpressure contract: every live feed list is DOM-capped.

    Additive only — this test pins the existing caps so Slice E's extra
    progress lines cannot overflow the feed on long runs. Fails if any feed
    grows unbounded.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    comms = (root / "web" / "js" / "ui" / "comms-feed.js").read_text(encoding="utf-8")
    activity = (root / "web" / "js" / "ui" / "activity.js").read_text(encoding="utf-8")
    console = (root / "web" / "js" / "pages" / "console.js").read_text(encoding="utf-8")
    assert "this.max" in comms and "while (this.root.children.length > this.max" in comms
    assert "this.max" in activity and "while (this.root.children.length > this.max" in activity
    assert "state.events.length > 2000" in console


async def test_new_progress_lines_keep_phase_shape(tmp_path, monkeypatch):
    """New progress lines reuse the exact ``[phase ...]`` tag shape.

    Guards the parser contract in tests/test_v3_live_console.py: every new
    line must start with ``[phase <name>]`` so rules.js stageOf keeps working.
    RED: no such lines exist yet.
    """
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    events: list[tuple[str, str]] = []

    async def emit(team, message):
        events.append((team, message))

    await run_fixture([0, 0, 0, 1, 0], emit=emit)
    new_lines = [
        m
        for _, m in events
        if ("batch " in m or "attempt" in m or "start" in m or "done" in m) and "[phase" in m
    ]
    assert new_lines, "expected new [phase ...] progress lines"

    for line in new_lines:
        assert re.match(r"\[phase [a-z ]+\]", line), f"bad phase shape: {line!r}"


async def test_new_lines_do_not_change_interpreter_counts():
    """Slice E lines through the REAL v3 interpreter: no double-count.

    Replays the live fixture stream (with all new [phase ...] progress and
    [phase verify] start/done lines) through node vm + Interpreter and pins
    the exact counts the base stream produces (findings=2 — the pre-existing
    red_proof chatter `exit 0` also keys EXIT_RE; patches=1; verified).
    A new line carrying an exit-shaped token would inflate findings/patches
    here. Fails closed on any parser drift.
    """
    import json
    import shutil
    import subprocess
    from pathlib import Path

    if shutil.which("node") is None:
        pytest.skip("node required")
    root = Path(__file__).resolve().parents[1]

    harness = r"""
const fs = require('fs'); const vm = require('vm'); const path = require('path');
const [root, files, lines] = [process.argv[1], JSON.parse(process.argv[2]), JSON.parse(process.argv[3])];
const noop = () => {};
const ctx2d = new Proxy({}, { get: (t, k) => (k in t ? t : (k === 'measureText' ? () => ({ width: 10 }) : (k === 'createRadialGradient' || k === 'createLinearGradient' ? () => ({ addColorStop: noop }) : noop))), set: (t, k, v) => { t[k] = v; return true; } });
const el = () => ({ getContext: () => ctx2d, addEventListener: noop, removeEventListener: noop, getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600 }), style: {}, width: 800, height: 600, setAttribute: noop, classList: { add: noop, remove: noop, toggle: noop } });
const ctx = { console, Math, Date, JSON, setTimeout: noop, clearTimeout: noop, setInterval: noop, clearInterval: noop, requestAnimationFrame: noop, cancelAnimationFrame: noop, devicePixelRatio: 1, performance: { now: () => 0 }, matchMedia: () => ({ matches: true, addEventListener: noop }), addEventListener: noop, removeEventListener: noop, ResizeObserver: class { observe() {} disconnect() {} }, document: { createElement: el, addEventListener: noop, body: { dataset: {} }, documentElement: { dataset: {} } }, location: { protocol: 'http:', host: 'localhost' }, localStorage: { getItem: () => null, setItem: noop }, sessionStorage: { getItem: () => null, setItem: noop } };
ctx.window = ctx; ctx.self = ctx; vm.createContext(ctx);
for (const f of files) vm.runInContext(fs.readFileSync(path.join(root, f), 'utf8'), ctx, { filename: f });
const out = vm.runInContext(`(() => {
  const g = new SMS.SpiderGraph(document.createElement('canvas'), { mode: 'console' });
  const it = new SMS.Interpreter(g);
  it.load(SMS.topology.profile('node_query_sink', {}));
  const beats = ${JSON.stringify(lines)}.map(([t, m]) => { const e = it.line(t, m); return e.beat || null; });
  it.result({ status: 'verified', pre_probe_exit: 0, post_probe_exit: 1 });
  return { findings: it.stats.findings, patches: it.stats.patches, verified: it.stats.verified, patched: !!it.patched };
})()`, ctx);
process.stdout.write(JSON.stringify(out));
"""

    async def collect():
        from modules.workflows.workflow import execute_purple_workflow

        events: list[list[str]] = []

        async def emit(team, message):
            events.append([team, message])

        result = await execute_purple_workflow(
            "node_query_sink",
            emit,
            config=CONFIG,
            sandbox_factory=lambda settings: FakeFixtureSandbox([0, 0, 0, 1, 0]),
            muse_factory=lambda settings: FakeFixtureMuse(),
        )
        assert result.status == "verified", result.message
        return events

    lines = await collect()
    assert any("[phase verify] start" in m for _, m in lines), "new brackets missing"
    assert any("[phase blue patch] attempt" in m for _, m in lines), "attempt line missing"

    manifest = json.loads((root / "web" / "tools" / "manifest.json").read_text())

    def expand(items):
        out = []
        for it in items:
            out += expand(manifest["groups"][it]) if it.startswith("@") else [it]
        return out

    scripts = [s for s in expand(["@core", "@model", "@engine", "@stream"])]
    res = subprocess.run(
        ["node", "-e", harness, str(root / "web"), json.dumps(scripts), json.dumps(lines)],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    out = json.loads(res.stdout)
    assert out == {"findings": 2, "patches": 1, "verified": 1, "patched": True}, out
