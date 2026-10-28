# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""One baseline -> probe -> patch -> regression workflow for both entry points."""

from typing import Literal

from docker.errors import DockerException
from pydantic import BaseModel, Field

from agents import (
    AgentError,
    BlueResearchDigest,
    BlueTeamPatch,
    MetaMuseClient,
    RedResearchDigest,
    RedTeamFinding,
)
from chatter import chatter
from checks import normal_behavior_script
from config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key
from docker_manager import DockerSandboxManager, SandboxError
from patches import PatchRejected, validate_patch
from pricing import ScanUsage
from registry import TARGETS_REGISTRY
from sms_async import Emit, blocking, make_log


def _sink_keywords(filename: str, contract: str) -> tuple[list[str], list[str]]:
    """Cheap local hints for the research pass: no model call, no network.

    Returns (package_hints, keyword_pairs). Filenames/contracts mentioning a
    known ecosystem package seed OSV/GHSA lookups; anything else falls back
    to CIRCL vendor/product browse pairs derived from the contract words.
    """
    text = f"{filename} {contract}".lower()
    packages: list[str] = []
    for name in (
        "express",
        "django",
        "flask",
        "rails",
        "spring",
        "react",
        "vue",
        "axios",
        "lodash",
        "mysql",
        "sqlite",
        "postgres",
        "redis",
    ):
        if name in text:
            packages.append(name)
    pairs: list[str] = []
    words = [w.strip(".,;:()[]{}\"'").lower() for w in contract.split()]
    nouns = [w for w in words if len(w) > 3][:8]
    for i in range(0, len(nouns) - 1, 2):
        pairs.append(f"{nouns[i]} {nouns[i + 1]}")
    return packages[:3], pairs[:3]


def _run_opt_in_scanners(settings: PurpleBoxConfig, filename: str, log_callable=None) -> list:
    """Run enabled local scanners against the fixture source. Never raises.

    Materializes the fixture source into a temp dir and runs each enabled
    scanner binary on the host (never inside the sandbox). Absent binaries
    and per-scanner failures degrade to fewer records. Sync: called via
    blocking() from the async workflow.
    """
    import tempfile
    from pathlib import Path

    from registry import TARGETS_REGISTRY

    target = TARGETS_REGISTRY.get(filename.replace(".py", "").replace(".js", ""))
    if target is None:
        for _key, candidate in TARGETS_REGISTRY.items():
            if candidate.filename == filename:
                target = candidate
                break
    if target is None:
        return []
    out: list = []
    with tempfile.TemporaryDirectory(prefix="purplebox-scan-") as tmp:
        src = Path(tmp) / target.filename
        src.write_text(target.read_source(), encoding="utf-8")
        wanted = set(settings.research_scanners)
        if "trivy" in wanted:
            try:
                import scanner_binaries as _sb

                out.extend(_sb.run_trivy(tmp))
            except Exception:
                pass
        if "grype" in wanted:
            try:
                import scanner_binaries as _sb

                out.extend(_sb.run_grype(tmp))
            except Exception:
                pass
        if "osv-scanner" in wanted:
            try:
                import scanner_binaries as _sb

                out.extend(_sb.run_osv_scanner(tmp))
            except Exception:
                pass
        if "dependency-check" in wanted:
            try:
                import scanner_binaries as _sb

                out.extend(_sb.run_dependency_check(tmp))
            except Exception:
                pass
        if "dependency-track" in wanted:
            try:
                import scanner_dtrack as _dt

                out.extend(_dt.scan_packages(target.filename, []))
            except Exception:
                pass
    return out[:20]


