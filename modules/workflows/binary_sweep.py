# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Three-pass sweep for compiled binaries through the trusted harness.

Same rigorous loop as source sweeps: static reversing profile grounds the
red passes, each pass probes the harness-executed binary over the isolated
network (exit 0/1/2 oracle), blue answers with mitigation rules that the
harness enforces, and the probe re-runs through the mitigated harness.
Only all-holding passes earn verified. Binaries execute ONLY as subprocesses
of the trusted harness inside the air-gapped sandbox, never on the host.
"""

from __future__ import annotations

from docker.errors import DockerException

from modules.core.agents import (
    AgentError,
    BlueTeamPatch,
    MetaMuseClient,
)
from modules.core.config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key
from modules.core.docker_manager import DockerSandboxManager, SandboxError
from modules.core.patches import PatchRejected
from modules.core.pricing import ScanUsage
from modules.services.binary_intake import BinaryRejected, BinarySpec, validate_binary_blob
from modules.services.binary_telemetry import summarize_profile
from modules.services.chatter import chatter
from modules.shared.sms_async import Emit, blocking, make_log
from modules.shared.sms_compress import compress_context
from modules.shared.sms_redact import EXPLOIT_REDACTED, PROBE_OUTPUT_WITHHELD
from modules.workflows.sweep import SWEEP_PASSES, SweepPassResult, SweepScanResult
from modules.workflows.workflow import build_verdict_receipt

BINARY_BASELINE_SCRIPT = """import sys, urllib.request, urllib.parse
params = urllib.parse.urlencode({"argv": "", "stdin": "hello"})
try:
    with urllib.request.urlopen("http://target-service:8080/?" + params, timeout=5) as response:
        import json
        body = json.loads(response.read(65537).decode("utf-8"))
except Exception as exc:
    print("HARNESS BASELINE FAIL: " + type(exc).__name__)
    sys.exit(2)
if body.get("status") not in ("ok", "timeout", "exec_error"):
    print("HARNESS BASELINE FAIL: unexpected status " + str(body.get("status")))
    sys.exit(2)
