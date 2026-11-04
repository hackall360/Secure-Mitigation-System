# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): ingest runtime-path contract — three paths, pinned behavior.

Three ingest paths choose wrapper-vs-raw differently TODAY:
- WS /ws/project: no-argv frame -> build_service_wrapper (serve 8080 +
  --smoke regression); explicit runtime_command -> raw straight-through.
- library scan_repo: ALWAYS wraps (serve + smoke from wrapper manifest).
- CLI/TUI _ingest_repo_to_project: raw detect (or explicit argv), NO
  wrapper — the regression runs the real entrypoint (long-lived apps
  fail the baseline; AnyCam needed the wrapper to pass).

This is intentional divergence (separate-project surface vs operator
console), but NOTHING pins it: a future edit could silently wrap or
unwrap one path and change live verdicts. Pin the contract:

- scan_repo MUST route through build_service_wrapper (idempotent skip
  when repo.smoke_command present) and MUST use smoke argv as the
  regression command (terminating), never the serve argv.
- _ingest_repo_to_project MUST honor explicit runtime_command over
  detect (Q3) and MUST flow cycles/contract (Q3).
"""

from __future__ import annotations


def test_scan_repo_wraps_and_uses_smoke_regression():
    src = open("library/services/sms_api.py").read()
    assert "build_service_wrapper" in src, "scan_repo must wrap the staged tree"
    assert "smoke_argv" in src and "regression_argv" in src
    assert '"test_command": regression_argv' in src, (
        "scan_repo regression must be the terminating smoke argv"
    )


def test_cli_ingest_honors_explicit_over_detect():
    import inspect

    import main as _main

    src = inspect.getsource(_main._ingest_repo_to_project)
    assert "runtime_command is not None" in src
    assert "cycles" in src and "contract_text" in src
