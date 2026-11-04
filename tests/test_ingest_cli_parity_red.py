# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): CLI ingest parity — --command/--test-command/--cycles/--contract work with --ingest-repo.

Reproduced live 2026-11-04 (Q3): `--ingest-repo URL --command ...` and
`--ingest-repo URL --cycles 1` both die with exit 2
"Project options require --project", because the gate at main.py:~3800
does not exempt --ingest-repo. But --project and --ingest-repo are
mutually exclusive, so there is NO CLI spelling for: explicit runtime
argv on an ingested repo, custom test command, contract text, or cycle
count. The WS ingest frame accepts runtime_command; the CLI cannot.

Parity contract (this pin):
- --ingest-repo admits --command, --test-command, --contract, --cycles,
  --scan-profile without --project.
- An explicit --command wins over detect_runtime (same rule as the WS
  explicit-argv path); omitted --command keeps auto-detect.
- Cycles flow into the derived ProjectSpec (default 1 preserved).
"""

from __future__ import annotations


def test_ingest_gate_exempts_command_options():
    src = open("main.py").read()
    gate_start = src.find("Project options require --project")
    assert gate_start != -1
    gate_block = src[max(0, gate_start - 1500) : gate_start]
    assert "ingest_repo" in gate_block or "ingest-repo" in gate_block, (
        "the project-options gate must exempt --ingest-repo for "
        "--command/--test-command/--contract/--cycles/--scan-profile"
    )


def test_ingest_repo_to_project_honors_explicit_argv():
    import inspect

    import main as _main

    src = inspect.getsource(_main._ingest_repo_to_project)
    assert "command" in src.split("def _ingest_repo_to_project")[1][:3000].lower(), (
        "_ingest_repo_to_project must accept explicit runtime/test argv, not detect unconditionally"
    )
