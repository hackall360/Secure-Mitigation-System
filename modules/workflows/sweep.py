# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Three-pass comprehensive security sweep: standard -> deep -> threat-actor.

Each pass runs the full evidence-gated loop (red finding -> Docker probe
exit 0/1/2 -> blue guarded patch -> regression -> re-probe) over the same
sandboxed target. The sweep never stops at the first finding: all selected
passes run, blue answers every confirmed pass, and only all-holding passes
earn verified. Inconclusive probes fail closed. Isolation (internal=True,
non-root, read-only roots) is untouched.
"""

from __future__ import annotations

from typing import Literal

from docker.errors import DockerException
from pydantic import BaseModel, ConfigDict, Field

from modules.core.agents import (
    AgentError,
    BlueTeamPatch,
    MetaMuseClient,
    RedTeamFinding,
)
from modules.core.checks import normal_behavior_script
from modules.core.config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key
from modules.core.docker_manager import DockerSandboxManager, SandboxError
from modules.core.patches import PatchRejected, validate_patch
from modules.core.pricing import ScanUsage
from modules.core.registry import TARGETS_REGISTRY
from modules.services.chatter import chatter
from modules.shared.sms_async import Emit, blocking, make_log
from modules.shared.sms_compress import CompressionReport, compress_context
from modules.shared.sms_redact import EXPLOIT_REDACTED, PROBE_OUTPUT_WITHHELD
from modules.workflows.workflow import build_verdict_receipt

SWEEP_PASSES: tuple[str, ...] = ("standard", "deep", "threat_actor")
SweepPassId = Literal["standard", "deep", "threat_actor"]

_PASS_LABEL: dict[str, str] = {
    "standard": "Standard sweep (common CVE patterns)",
    "deep": "Deep sweep (edge cases, input-mutation handling)",
    "threat_actor": "Threat-actor sweep (logic abuse + technical exploitation)",
}


class SweepPassResult(BaseModel):
    """One pass verdict: Docker exits decide, receipt records."""

    model_config = ConfigDict(extra="forbid", strict=True)

    pass_id: str
    finding: RedTeamFinding | None = None
    patch: BlueTeamPatch | None = None
    diff: str = ""
    pre_exit_code: int | None = None
    post_exit_code: int | None = None
    regression_passed: bool = False
    cleared: bool = False
    receipt: object | None = None

    @property
    def holds(self) -> bool:
        """A pass holds when it cleared outright or its patch blocked the probe."""
        return self.cleared or (
            self.receipt is not None and self.post_exit_code == 1 and self.regression_passed
        )


class SweepScanResult(BaseModel):
    """Aggregate sweep verdict over all selected passes."""

    model_config = ConfigDict(extra="forbid", strict=True)

    target: str
    status: Literal["verified", "not_confirmed", "rejected", "failed", "error"] = "error"
    message: str = "Sweep did not complete."
    pass_results: list[SweepPassResult] = Field(default_factory=list)
    cumulative_diff: str = ""
    baseline_passed: bool = False
    cleanup_ok: bool = True
    traces: dict[str, str] = Field(default_factory=dict)
    usage: ScanUsage = Field(default_factory=ScanUsage)
    total_tokens: int = 0
    cost_usd: float | None = None
    compression: CompressionReport = Field(default_factory=CompressionReport)
    vault_recall: str = ""
    vault_namespaces: list[str] = []

    @property
    def success(self) -> bool:
        return self.status == "verified" and self.cleanup_ok


async def execute_sweep_scan(
    target_key: str,
    emit: Emit,
    *,
    config: PurpleBoxConfig | None = None,
    sandbox_factory=DockerSandboxManager,
    muse_factory=MetaMuseClient,
    max_passes: int = 3,
) -> SweepScanResult:
    """Run the 3-pass sweep over one fixture target.

    Baseline once, then per selected pass: red pass analysis -> probe.
    Exit 1 clears the pass (no blue call). Exit 0 requests a blue patch
    against the CURRENT source (carrying prior passes' patches), then
    regression + re-probe + final health. Exit 2 fails the sweep closed.
    `max_passes` 1..3 selects a prefix of SWEEP_PASSES (CLI/deep-link).
    """
    result = SweepScanResult(target=target_key)
    sandbox = None
    muse = None
    log = make_log(emit)
    selected = [
        p for p in SWEEP_PASSES if 0 < SWEEP_PASSES.index(p) + 1 <= max(1, min(3, max_passes))
    ]

    try:
        if target_key not in TARGETS_REGISTRY:
            raise ValueError("Unknown fixture. Choose one of the registered targets.")
        if target_key == "binary_argv_echo":
            raise ValueError(
                "binary_argv_echo is a compiled ELF fixture: use the binary harness "
                "path (execute_binary_sweep), not the source sweep."
            )
        settings = config or load_config()
        require_api_key(settings)
        target = TARGETS_REGISTRY[target_key]
        source = target.read_source()
        current_source = source
        compressed = compress_context(source, filename=target.filename)
        result.compression = compressed
        await log(
            "system",
            f"[phase compress] Context {compressed.raw_tokens_estimated} -> "
            f"{compressed.compressed_tokens_sent} tokens "
            f"(saved {compressed.tokens_saved}, ratio {compressed.compression_ratio:.2f}).",
        )
        try:
            from modules.intel.sms_vault import query_vault

            vault_answer = query_vault(source)
            result.vault_recall = vault_answer.status
            result.vault_namespaces = vault_answer.namespaces
            await log(
                "system",
                f"[phase vault] {vault_answer.status} ({vault_answer.record_count} prior records).",
            )
        except Exception as exc:
            await log("system", f"[phase vault] Recall unavailable ({type(exc).__name__}).")
            result.vault_recall = "VAULT_UNAVAILABLE"
        muse = muse_factory(settings)
        sandbox = await blocking(sandbox_factory, settings)
        await blocking(sandbox.require_base_images)
        await log(
            "system",
            "[phase baseline] Creating an internal Docker network and immutable target snapshot.",
        )
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
        await log(
            "system",
            "[phase baseline] Original fixture is ready; normal-input checks passed.",
        )

        cumulative_diffs: list[str] = []
        for pass_id in selected:
            label = _PASS_LABEL[pass_id]
            passed = SweepPassResult(pass_id=pass_id)
            result.pass_results.append(passed)
            await log("red", f"[sweep {pass_id}] {label}.")
            finding = await muse.run_red_team_pass_analysis(
                pass_id, target.filename, current_source, target.contract
            )
            passed.finding = finding
            await log(
                "red",
                f"[sweep {pass_id}] {finding.vulnerability_class} at "
                f"{finding.sink_location}: {finding.analysis_summary}",
            )
            pre = await blocking(
                sandbox.run_isolated_verifier, network, finding.verification_script_python
            )
            passed.pre_exit_code = pre.exit_code
            result.traces[f"{pass_id}:before"] = pre.output
            await log(
                "red", f"[sweep {pass_id}] Boundary check exited {pre.exit_code}. {pre.output}"
            )
            await log(
                "red",
                chatter(
                    "red_proof",
                    persona="Breakwater",
                    path=target.filename,
                    code=pre.exit_code,
                    seed=hash(pass_id) % 1000,
                ),
            )
            if pre.inconclusive:
                raise SandboxError(
                    f"Sweep pass {pass_id} verifier was inconclusive; no patch was requested."
                )
            if pre.exit_code == 1:
                passed.cleared = True
                passed.regression_passed = True
                await log("red", f"[sweep {pass_id}] Probe blocked; pass is clear.")
                continue
            await log(
                "blue",
                f"[sweep {pass_id}] Requesting a sanitization patch from "
                f"{settings.blue_team_model}.",
            )
            patch = await muse.run_blue_team_sanitizer(
                target.filename, current_source, finding, pre.output, target.contract
            )
            passed.patch = patch
            passed.diff = validate_patch(target, current_source, patch.patched_file_content)
            cumulative_diffs.append(passed.diff)
            current_source = patch.patched_file_content
            await log("blue", patch.sanitization_strategy)
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
            result.traces[f"{pass_id}:regression"] = regression.output
            if regression.exit_code != 0:
                raise PatchRejected(
                    f"Sweep pass {pass_id} patched fixture failed trusted normal-input regression."
                )
            passed.regression_passed = True
            post = await blocking(
                sandbox.run_isolated_verifier, network, finding.verification_script_python
            )
            passed.post_exit_code = post.exit_code
            result.traces[f"{pass_id}:after"] = post.output
            await log(
                "blue",
                f"[sweep {pass_id}] Post-patch boundary check exited {post.exit_code}. "
                f"{post.output}",
            )
            if post.inconclusive:
                raise SandboxError(f"Sweep pass {pass_id} post-patch verifier was inconclusive.")
            final_health = await blocking(
                sandbox.run_isolated_verifier, network, normal_behavior_script(target_key)
            )
            result.traces[f"{pass_id}:after_probe_regression"] = final_health.output
            if final_health.exit_code != 0:
                passed.regression_passed = False
                raise PatchRejected(
                    f"Sweep pass {pass_id} target failed normal-input checks after the probe."
                )
            if post.exit_code != 1:
                result.status = "failed"
                result.message = (
                    f"Sweep pass {pass_id} probe still reaches the sink after patching."
                )
                break
            passed.receipt = build_verdict_receipt(
                fixture=target_key,
                pre_exit_code=pre.exit_code,
                post_exit_code=post.exit_code,
                regression_passed=passed.regression_passed,
                patch_content=patch.patched_file_content,
            )
        result.cumulative_diff = "\n".join(cumulative_diffs)
        if result.status != "failed":
            if all(p.holds for p in result.pass_results):
                result.status = "verified"
                result.message = (
                    "All sweep passes hold: every confirmed boundary is blocked and "
                    "trusted normal-input checks passed. Review the candidate diff."
                )
                try:
                    from modules.intel.sms_vault import VaultNamespace, commit_verified

                    for passed in result.pass_results:
                        if passed.finding is not None and passed.pre_exit_code == 0:
                            commit_verified(
                                namespace=VaultNamespace.RED,
                                source=source,
                                payload={
                                    "kind": "sweep_boundary",
                                    "fixture": target_key,
                                    "pass_id": passed.pass_id,
                                    "sink": passed.finding.sink_location,
                                },
                            )
                    if result.cumulative_diff:
                        commit_verified(
                            namespace=VaultNamespace.BLUE,
                            source=result.cumulative_diff,
                            payload={
                                "kind": "sweep_patch",
                                "fixture": target_key,
                                "passes": [p.pass_id for p in result.pass_results],
                            },
                        )
                    await log("system", "[phase vault] Sweep findings committed.")
                except Exception as exc:
                    await log("system", f"[phase vault] Commit skipped ({type(exc).__name__}).")
            else:
                result.status = "failed"
                result.message = "One or more sweep passes did not hold after patching."
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
            f"Sweep failed ({type(exc).__name__}); no verified patch produced.",
        )
    finally:
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
    await log("system", f"[done] {result.message}")
    if sandbox is not None and result.cleanup_ok:
        await log("system", "[phase cleanup] Session containers, snapshots, and network removed.")
    return result


def redact_sweep_result_for_user(result: SweepScanResult) -> dict:
    """User-safe sweep report: patches + exit codes only, no probe source or payloads."""
    data = result.model_dump()
    for passed in data.get("pass_results", []):
        finding = passed.get("finding")
        if isinstance(finding, dict):
            finding["verification_script_python"] = EXPLOIT_REDACTED
    for key, value in list(data.get("traces", {}).items()):
        if isinstance(value, str) and (":before" in key or ":after" in key):
            data["traces"][key] = PROBE_OUTPUT_WITHHELD
    return data
