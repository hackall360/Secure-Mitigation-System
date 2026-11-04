# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: coverage pass must be reachable through every live path (overnight).

The engine runs 5 passes (sweep.py SWEEP_PASSES + min(5,...)). Pin: every
live clamp admits 5 — the coverage pass is live on all five surfaces
(WebUI/CLI/TUI/MCP/library), not unit-only.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ws_sweep_gate_admits_five():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '"5"' in src and "sweep_raw" in src, "WS sweep gate must admit pass 5"


def test_no_min4_clamps_remain_on_source_paths():
    bad: list[str] = []
    # Binary paths (binary_sweep.py, binary runners) intentionally cap at
    # 3/4: chain is refused fail-closed there, so coverage is unreachable.
    for rel in ("library/services/sms_api.py", "tui.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        for i, line in enumerate(src.splitlines(), 1):
            if re.search(r"min\(\s*4\s*,", line) and "max_passes" in line:
                bad.append(f"{rel}:{i}: {line.strip()}")
    # main.py source runners must admit 5; the binary_sweep_runner keeps 4.
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        if re.search(r"min\(\s*4\s*,", line) and "max_passes" in line:
            context = "\n".join(src.splitlines()[max(0, i - 12) : i])
            if (
                "binary_sweep" not in context
                and "binary" not in context.lower().split("max_passes")[0][-200:]
            ):
                bad.append(f"main.py:{i}: {line.strip()}")
    assert not bad, f"max_passes clamps still cap at 4: {bad}"


def test_sweep_passes_is_five_tuple():
    from library.workflows.sweep import SWEEP_PASSES

    assert tuple(SWEEP_PASSES) == ("standard", "deep", "threat_actor", "chain", "coverage")


def test_mcp_schema_admits_five():
    from library.services.mcp_bridge import sms_scan_source_tool_definition

    tool = sms_scan_source_tool_definition()
    assert tool["inputSchema"]["properties"]["max_passes"]["maximum"] == 5
    # Binary sweep keeps maximum 3: the chain pass (4) is refused
    # fail-closed there, so coverage (5) is unreachable on binaries.


def test_webui_schema_admits_five():
    src = (ROOT / "web/js/options/schema.js").read_text(encoding="utf-8")
    assert "max: 5" in src and "coverage pass" in src