print("Binary harness baseline passed: binary executed under the harness.")
sys.exit(0)
"""

_BLUE_MITIGATION_SUFFIX = (
    "\n\nYou are mitigating a COMPILED BINARY executed by a trusted harness, "
    "not patching source. Return exactly one JSON object with nonempty string "
    "fields sanitization_strategy, diff_summary, patched_file_content. The "
    "patched_file_content must be ONLY mitigation rule lines: one `reject:` "
    "prefix per line (matched against probe argv/stdin before the binary "
    "runs), nothing else, at most 8 KiB. Prefer exact dangerous-input "
    "prefixes with clean rejection over broad blocks."
)


def extract_mitigation_rules(patch: BlueTeamPatch) -> str:
    """Mitigation text from a blue patch: only `reject:` lines survive."""
    lines = [
        line.strip()
        for line in patch.patched_file_content.splitlines()
        if line.strip().startswith("reject:")
    ]
    if not lines:
        raise PatchRejected(
            "Binary mitigation has no reject: rules; only reject:-prefixed lines are accepted.",
            guard_id="binary_mitigation_empty",
        )
    text = "\n".join(lines) + "\n"
    if len(text.encode("utf-8")) > 8 * 1024:
        raise PatchRejected(
            "Binary mitigation exceeds the 8 KiB rule budget.",
            guard_id="binary_mitigation_budget",
        )
    return text


async def execute_binary_sweep(
    spec: BinarySpec,
    emit: Emit,
    *,
    config: PurpleBoxConfig | None = None,
    sandbox_factory=DockerSandboxManager,
    muse_factory=MetaMuseClient,
    max_passes: int = 3,
) -> SweepScanResult:
    """Run the 3-pass sweep over one validated binary spec."""
    result = SweepScanResult(target=f"binary:{spec.filename}")
    sandbox = None
    muse = None
    log = make_log(emit)
    selected = [
        p for p in SWEEP_PASSES if 0 < SWEEP_PASSES.index(p) + 1 <= max(1, min(4, max_passes))
    ]

    try:
        settings = config or load_config()
        require_api_key(settings)
        muse = muse_factory(settings)
        sandbox = await blocking(sandbox_factory, settings)
        await blocking(sandbox.require_base_images)
        await blocking(sandbox.require_binary_image)
        await log(
            "system",
            "[phase baseline] Creating an internal Docker network and immutable binary snapshot.",
        )
        network = await blocking(sandbox.create_isolated_network)
        profile = await blocking(sandbox.binary_static_profile, network, spec.blob)
        result.traces["profile"] = profile[:2000]
        summary = summarize_profile(profile)
        compressed_profile = compress_context(profile, filename=spec.filename)
        result.compression = compressed_profile
        try:
            from modules.intel.sms_vault import query_vault

            vault_answer = query_vault(profile)
            result.vault_recall = vault_answer.status
            result.vault_namespaces = vault_answer.namespaces
            await log(
                "system",
                f"[phase vault] {vault_answer.status} "
                f"({vault_answer.record_count} prior binary profiles).",
            )
        except Exception as exc:
            await log("system", f"[phase vault] Recall unavailable ({type(exc).__name__}).")
            result.vault_recall = "VAULT_UNAVAILABLE"
        await log(
            "system",
            f"[phase profile] Static reversing profile collected in-sandbox "
            f"(format={summary.get('format')}, signals={len(summary.get('signals', []))}, "
            f"profile {compressed_profile.raw_tokens_estimated}->"
            f"{compressed_profile.compressed_tokens_sent} tokens).",
        )
        container, snapshot = await blocking(sandbox.start_binary_harness, network, spec.blob)
        baseline = await blocking(sandbox.run_isolated_verifier, network, BINARY_BASELINE_SCRIPT)
        result.traces["baseline"] = baseline.output
        if baseline.exit_code != 0:
            raise SandboxError("Binary harness failed its trusted baseline checks.")
        result.baseline_passed = True
        await log(
            "system",
            "[phase baseline] Binary harness is ready; baseline checks passed.",
        )

        for pass_id in selected:
            passed = SweepPassResult(pass_id=pass_id)
            result.pass_results.append(passed)
            await log(
                "red", f"[sweep {pass_id}] Binary pass over {spec.filename} ({spec.binary_format})."
            )
            finding = await muse.run_red_team_pass_analysis(
                pass_id,
                spec.filename,
                f"STATIC PROFILE:\n{profile}\n\nCONTRACT:\n{spec.contract}",
                spec.contract,
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
                    path=spec.filename,
                    code=pre.exit_code,
                    seed=hash(pass_id) % 1000,
                ),
            )
            if pre.inconclusive:
                raise SandboxError(f"Binary sweep pass {pass_id} verifier was inconclusive.")
            if pre.exit_code == 1:
                passed.cleared = True
                passed.regression_passed = True
                await log("red", f"[sweep {pass_id}] Probe blocked; pass is clear.")
                continue
            await log(
                "blue",
                f"[sweep {pass_id}] Requesting mitigation rules from {settings.blue_team_model}.",
            )
            patch = await muse.run_blue_team_sanitizer(
                spec.filename,
                profile,
                finding,
                pre.output,
                spec.contract + _BLUE_MITIGATION_SUFFIX,
            )
            passed.patch = patch
            mitigation = extract_mitigation_rules(patch)
            passed.diff = mitigation
            await log("blue", patch.sanitization_strategy)
            container, snapshot = await blocking(
                sandbox.replace_binary_harness,
                container,
                snapshot,
                network,
                mitigation=mitigation,
            )
            regression = await blocking(
                sandbox.run_isolated_verifier, network, BINARY_BASELINE_SCRIPT
            )
            result.traces[f"{pass_id}:regression"] = regression.output
            if regression.exit_code != 0:
                raise PatchRejected(
                    f"Binary sweep pass {pass_id} mitigated harness failed baseline."
                )
            passed.regression_passed = True
            post = await blocking(
                sandbox.run_isolated_verifier, network, finding.verification_script_python
            )
            passed.post_exit_code = post.exit_code
            result.traces[f"{pass_id}:after"] = post.output
            await log(
                "blue",
                f"[sweep {pass_id}] Post-mitigation check exited {post.exit_code}. {post.output}",
            )
            if post.inconclusive:
                raise SandboxError(
                    f"Binary sweep pass {pass_id} post-mitigation verifier was inconclusive."
                )
            final_health = await blocking(
                sandbox.run_isolated_verifier, network, BINARY_BASELINE_SCRIPT
            )
            result.traces[f"{pass_id}:after_probe_regression"] = final_health.output
            if final_health.exit_code != 0:
                passed.regression_passed = False
                raise PatchRejected(
                    f"Binary sweep pass {pass_id} harness failed checks after the probe."
                )
            if post.exit_code != 1:
                result.status = "failed"
                result.message = (
                    f"Binary sweep pass {pass_id} probe still reaches the sink after mitigation."
                )
                break
            passed.receipt = build_verdict_receipt(
                fixture=f"binary:{spec.filename}",
                pre_exit_code=pre.exit_code,
                post_exit_code=post.exit_code,
                regression_passed=passed.regression_passed,
                patch_content=mitigation,
            )
        result.cumulative_diff = "\n".join(p.diff for p in result.pass_results if p.diff)
        if result.status != "failed":
            if all(p.holds for p in result.pass_results):
                result.status = "verified"
                result.message = (
                    "All binary sweep passes hold: every confirmed boundary is "
                    "mitigated and harness checks passed. Review the mitigation rules."
                )
                try:
                    from modules.intel.sms_vault import VaultNamespace, commit_verified

                    commit_verified(
                        namespace=VaultNamespace.RED,
                        source=profile,
                        payload={
                            "kind": "binary_profile",
                            "fixture": spec.filename,
                            "format": spec.binary_format,
                            "signals": summarize_profile(profile).get("signals", []),
                        },
                    )
                    if result.cumulative_diff:
                        commit_verified(
                            namespace=VaultNamespace.BLUE,
                            source=result.cumulative_diff,
                            payload={
                                "kind": "binary_mitigation",
                                "fixture": spec.filename,
                                "passes": [p.pass_id for p in result.pass_results],
                            },
                        )
                    await log("system", "[phase vault] Binary profile + rules committed.")
                except Exception as exc:
                    await log("system", f"[phase vault] Commit skipped ({type(exc).__name__}).")
            else:
                result.status = "failed"
                result.message = "One or more binary sweep passes did not hold."
    except PatchRejected as exc:
        result.status, result.message = "rejected", str(exc)
    except (ConfigurationError, AgentError, SandboxError, ValueError, BinaryRejected) as exc:
        result.status, result.message = "error", str(exc)
    except DockerException:
        result.status, result.message = (
            "error",
            "Docker operation failed. Check the daemon and base images.",
        )
    except Exception as exc:
        result.status, result.message = (
            "error",
            f"Binary sweep failed ({type(exc).__name__}); no verified mitigation produced.",
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


def redact_binary_sweep_result_for_user(result: SweepScanResult) -> dict:
    """User-safe binary sweep report: rules + exit codes only, no probe payloads."""
    data = result.model_dump()
    for passed in data.get("pass_results", []):
        finding = passed.get("finding")
        if isinstance(finding, dict):
            finding["verification_script_python"] = EXPLOIT_REDACTED
    for key, value in list(data.get("traces", {}).items()):
        if isinstance(value, str) and (":before" in key or ":after" in key):
            data["traces"][key] = PROBE_OUTPUT_WITHHELD
    return data


__all__ = [
    "BINARY_BASELINE_SCRIPT",
    "execute_binary_sweep",
    "extract_mitigation_rules",
    "redact_binary_sweep_result_for_user",
    "validate_binary_blob",
]
