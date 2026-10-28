# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""One baseline -> probe -> patch -> regression workflow for both entry points."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

from docker.errors import DockerException
from pydantic import BaseModel, Field

from agents import AgentError, BlueTeamPatch, MetaMuseClient, RedTeamFinding
from checks import normal_behavior_script
from config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key
from docker_manager import DockerSandboxManager, SandboxError
from patches import PatchRejected, validate_patch
from pricing import ScanUsage
from registry import TARGETS_REGISTRY

Emit = Callable[[str, str], Awaitable[None]]


class ScanResult(BaseModel):
    target: str
    status: Literal["verified", "not_confirmed", "rejected", "failed", "error"] = "error"
    message: str = "Scan did not complete."
    finding: RedTeamFinding | None = None
    patch: BlueTeamPatch | None = None
    diff: str = ""
    pre_exit_code: int | None = None
    post_exit_code: int | None = None
    baseline_passed: bool = False
    regression_passed: bool = False
    cleanup_ok: bool = True
    traces: dict[str, str] = Field(default_factory=dict)
    usage: ScanUsage = Field(default_factory=ScanUsage)
    total_tokens: int = 0
    cost_usd: float | None = None

    @property
    def success(self) -> bool:
        return self.status == "verified" and self.cleanup_ok


async def blocking(function, *args, **kwargs):
    """Join in-flight Docker operations before propagating cancellation to cleanup."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        except Exception:
            pass
        raise


async def execute_purple_workflow(
    target_key: str,
    emit: Emit,
    *,
    config: PurpleBoxConfig | None = None,
    sandbox_factory=DockerSandboxManager,
    muse_factory=MetaMuseClient,
) -> ScanResult:
    result = ScanResult(target=target_key)
    sandbox = None
    muse = None

    async def log(team: str, message: str) -> None:
        # Logging/closed UI sockets must never prevent resource cleanup.
        try:
            await emit(team, message)
        except Exception:
            pass

    try:
        if target_key not in TARGETS_REGISTRY:
            raise ValueError("Unknown fixture. Choose one of the registered targets.")
        settings = config or load_config()
        require_api_key(settings)
        target = TARGETS_REGISTRY[target_key]
        source = target.read_source()
        muse = muse_factory(settings)
        sandbox = await blocking(sandbox_factory, settings)
        await blocking(sandbox.require_base_images)
        await log("system", "Creating an internal Docker network and immutable target snapshot.")
        network = await blocking(sandbox.create_isolated_network)
        container, snapshot = await blocking(
            sandbox.start_cloneable_target, network, target, source
        )
        baseline = await blocking(
            sandbox.run_isolated_verifier, network, normal_behavior_script(target_key)
        )
        result.traces["baseline"] = baseline.output
        if baseline.exit_code != 0:
            raise SandboxError("Original fixture failed its trusted normal-input checks.")
        result.baseline_passed = True
        await log("system", "Original fixture is ready; normal-input checks passed.")

        await log("red", f"Analyzing {target.filename} with {settings.red_team_model}.")
        finding = await muse.run_red_team_analysis(target.filename, source, target.contract)
        result.finding = finding
        await log(
            "red",
            f"{finding.vulnerability_class} at {finding.sink_location}: {finding.analysis_summary}",
        )
        pre = await blocking(
            sandbox.run_isolated_verifier, network, finding.verification_script_python
        )
        result.pre_exit_code = pre.exit_code
        result.traces["before"] = pre.output
        await log("red", f"Boundary check exited {pre.exit_code}. {pre.output}")
        if pre.inconclusive:
            raise SandboxError("Pre-patch verifier was inconclusive; no patch was requested.")
        if pre.exit_code == 1:
            result.status = "not_confirmed"
            result.message = (
                "The probe did not confirm the reported boundary. No patch was requested."
            )
        else:
            await log("blue", f"Requesting a sanitization patch from {settings.blue_team_model}.")
            patch = await muse.run_blue_team_sanitizer(
                target.filename,
                source,
                finding,
                pre.output,
                target.contract,
            )
            result.patch = patch
            result.diff = validate_patch(target, source, patch.patched_file_content)
            await log("blue", patch.sanitization_strategy)
            await log("blue", result.diff)
            await log("system", "Starting a fresh target from the patched snapshot.")
            container, _ = await blocking(
                sandbox.replace_target,
                container,
                snapshot,
                network,
                target,
                patch.patched_file_content,
            )
            regression = await blocking(
                sandbox.run_isolated_verifier, network, normal_behavior_script(target_key)
            )
            result.traces["regression"] = regression.output
            if regression.exit_code != 0:
                raise PatchRejected(
                    "Patched fixture failed trusted normal-input regression checks."
                )
            result.regression_passed = True
            post = await blocking(
                sandbox.run_isolated_verifier, network, finding.verification_script_python
            )
            result.post_exit_code = post.exit_code
            result.traces["after"] = post.output
            await log("blue", f"Post-patch boundary check exited {post.exit_code}. {post.output}")
            if post.inconclusive:
                raise SandboxError(
                    "Post-patch verifier was inconclusive; this is not a successful fix."
                )
            # A probe must not earn success by leaving the application broken afterward.
            final_health = await blocking(
                sandbox.run_isolated_verifier, network, normal_behavior_script(target_key)
            )
            result.traces["after_probe_regression"] = final_health.output
            if final_health.exit_code != 0:
                result.regression_passed = False
                raise PatchRejected("Target failed normal-input checks after the boundary probe.")
            result.status = "verified" if post.exit_code == 1 else "failed"
            result.message = (
                "Boundary probe blocked and trusted normal-input checks passed. Review the candidate diff."
                if result.status == "verified"
                else "The original boundary probe still reaches the sink."
            )
    except PatchRejected as exc:
        result.status, result.message = "rejected", str(exc)
    except (ConfigurationError, AgentError, SandboxError, ValueError) as exc:
        result.status, result.message = "error", str(exc)
    except DockerException:
        result.status, result.message = (
            "error",
            "Docker operation failed. Check the daemon and base images.",
        )
    except Exception as exc:
        result.status, result.message = (
            "error",
            f"Workflow failed ({type(exc).__name__}); no verified patch produced.",
        )
    finally:
        # Cleanup precedes any final emission and also runs during cancellation.
        try:
            if sandbox is not None:
                try:
                    await blocking(sandbox.close)
                except Exception as exc:
                    result.cleanup_ok = False
                    result.status = "error"
                    result.message = (
                        str(exc)
                        if isinstance(exc, SandboxError)
                        else "Docker cleanup failed; inspect session resources."
                    )
        finally:
            if muse is not None:
                calls = getattr(muse, "usage", None)
                if isinstance(calls, list):
                    result.usage = ScanUsage(calls=calls)
                    result.total_tokens = result.usage.total_tokens
                    result.cost_usd = result.usage.cost_usd
                try:
                    await muse.aclose()
                except Exception:
                    pass
    await log("system", result.message)
    if sandbox is not None and result.cleanup_ok:
        await log("system", "Session containers, snapshots, and network removed.")
    return result
