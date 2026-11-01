# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Audit-M drift pins: four small surface-drift fixes (kitten 2, 7b, 9, 3-note).

LAW 4: no test may print or assert on probe scripts, payloads, or keys.
LAW 9 RED-first: each test FAILS pre-fix, green post-fix.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI_MD = ROOT / "docs" / "reference" / "CLI.md"


def test_mcp_tool_count_matches_docs():
    """(a) All 6 MCP_TOOLS names appear in CLI.md."""
    from library.services.mcp_bridge import MCP_TOOLS

    names = [tool["name"] for tool in MCP_TOOLS]
    assert len(names) == 6, names
    doc = CLI_MD.read_text()
    for name in names:
        assert name in doc, name


def test_snippet_flag_both_spellings_documented():
    """(b) CLI --mcp-snippet and TUI --snippet are both documented in CLI.md."""
    result = subprocess.run(
        [sys.executable, "main.py", "--help"], capture_output=True, text=True, cwd=ROOT
    )
    assert "--mcp-snippet" in result.stdout
    result = subprocess.run(
        [sys.executable, "tui.py", "--help"], capture_output=True, text=True, cwd=ROOT
    )
    assert "--snippet" in result.stdout
    doc = CLI_MD.read_text()
    bare = re.compile(r"(?<![\w-])--snippet(?![\w-])")
    lines = doc.splitlines()
    assert any("--mcp-snippet" in ln and bare.search(ln) for ln in lines), (
        "both spellings must share one CLI.md row"
    )


def test_health_error_path_carries_version():
    """(c) Error-path /api/health payload still carries version."""
    from fastapi.testclient import TestClient

    from library.core.config import PurpleBoxConfig
    from main import create_app

    bad = PurpleBoxConfig(red_team_model="not-a-model")
    with TestClient(create_app(bad), base_url="http://localhost") as client:
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json()["version"]  # one-line error-payload version


def test_tui_sweep_help_states_cap():
    """(d) TUI --sweep-passes help states the TUI max of 4 (truth-sweep F7)."""
    result = subprocess.run(
        [sys.executable, "tui.py", "--help"], capture_output=True, text=True, cwd=ROOT
    )
    assert "max 4" in result.stdout.lower(), result.stdout
