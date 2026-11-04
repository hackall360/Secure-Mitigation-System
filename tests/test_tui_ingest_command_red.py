# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): TUI ingest parity — --ingest-command threads explicit argv.

TUI project mode has --project-command/--project-test-command; TUI ingest
mode has --ingest-repo/--commit-hash but NO argv spelling. The backend
_ingest_repo_to_project now accepts runtime_command (Q3/Q7), the TUI
never passes it — a repo needing explicit argv dead-ends in TUI while
CLI/MCP/WS all have a spelling.

Parity contract: --ingest-command (JSON argv, optional) parses like
--project-command and forwards as runtime_command to
_ingest_repo_to_project. Omitted keeps auto-detect.
"""

from __future__ import annotations


def test_tui_ingest_command_parses_and_forwards():
    import argparse
    import json

    import tui as _tui

    parser = argparse.ArgumentParser()
    _tui._add_dispatch_flags(parser)
    args = parser.parse_args(
        ["--ingest-repo", "https://github.com/a/b.git", "--ingest-command", '["node", "server.js"]']
    )
    assert json.loads(args.ingest_command) == ["node", "server.js"]
    src = open("tui.py").read()
    idx = src.find("await main_mod._ingest_repo_to_project(")
    assert idx != -1
    assert "runtime_command" in src[idx : idx + 600], "TUI ingest run must forward runtime_command"
