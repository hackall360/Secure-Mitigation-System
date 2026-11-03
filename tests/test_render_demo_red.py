# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED-first contract for video-demo/render_demo.sh (rubric P2-4).

The full script provisions servers/sinks/capture, so tests MUST NEVER run it:
only `bash -n` (syntax) and `--check` (input verification + phase plan,
starts NOTHING) are exercised. Red phase: every test fails with
FileNotFoundError / assertion while the script is absent.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "video-demo" / "render_demo.sh"

PHASES = [
    "Phase 1/6",
    "Phase 2/6",
    "Phase 3/6",
    "Phase 4/6",
    "Phase 5/6",
    "Phase 6/6",
]


def _check(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=str(ROOT),
    )


def test_render_script_exists():
    assert SCRIPT.is_file(), f"missing provisioning script: {SCRIPT}"


def test_render_script_executable_bit():
    assert SCRIPT.is_file(), f"missing provisioning script: {SCRIPT}"
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "render_demo.sh must carry the executable bit"


def test_render_script_bash_syntax_clean():
    assert SCRIPT.is_file(), f"missing provisioning script: {SCRIPT}"
    proc = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"bash -n failed: {proc.stderr}"


def test_render_check_names_all_six_phases():
    assert SCRIPT.is_file(), f"missing provisioning script: {SCRIPT}"
    proc = _check("--check")
    assert proc.returncode == 0, f"--check failed on the real tree: {proc.stderr}"
    for phase in PHASES:
        assert phase in proc.stdout, f"--check output missing {phase}"


def test_render_check_missing_input_fails_actionable():
    assert SCRIPT.is_file(), f"missing provisioning script: {SCRIPT}"
    proc = _check("--check", env_extra={"STEM_SRC_DIR": "/nonexistent-stems-dir-xyz"})
    assert proc.returncode != 0, "--check must fail on a doctored missing input"
    combined = proc.stdout + proc.stderr
    assert "STEM_SRC_DIR" in combined, "failure must name the missing override"
    assert "missing" in combined.lower(), "failure must carry an actionable message"
