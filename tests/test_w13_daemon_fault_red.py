# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Daemon-death fail-closed pins (tribunal S3-6).

The Docker daemon can die mid-scan. Every pin here injects death at the SDK
boundary ONLY (Fake clients raising docker.errors.DockerException — a true
third-party boundary, so LAW 9C permits the doubles; the real daemon is never
touched and no user process is signaled).

Fail-closed contract: daemon death yields status error (never verified, never
a claimed verdict, never a hang); docker_status reports unavailable; stale
cleanup is best-effort and never raises.

Tests 1, 4, and 5 are RED-first gap tests (raw DockerException escaped before
the docker_manager.py daemon-death wrappers). Tests 2 and 3 pin behavior that
already held so regressions cannot reopen the gap.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from docker.errors import DockerException
from helpers import silent_emit
from test_sweep_passes import SweepFakeMuse

from modules.core.config import PurpleBoxConfig
from modules.core.docker_manager import (
    DockerSandboxManager,
    SandboxError,
    VerificationResult,
    docker_status,
    remove_stale_resources,
)

TEST_CONFIG = PurpleBoxConfig(meta_api_key="test-key")


def test_pre_probe_daemon_death_raises_sandbox_error():
    """Daemon death on containers.create during the pre-probe → SandboxError.

    RED-first gap test: raw DockerException escaped run_isolated_verifier
    before the docker_manager.py daemon-death wrapper. Must raise (never hang,
    never return a verdict).
    """
    client = MagicMock()
    client.containers.create.side_effect = DockerException("daemon socket gone")
    manager = DockerSandboxManager(TEST_CONFIG, client=client)
    with pytest.raises(SandboxError, match="daemon"):
        manager.run_isolated_verifier(MagicMock(), "import sys\nsys.exit(0)")


class _MidSweepDeathSandbox:
    """Baseline/pre/regression succeed; the daemon dies on the post-patch probe."""

    def __init__(self):
        self.probe_calls = 0
        self.closed = False

    def require_base_images(self):
        return None

    def create_isolated_network(self):
        return "test-network"

    def start_cloneable_target(self, *args):
        return "container", "snapshot"

    def replace_target(self, *args):
        return "patched-container", "patched-snapshot"

    def run_isolated_verifier(self, network, script):
        self.probe_calls += 1
        if self.probe_calls <= 3:
            return VerificationResult(0, "test evidence")
        raise DockerException("daemon died mid-sweep")

    def close(self):
        self.closed = True


async def test_mid_sweep_daemon_death_fails_closed_without_receipt():
    """Daemon death on the post-patch verifier → error, never verified.

    Fail-closed mapping note: an infrastructure fault yields status "error",
    not "failed" — "failed" would claim a probe verdict that no completed
    probe supports. The load-bearing pins are verified False and no receipt.
    """
    from modules.workflows.sweep import execute_sweep_scan

    sandbox = _MidSweepDeathSandbox()
    muse = SweepFakeMuse()
    result = await asyncio.wait_for(
        execute_sweep_scan(
            "node_query_sink",
            silent_emit,
            config=TEST_CONFIG,
            sandbox_factory=lambda settings: sandbox,
            muse_factory=lambda settings: muse,
            max_passes=1,
        ),
        timeout=60,
    )
    assert result.status == "error"
    assert "Docker" in result.message
    assert result.verified is False
    assert result.success is False
    assert [passed.receipt for passed in result.pass_results] == [None]
    assert result.pass_results[0].post_exit_code is None
    assert sandbox.probe_calls == 4
    assert muse.blue_calls == 1
    assert sandbox.closed is True


def test_docker_status_dead_client_reports_unavailable_never_raises():
    """docker_status with a dead daemon reports unavailable instead of raising."""
    ping_dead = MagicMock()
    ping_dead.ping.side_effect = DockerException("daemon socket gone")
    report = docker_status(TEST_CONFIG, client=ping_dead)
    assert report["state"] == "unavailable"
    assert report["missing_images"] == []
    assert report["leftover_containers"] == 0

    list_dead = MagicMock()
    list_dead.containers.list.side_effect = DockerException("daemon died mid-list")
    report = docker_status(TEST_CONFIG, client=list_dead)
    assert report["state"] == "unavailable"
    assert report["missing_images"] == []
    assert report["leftover_containers"] == 0


def test_stale_cleanup_best_effort_after_daemon_death():
    """remove_stale_resources with a dead daemon returns zeros, never raises.

    RED-first gap test: the daemon-death DockerException escaped before the
    best-effort wrapper, so post-fault crash recovery crashed instead of
    sweeping what it could.
    """
    client = MagicMock()
    client.containers.list.side_effect = DockerException("daemon socket gone")
    removed = remove_stale_resources(TEST_CONFIG, client=client)
    assert removed == {"containers": 0, "networks": 0, "snapshots": 0}


def test_stale_cleanup_returns_partial_counts_when_later_scope_dies():
    """Containers already reaped stay counted when the daemon dies mid-sweep."""
    client = MagicMock()
    container = MagicMock()
    client.containers.list.return_value = [container]
    client.networks.list.side_effect = DockerException("daemon died mid-sweep")
    removed = remove_stale_resources(TEST_CONFIG, client=client)
    assert removed == {"containers": 1, "networks": 0, "snapshots": 0}
    container.remove.assert_called_once_with(force=True)
