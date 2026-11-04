# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): OOM diagnostics — a SIGKILL must name the killer.

Found live 2026-11-04 (Part 2 dry run): a warmed-up baseline container
died with exit 137 (OOMKilled) at ~20 s under the 256m limit. The server
reported only "Project check failed before producing a result" — no hint
that memory was the killer, sending the debug down a Docker-daemon rabbit
hole first.

Fix contract: the wait/timeout path in run_project_check inspects the dead
container state (OOMKilled / ExitCode 137) and names it: memory limit,
current setting, and the PURPLEBOX_CONTAINER_MEM_LIMIT knob. A SIGKILL
must never masquerade as a generic check failure.

This pin asserts the OOM branch exists and mentions the knob — at the
source level (no Docker needed): the SandboxError text for an OOMKilled
container must name the memory limit.
"""

from __future__ import annotations


def _run_project_check_src() -> str:
    import inspect

    import library.core.docker_manager as dm

    return inspect.getsource(dm.DockerSandboxManager.run_project_check)


def test_oom_names_the_memory_limit():
    src = _run_project_check_src()
    assert "OOMKilled" in src, (
        "run_project_check must inspect OOMKilled on dead containers — "
        "exit 137 masquerading as a generic failure cost a dry-run night"
    )


def test_oom_error_points_at_the_knob():
    src = _run_project_check_src()
    assert "PURPLEBOX_CONTAINER_MEM_LIMIT" in src
    assert "container_mem_limit" in src


def test_wait_timeout_means_still_running():
    src = _run_project_check_src()
    assert "STILL-" in src or "still-" in src.lower(), (
        "wait() timeout on a live container must report timed_out, not "
        "SandboxError — a long-running service is alive, not failed"
    )
