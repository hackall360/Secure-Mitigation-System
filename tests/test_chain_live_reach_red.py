# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: chain pass must be reachable through every live path (G2).

The engine runs 4 passes (sweep.py SWEEP_PASSES + min(4,...)), but six
entry points still clamp to 3, so the chain pass is unit-only. Pin: every
live clamp admits 4.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ws_sweep_gate_admits_four():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'sweep_raw in ("2", "3", "4")' in src or "sweep_raw in ('2', '3', '4')" in src


def test_no_min3_clamps_remain():
    bad: list[str] = []
    for rel in ("main.py", "modules/services/sms_api.py", "modules/workflows/binary_sweep.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        for i, line in enumerate(src.splitlines(), 1):
            if re.search(r"min\(\s*3\s*,", line) and "max_passes" in line:
                bad.append(f"{rel}:{i}: {line.strip()}")
    assert not bad, f"max_passes clamps still cap at 3: {bad}"


def test_binary_sweep_admits_four():
    src = (ROOT / "modules/workflows/binary_sweep.py").read_text(encoding="utf-8")
    assert "min(4," in src