async def _gather_research(
    muse, settings: PurpleBoxConfig, filename: str, contract: str, log
) -> tuple[str, list[dict]]:
    """Opt-in research sidecar pass. Returns (digest_text, record_dicts).

    Never raises: transport failures degrade to an empty digest and the scan
    continues with ungrounded red/blue prompts. Every record stays marked
    untrusted; only Docker evidence decides verdicts downstream.
    """

    try:
        import research as _research
    except ImportError:
        return "", []
    sink = f"{filename}: {contract}"[:2000]
    package_hints, keyword_pairs = _sink_keywords(filename, contract)
    try:
        records = await blocking(
            _research.research_for_sink,
            keyword_pairs,
            package_hints=package_hints,
        )
    except Exception as exc:
        await log(
            "research",
            f"[phase intel] Intel fetch unavailable ({type(exc).__name__}); continuing ungrounded.",
        )
        return "", []
    records = list(records)
    # CVE ids mentioned in the sink/contract get the full endpoint series
    # (CIRCL + OSV + EPSS + GHSA); named text gets web definition notes.
    # Same untrusted-data rules as every other record below.
    try:
        from demo_gen import parse_build_intent as _parse_intent

        intent = _parse_intent(vulns=f"{filename} {contract}")
        if intent.cve_ids:
            records = list(await blocking(_research.cve_records, intent.cve_ids)) + records
        # Only query the web for substantive named types or genuinely
        # descriptive free text — skip filename/contract word-salad so the
        # series doesn't burn requests on noise.
        web_queries = list(intent.named_types) + [
            free for free in intent.free_text if len(free.split()) >= 4
        ]
        if web_queries:
            records = records + list(await blocking(_research.web_notes, web_queries))
    except Exception:
        pass
    if settings.research_scanners:
        scanner_hits = await blocking(_run_opt_in_scanners, settings, filename, log)
        records.extend(scanner_hits)
    if not records:
        await log(
            "research",
            "[phase intel] No intel records for this sink; continuing ungrounded.",
        )
        return "", []
    await log(
        "research",
        f"[phase intel] {len(records)} intel records across "
        f"{len({getattr(r, 'source', getattr(r, 'scanner', '?')) for r in records})} sources.",
    )
    from sms_records import to_record_dict as _to_dict

    record_dicts = [_to_dict(r) for r in records[:16]]
    digest = ""
    try:
        red_digest: RedResearchDigest = await muse.run_red_research(sink, record_dicts)
        blue_digest: BlueResearchDigest = await muse.run_blue_research(sink, record_dicts)
        parts = [
            "Grounded attack patterns: " + "; ".join(red_digest.attack_patterns[:4]),
            "Grounded fix patterns: " + "; ".join(blue_digest.fix_patterns[:4]),
            "CWE hints: "
            + ", ".join(sorted(set(red_digest.cwe_hints + blue_digest.cwe_hints))[:4]),
        ]
        digest = "\n".join(p for p in parts if p and not p.endswith(": "))
        await log(
            "research",
            f"[phase intel] Red patterns: {len(red_digest.attack_patterns)}, "
            f"blue patterns: {len(blue_digest.fix_patterns)}.",
        )
    except (AgentError, ValueError) as exc:
        await log(
            "research",
            f"[phase intel] Research digest unavailable ({type(exc).__name__}); raw records only.",
        )
    return digest, record_dicts


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
    research_records: list[dict] = Field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.status == "verified" and self.cleanup_ok


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

    log = make_log(emit)

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

        await log(
            "red",
            f"[phase red probe] Analyzing {target.filename} with {settings.red_team_model}.",
        )
        research_digest = ""
        if settings.research_enabled:
            await log("research", "Research sidecars on: fetching keyless intel.")
            research_digest, result.research_records = await _gather_research(
                muse, settings, target.filename, target.contract, log
            )
        await log(
            "red",
            chatter("red_start", persona="Breakwater", path=target.filename, seed=1),
        )
        finding = await muse.run_red_team_analysis(
            target.filename,
            source,
            target.contract
            + (f"\n\nGrounded intel:\n{research_digest}" if research_digest else ""),
        )
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
        await log("red", f"[phase red probe] Boundary check exited {pre.exit_code}. {pre.output}")
        await log(
            "red",
            chatter(
                "red_proof",
                persona="Breakwater",
                path=target.filename,
                code=pre.exit_code,
                seed=2,
            ),
        )
        if pre.inconclusive:
            raise SandboxError("Pre-patch verifier was inconclusive; no patch was requested.")
        if pre.exit_code == 1:
            result.status = "not_confirmed"
            result.message = (
                "The probe did not confirm the reported boundary. No patch was requested."
            )
        else:
            await log(
                "blue",
                f"[phase blue patch] Requesting a sanitization patch from {settings.blue_team_model}.",
            )
            await log(
                "blue",
                chatter("blue_start", persona="Bastion", path=target.filename, seed=3),
            )
            patch = await muse.run_blue_team_sanitizer(
                target.filename,
                source,
                finding,
                pre.output,
                target.contract
                + (f"\n\nGrounded intel:\n{research_digest}" if research_digest else ""),
            )
            result.patch = patch
            result.diff = validate_patch(target, source, patch.patched_file_content)
            await log("blue", patch.sanitization_strategy)
            await log("blue", result.diff)
            await log(
                "system",
                "[phase blue patch] Starting a fresh target from the patched snapshot.",
            )
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
            await log(
                "blue",
                f"[phase verify] Post-patch boundary check exited {post.exit_code}. {post.output}",
            )
            await log(
                "blue",
                chatter(
                    "blue_done",
                    persona="Bastion",
                    path=target.filename,
                    code=post.exit_code,
                    seed=4,
                ),
            )
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
    await log("system", f"[done] {result.message}")
    if sandbox is not None and result.cleanup_ok:
        await log("system", "[phase cleanup] Session containers, snapshots, and network removed.")
    return result


from sms_redact import EXPLOIT_REDACTED as EXPLOIT_REDACTED  # noqa: E402 (re-export shim; canonical defs live in sms_redact)
from sms_redact import redact_fixture_result as _redact_fixture  # noqa: E402 (re-export shim; canonical defs live in sms_redact)


def redact_fixture_result_for_user(result: "ScanResult") -> dict:
    """User-safe fixture report: patch + exit codes only, no probe source or payload output."""
    return _redact_fixture(result)
