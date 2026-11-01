# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED lane: repo-intake URL reaches `sh -c` unquoted (validator hole + shell sink).

VERIFIED FINDING under test: ``library/services/repo_intake.py:362``
interpolates ``spec.url`` unquoted into an ``sh -c`` string, while
``RepoIntakeSpec.__post_init__`` (lines 56-66) rejects spaces but passes
``$(...)``, backticks, ``;``, ``&&``, ``|``. Reachable via the WS project
socket (``ingest_repo``/``commit_hash`` frame keys) and ``--ingest-repo`` CLI.

LAW 9 RED-first: both tests FAIL on unmodified code for the FUNCTIONAL
reason (hostile URL passes validation / reaches the shell command), and
both PASS post-fix under EITHER fix shape:
  (A) validator rejects shell metacharacters, OR
  (B) clone uses an argv-list exec with no ``sh -c`` string.

SAFETY: no shell ever runs here. The hostile URL is an inert canary
(``$(id)`` as a literal substring, never executed); the sandbox is
a recording double, and ``exec_run`` output is a canned dict. No network,
no Docker, no subprocess.
"""

from __future__ import annotations

import pytest

from library.services.repo_intake import RepoIntakeSpec, intake_repo_to_snapshot

# Inert canary: passes today's validator (https scheme, hostname "x",
# no spaces) but carries command-substitution metacharacters.
HOSTILE_URL = "https://x/a$(id).git"
HOSTILE_MARKER = "$(id)"
PINNED_COMMIT = "a" * 40


def test_1_validator_rejects_shell_metachars_red():
    """RED-1 (validation hole): hostile URL must not survive the boundary.

    FAILS today: ``RepoIntakeSpec`` constructs without raising, proving the
    validator passes ``$(...)`` through. PASSES post-fix under EITHER shape:
    (A) constructor raises ValueError, or (B) construction succeeds but the
    clone path below proves shell-free (the sink half carries it — see
    test_2). This test pins the (A) half directly and defers to (B) so a
    defense-in-depth argv-list fix also greens it.
    """
    try:
        spec = RepoIntakeSpec(url=HOSTILE_URL, commit_hash=PINNED_COMMIT)
    except ValueError:
        return  # PASS post-fix via (A): validator closed at the boundary.
    # Validator still passes: only green if the sink is shell-free (fix B).
    stage = _RecordingStage()
    with pytest.raises(ValueError, match="staging clone failed"):
        intake_repo_to_snapshot(
            spec,
            runtime_command=["python3", "main.py"],
            sandbox=_RecordingSandbox(stage),
            clone=True,
        )
    clone_cmd = stage.commands[1]
    shell_string = clone_cmd[2] if len(clone_cmd) > 2 else ""
    assert not (clone_cmd[:2] == ["sh", "-c"] and HOSTILE_MARKER in shell_string), (
        "RED PROOF: validator passed $(...) AND it reached sh -c: %r" % (clone_cmd,)
    )


class _RecordingStage:
    """Stage-container double: records exec_run argv, never executes."""

    def __init__(self):
        self.commands = []

    def exec_run(self, cmd, timeout=None):
        self.commands.append(list(cmd))
        return {"exit_code": 1, "output": b""}

    def get_archive(self, path):
        raise AssertionError("must not reach get_archive on failed clone")

    def remove(self, force=False):
        pass


class _RecordingContainers:
    def __init__(self, stage):
        self._stage = stage

    def create(self, *args, **kwargs):
        return self._stage


class _RecordingClient:
    def __init__(self, stage):
        self.containers = _RecordingContainers(stage)


class _RecordingSandbox:
    """DockerSandboxManager double: real unit under test runs unmocked."""

    def __init__(self, stage):
        self.client = _RecordingClient(stage)

    def _options(self, _kind):
        return {}


def test_2_clone_command_has_no_shell_interpolation_red():
    """RED-2 (shell sink): hostile URL must not reach `sh -c` unquoted.

    Runs the REAL ``intake_repo_to_snapshot`` / ``_clone_in_staging``
    (validator + command construction unmocked) against a recording
    sandbox double. FAILS today: captured clone command is
    ``["sh", "-c", "rm -rf ... git clone --depth 1 https://x/a$(id).git ..."]``
    with the raw metacharacters inside the shell string. PASSES post-fix
    if validation rejects (early return, fix A) or if the clone path uses
    an argv-list exec without ``sh -c`` (fix B).
    """
    try:
        spec = RepoIntakeSpec(url=HOSTILE_URL, commit_hash=PINNED_COMMIT)
    except ValueError:
        return  # PASS post-fix via (A): validator closed, shell unreachable.
    stage = _RecordingStage()
    with pytest.raises(ValueError, match="staging clone failed"):
        intake_repo_to_snapshot(
            spec,
            runtime_command=["python3", "main.py"],
            sandbox=_RecordingSandbox(stage),
            clone=True,
        )
    assert len(stage.commands) == 2, f"expected git-check + clone execs, got: {stage.commands}"
    clone_cmd = stage.commands[1]
    shell_string = clone_cmd[2] if len(clone_cmd) > 2 else ""
    assert not (clone_cmd[:2] == ["sh", "-c"] and HOSTILE_MARKER in shell_string), (
        "RED PROOF: hostile URL interpolated unquoted into sh -c: %r" % (clone_cmd,)
    )
