# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import asyncio
import threading

import pytest
from test_patches import node_patch

from agents import BlueTeamPatch, RedTeamFinding
from config import PurpleBoxConfig
from docker_manager import SandboxError, VerificationResult
from registry import TARGETS_REGISTRY
from workflow import execute_purple_workflow


class FakeMuse:
    def __init__(self):
        self.blue_calls = 0
        self.closed = False

    async def run_red_team_analysis(self, *args):
        return RedTeamFinding(
            vulnerability_class="test boundary",
            sink_location="app.js",
            analysis_summary="Test-only injected agent.",
            verification_script_python="import sys\nsys.exit(0)",
        )

    async def run_blue_team_sanitizer(self, *args):
        self.blue_calls += 1
        return BlueTeamPatch(
            sanitization_strategy="Validate IDs",
            diff_summary="Add a guard",
            patched_file_content=node_patch(TARGETS_REGISTRY["node_query_sink"].read_source()),
        )

    async def aclose(self):
        self.closed = True


class FakeSandbox:
    def __init__(self, codes):
        self.codes = iter(codes)
        self.closed = False
        self.replaced = False

    def require_base_images(self):
        return None

    def create_isolated_network(self):
        return "test-network"

    def start_cloneable_target(self, *args):
        return "container", "snapshot"

    def replace_target(self, *args):
        self.replaced = True
        return "patched-container", "patched-snapshot"

    def run_isolated_verifier(self, *args):
        return VerificationResult(next(self.codes), "test evidence")

    def close(self):
        self.closed = True


async def silent_emit(team, message):
    return None


async def run(codes, emit=silent_emit, sandbox=None):
    sandbox = sandbox or FakeSandbox(codes)
    muse = FakeMuse()
    result = await execute_purple_workflow(
        "node_query_sink",
        emit,
        config=PurpleBoxConfig(meta_api_key="unit-test-key"),
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: muse,
    )
    assert sandbox.closed and muse.closed
    return result, sandbox, muse


async def test_complete_success_requires_both_checks():
    result, sandbox, muse = await run([0, 0, 0, 1, 0])
    assert result.success and result.baseline_passed and result.regression_passed
    assert result.pre_exit_code == 0 and result.post_exit_code == 1
    assert sandbox.replaced and muse.blue_calls == 1


@pytest.mark.parametrize(
    "codes,status,blue_calls",
    [
        ([0, 1], "not_confirmed", 0),
        ([0, 2], "error", 0),
        ([2], "error", 0),
        ([0, 0, 0, 0, 0], "failed", 1),
        ([0, 0, 0, 2], "error", 1),
        ([0, 0, 0, 137], "error", 1),
        ([0, 0, 2], "rejected", 1),
        ([0, 0, 0, 1, 2], "rejected", 1),
    ],
)
async def test_fail_closed_outcomes(codes, status, blue_calls):
    result, _, muse = await run(codes)
    assert not result.success and result.status == status
    assert muse.blue_calls == blue_calls


async def test_broken_emitter_cannot_skip_cleanup():
    async def disconnected(team, message):
        raise ConnectionError("UI closed")

    result, _, _ = await run([0, 0, 0, 1, 0], emit=disconnected)
    assert result.success


async def test_cleanup_error_prevents_success():
    sandbox = FakeSandbox([0, 0, 0, 1, 0])

    def fail_cleanup():
        sandbox.closed = True
        raise SandboxError("Cleanup failed")

    sandbox.close = fail_cleanup
    result, _, _ = await run([], sandbox=sandbox)
    assert not result.cleanup_ok and not result.success


async def test_cancellation_waits_for_in_flight_docker_then_cleans_up():
    started, release = threading.Event(), threading.Event()
    sandbox = FakeSandbox([])
    muse = FakeMuse()

    def create_network():
        started.set()
        assert release.wait(timeout=5)
        return "created-before-cleanup"

    sandbox.create_isolated_network = create_network
    task = asyncio.create_task(
        execute_purple_workflow(
            "node_query_sink",
            silent_emit,
            config=PurpleBoxConfig(meta_api_key="unit-test-key"),
            sandbox_factory=lambda settings: sandbox,
            muse_factory=lambda settings: muse,
        )
    )
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sandbox.closed and muse.closed


async def test_missing_key_fails_before_touching_docker():
    def forbidden(settings):
        raise AssertionError("Docker must not be opened")

    result = await execute_purple_workflow(
        "node_query_sink", silent_emit, config=PurpleBoxConfig(), sandbox_factory=forbidden
    )
    assert result.status == "error" and "META_MUSE_API_KEY" in result.message
