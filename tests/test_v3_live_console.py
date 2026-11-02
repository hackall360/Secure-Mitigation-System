"""v3 live console: stageOf() against REAL backend wording + snapshot chip hydration (node vm)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node required")

HARNESS = r"""
const fs = require('fs'); const vm = require('vm');
const cases = JSON.parse(process.argv[2]);
const ctx = { console }; ctx.window = ctx; vm.createContext(ctx);
for (const f of process.argv[1].split(',')) vm.runInContext(fs.readFileSync(f, 'utf8'), ctx);
process.stdout.write(JSON.stringify({
  stages: ctx.SMS.palette.STAGES,
  out: cases.map(([team, text, cur]) => ctx.SMS.rules.stageOf(team, text, cur)),
}));
"""

# (team, verbatim backend line with f-string values filled, current stage index, expected)
CASES = [
    # library/workflows/workflow.py:358
    (
        "system",
        "[phase baseline] Creating an internal Docker network and immutable target snapshot.",
        0,
        "sandbox",
    ),
    # library/workflows/binary_sweep.py:126
    (
        "system",
        "[phase baseline] Creating an internal Docker network and immutable binary snapshot.",
        0,
        "sandbox",
    ),
    # library/workflows/workflow.py:373
    (
        "system",
        "[phase baseline] Original fixture is ready; normal-input checks passed.",
        0,
        "baseline",
    ),
    # library/workflows/project_workflow.py:1358
    (
        "system",
        "[phase baseline] Running original-project baseline checks in isolated containers.",
        0,
        "baseline",
    ),
    # library/workflows/binary_sweep.py:163
    ("system", "[phase baseline] Binary harness is ready; baseline checks passed.", 0, "baseline"),
    # library/workflows/workflow.py:378
    ("red", "[phase red probe] Analyzing app.js with muse-red.", 1, "analysis"),
    # library/workflows/project_workflow.py:1388
    (
        "red",
        "[phase red review] Cycle 1/2, pass 1/1: reviewing the cumulative verified snapshot.",
        1,
        "analysis",
    ),
    # library/workflows/binary_sweep.py:150
    (
        "system",
        "[phase profile] Static reversing profile collected in-sandbox (format=elf, signals=3, profile 10->5 tokens).",
        1,
        "analysis",
    ),
    # library/workflows/workflow.py:430
    ("red", "[phase red probe] Boundary check exited 0.", 2, "probe"),
    # library/workflows/sweep.py:406
    ("red", "[sweep sqli] Boundary check exited 0.", 2, "probe"),
    # library/workflows/project_workflow.py:1458
    (
        "red",
        "[phase verify] Cycle 1/2 pass 1/1: proving the finding before requesting changes.",
        2,
        "probe",
    ),
    # library/workflows/workflow.py:451
    ("blue", "[phase blue patch] Requesting a sanitization patch from muse-blue.", 3, "patch"),
    # library/workflows/sweep.py:453
    ("blue", "[sweep sqli] Requesting a sanitization patch from muse-blue.", 3, "patch"),
    # library/workflows/project_workflow.py:1548
    (
        "blue",
        "[phase blue patch] Cycle 1/2 pass 1/1: requesting bounded sanitation-only replacements.",
        3,
        "patch",
    ),
    # library/workflows/workflow.py:471
    (
        "blue",
        "[phase blue patch] Starting a fresh target from the patched snapshot.",
        4,
        "regression",
    ),
    # library/workflows/workflow.py:497
    ("blue", "[phase verify] Post-patch boundary check exited 1.", 4, "regression"),
    # library/workflows/sweep.py:524
    ("blue", "[sweep sqli] Post-patch boundary check exited 1.", 4, "regression"),
    # library/workflows/project_workflow.py:1607
    (
        "system",
        "[phase verify] Cycle 1/2 pass 1/1: verifying a fresh target with the original probe and regression command.",
        4,
        "regression",
    ),
    # library/workflows/project_workflow.py:1844
    (
        "system",
        "[phase cleanup] Removing project session containers, snapshots, and network.",
        5,
        "cleanup",
    ),
    # library/workflows/workflow.py:604
    ("system", "[phase cleanup] Session containers, snapshots, and network removed.", 5, "cleanup"),
]


def test_stage_of_real_backend_phrases():
    files = ",".join(str(ROOT / p) for p in ("web/js/core/palette.js", "web/js/stream/rules.js"))
    cases = [[t, m, c] for t, m, c, _ in CASES]
    res = json.loads(
        subprocess.run(
            ["node", "-e", HARNESS, files, json.dumps(cases)],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        ).stdout
    )
    got = {m: s for (_, m, _, _), s in zip(CASES, res["out"], strict=True)}
    want = {m: e for _, m, _, e in CASES}
    assert got == want
    assert all(s in res["stages"] for s in res["out"])


def test_console_has_snapshot_chip_handler():
    src = (ROOT / "web/js/pages/console.js").read_text()
    assert "onSnapshot" in src
    seg = src[src.index("function onSnapshot") :]
    seg = seg[: seg.index("\n  }\n")]
    for needle in ("chips", "chip-server", "chip-docker", "chip-key", "images_missing", "busy"):
        assert needle in seg
    assert "onLine(" not in seg  # snapshot never emits a stream line
