# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Iterative arbitrary-project red, blue, verification, and reporting workflow."""

from __future__ import annotations

import ast
import asyncio
import difflib
import hashlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from modules.core.agents import AgentError, MetaMuseClient
from modules.core.config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key
from modules.core.docker_manager import (
    DockerSandboxManager,
    ProjectCheckResult,
    SandboxError,
    VerificationResult,
)
from modules.core.personas import blue_persona, red_persona
from modules.core.pricing import ScanUsage
from modules.services.chatter import chatter
from modules.services.project_agents import (
    BlueProposal,
    ContextCoverage,
    FinalBlueReport,
    ProjectAgentRunner,
    RedAnalysisArtifacts,
    documents_from_mapping,
)
from modules.services.projects import (
    ProjectSnapshot,
    ProjectSpec,
    replace_snapshot_files,
    snapshot_project,
)
from modules.shared.sms_async import Emit, blocking, make_log
from modules.shared.sms_budget import resolve_payload_budget
from modules.shared.sms_text import bounded as _bounded


class ProjectWorkflowError(RuntimeError):
    """An invalid project or untrusted stage result prevented safe continuation."""


class ProjectWorkflowInput(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    name: str = Field(min_length=1, max_length=256)
    files: dict[str, str] = Field(min_length=1, max_length=20_000)
    regression_command: list[str] = Field(min_length=1, max_length=128)
    contract: str = Field(default="", max_length=32_768)

    @model_validator(mode="after")
    def validate_snapshot(self) -> ProjectWorkflowInput:
        for path, content in self.files.items():
            validate_safe_path(path)
            if not isinstance(content, str):
                raise ValueError("Project file contents must be text.")
        if any(not part or len(part) > 4096 for part in self.regression_command):
            raise ValueError("Regression command entries must be non-empty and bounded.")
        return self


class ExecutionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    exit_code: int
    output: str = Field(max_length=131_072)

    @property
    def vulnerable(self) -> bool:
        """Exit 0 means the probe reached the boundary: the flaw is exposed."""
        return self.exit_code == 0

    @property
    def blocked(self) -> bool:
        """Exit 1 means the probe was stopped: the boundary held."""
        return self.exit_code == 1

    @property
    def inconclusive(self) -> bool:
        """Any other exit means the probe itself failed: no verdict possible."""
        return self.exit_code not in (0, 1)


class SnapshotVerification(BaseModel):
    """Evidence produced against one fresh target created from one immutable file map."""

    model_config = ConfigDict(extra="forbid", strict=True)
    probe: ExecutionEvidence
    regression: ExecutionEvidence
    fresh_target: bool = True
    properties: ExecutionEvidence | None = None
    mutations: ExecutionEvidence | None = None


def property_gate_passed(verification: SnapshotVerification | Mapping[str, Any] | Any) -> bool:
    """Fail-closed normal-contract property gate: True unless properties ran and failed.

    ``None`` properties means the fixture has no property contract (arbitrary
    projects) or the check did not run, so the gate passes and the existing
    regression requirement decides. Any recorded properties exit other than 0
    fails the gate; missing/inconclusive evidence never upgrades a verdict.
    """
    if isinstance(verification, SnapshotVerification):
        properties = verification.properties
    elif isinstance(verification, Mapping):
        properties = verification.get("properties")
    else:
        properties = getattr(verification, "properties", None)
    if properties is None:
        return True
    if isinstance(properties, ExecutionEvidence):
        return properties.exit_code == 0
    if isinstance(properties, Mapping):
        try:
            return int(properties.get("exit_code")) == 0
        except (TypeError, ValueError):
            return False
    try:
        return int(properties.exit_code) == 0
    except (TypeError, ValueError):
        return False


def mutation_gate_passed(verification: SnapshotVerification | Mapping[str, Any] | Any) -> bool:
    """Fail-closed bounded-mutation gate: True unless mutations ran and failed.

    ``None`` mutations means the fixture has no mutation contract (arbitrary
    projects, node fixtures in another agent's lane) or the check did not run,
    so the gate passes and the existing regression requirement decides. Any
    recorded mutations exit other than 0 fails the gate; missing/inconclusive
    evidence never upgrades a verdict.
    """
    if isinstance(verification, SnapshotVerification):
        mutations = verification.mutations
    elif isinstance(verification, Mapping):
        mutations = verification.get("mutations")
    else:
        mutations = getattr(verification, "mutations", None)
    if mutations is None:
        return True
    if isinstance(mutations, ExecutionEvidence):
        return mutations.exit_code == 0
    if isinstance(mutations, Mapping):
        try:
            return int(mutations.get("exit_code")) == 0
        except (TypeError, ValueError):
            return False
    try:
        return int(mutations.exit_code) == 0
    except (TypeError, ValueError):
        return False


class ProjectSandbox(Protocol):
    """High-level Docker boundary required by the arbitrary-project workflow."""

    def require_base_images(self) -> None: ...

    def verify_project_snapshot(
        self,
        project: ProjectWorkflowInput,
        files: Mapping[str, str],
        verification_script_python: str,
        regression_command: Sequence[str],
        *,
        label: str,
    ) -> SnapshotVerification: ...

    def close(self) -> None: ...


class GuardRationale(BaseModel):
    """Structured rationale for a rejected sanitization patch (SPEC 14.8 item 2).

    ``guard_id`` names which guard fired, ``trigger`` names the protected
    path/line/setting that tripped it. Contains no probe bytes (LAW 4):
    triggers name paths, sink substrings from the guard allowlist, or
    original-source symbols only — never probe output.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    guard_id: str = Field(min_length=1, max_length=128)
    reason: str = ""
    trigger: str = Field(default="", max_length=500)


class ReplacementValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    accepted: bool
    paths: list[str] = Field(default_factory=list)
    changed_bytes: int = Field(default=0, ge=0)
    reason: str = ""
    guard_rationale: GuardRationale | None = None


class CycleEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    red: RedAnalysisArtifacts
    pre_verification: SnapshotVerification | None = None
    blue_proposal: BlueProposal | None = None
    replacement_validation: ReplacementValidation | None = None
    patched_verification: SnapshotVerification | None = None
    differential_passed: bool = False
    independent_red: RedAnalysisArtifacts | None = None
    independent_verification: SnapshotVerification | None = None
    final_blue_report: FinalBlueReport | None = None


class CycleReceipt(BaseModel):
    """Machine-readable execution-oracle receipt for one retained project cycle.

    Records only: records never upgrade a verdict, only the Docker evidence does.
    Exported alongside the candidate diff via the cycle report model dump.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    fixture: str
    pre_probe_exit: int
    post_probe_exit: int
    baseline_regression_exit: int
    patched_regression_exit: int
    differential_passed: bool
    property_exit: int | None = None
    property_passed: bool | None = None
    patch_sha256: str = ""
    retained: bool = True


def build_cycle_receipt(
    *,
    fixture: str,
    pre: SnapshotVerification,
    patched: SnapshotVerification,
    baseline_regression_exit: int,
    differential_passed: bool,
    candidate_diff: str,
) -> CycleReceipt:
    """Record a receipt for a retained cycle only; never upgrades a verdict."""
    properties = patched.properties
    if properties is None:
        property_exit: int | None = None
        property_passed: bool | None = None
    else:
        property_exit = properties.exit_code
        property_passed = properties.exit_code == 0
    return CycleReceipt(
        fixture=fixture,
        pre_probe_exit=pre.probe.exit_code,
        post_probe_exit=patched.probe.exit_code,
        baseline_regression_exit=baseline_regression_exit,
        patched_regression_exit=patched.regression.exit_code,
        differential_passed=differential_passed,
        property_exit=property_exit,
        property_passed=property_passed,
        patch_sha256=hashlib.sha256(candidate_diff.encode("utf-8")).hexdigest(),
        retained=True,
    )


def export_cycle_receipt_json(receipt: CycleReceipt) -> str:
    """Serialize a cycle receipt alongside the candidate diff for review."""
    return receipt.model_dump_json()


class ProjectCycleReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    cycle: int = Field(ge=1, le=20)
    pass_number: int = Field(default=1, ge=1, le=2)
    status: Literal[
        "retained", "rolled_back", "no_finding", "not_confirmed", "inconclusive", "error"
    ]
    message: str
    changed_paths: list[str] = Field(default_factory=list)
    diff: str = ""
    receipt: CycleReceipt | None = None
    evidence: CycleEvidence


class CleanupReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    attempted: bool = False
    succeeded: bool = True
    error: str = ""


class ProjectWorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    project: str
    status: Literal["verified", "no_findings", "partial", "error"] = "error"
    message: str = "Project workflow did not complete."
    scan_profile: str = "custom"
    passes_per_cycle: int = Field(default=1, ge=1, le=2)
    red_agents: int = Field(default=5, ge=1, le=12)
    blue_agents: int = Field(default=5, ge=1, le=12)
    cycles_requested: int = Field(ge=1, le=20)
    cycles_completed: int = Field(default=0, ge=0, le=20)
    cycle_reports: list[ProjectCycleReport] = Field(default_factory=list)
    cumulative_diff: str = ""
    baseline_verification: SnapshotVerification | None = None
    context_coverage: list[ContextCoverage] = Field(default_factory=list)
    research_records: list[dict] = Field(default_factory=list)
    usage: ScanUsage = Field(default_factory=ScanUsage)
    total_tokens: int = 0
    total_cost_usd: float | None = None
    cleanup: CleanupReport = Field(default_factory=CleanupReport)

    @property
    def success(self) -> bool:
        return self.status in ("verified", "no_findings") and self.cleanup.succeeded

    @property
    def cycles(self) -> list[ProjectCycleReport]:
        return self.cycle_reports

    @property
    def diff(self) -> str:
        return self.cumulative_diff

    @property
    def cost_usd(self) -> float | None:
        return self.total_cost_usd

    @property
    def cleanup_ok(self) -> bool:
        return self.cleanup.succeeded

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        data.update(
            success=self.success,
            cycles=[cycle.model_dump() for cycle in self.cycle_reports],
            diff=self.cumulative_diff,
            cost_usd=self.total_cost_usd,
            cleanup_ok=self.cleanup.succeeded,
        )
        return data


class ProjectWorkflowLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    max_batch_bytes: int = Field(default=48_000, ge=1_024, le=4_000_000)
    max_changed_files: int = Field(default=8, ge=1, le=32)
    max_changed_bytes: int = Field(default=256_000, ge=1_024, le=2_000_000)
    max_evidence_chars: int = Field(default=16_000, ge=1_000, le=131_072)
    max_diff_chars: int = Field(default=100_000, ge=1_000, le=1_000_000)
    max_context_files: int = Field(default=512, ge=1, le=4096)
    max_context_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=32 * 1024 * 1024)
    max_payload_bytes: int = Field(default=256_000, ge=16_384, le=4_000_000)


def validate_safe_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if (
        not path
        or candidate.is_absolute()
        or path != candidate.as_posix()
        or "\\" in path
        or any(part in ("", ".", "..") for part in candidate.parts)
    ):
        raise ValueError(f"Unsafe project path: {path!r}")


def coerce_project(project: ProjectWorkflowInput | Mapping[str, Any] | Any) -> ProjectWorkflowInput:
    """Accept the public model plus the simple objects emitted by project intake."""
    if isinstance(project, ProjectWorkflowInput):
        return project
    if isinstance(project, Mapping):
        raw = dict(project)
    elif hasattr(project, "model_dump"):
        raw = project.model_dump()
    else:
        raw = vars(project)

    name = raw.get("name") or raw.get("project_name") or raw.get("project_id")
    files = raw.get("files") or raw.get("source_files")
    command = raw.get("regression_command") or raw.get("test_command")
    contract = raw.get("contract") or ""
    if isinstance(files, list):
        converted: dict[str, str] = {}
        for item in files:
            item = item.model_dump() if hasattr(item, "model_dump") else item
            if not isinstance(item, Mapping):
                raise ProjectWorkflowError("Project source entries must be mappings.")
            converted[str(item.get("path", ""))] = str(item.get("content", ""))
        files = converted
    if isinstance(command, tuple):
        command = list(command)
    try:
        return ProjectWorkflowInput.model_validate(
            {
                "name": name,
                "files": files,
                "regression_command": command,
                "contract": contract,
            },
            strict=True,
        )
    except Exception as exc:
        raise ProjectWorkflowError("Project intake did not provide a valid safe snapshot.") from exc


_PRIORITY_SUFFIX_RANK0 = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".php",
        ".go",
        ".rs",
        ".rb",
        ".java",
        ".c",
        ".cpp",
        ".sql",
        ".cnf",
        ".conf",
        ".ini",
        ".yaml",
        ".yml",
        ".toml",
    }
)


def _priority_rank(path: str) -> int:
    lowered = path.lower()
    parts = lowered.split("/")
    name = parts[-1] if parts else lowered
    suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    is_test = (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "/test/" in lowered
        or "/tests/" in lowered
        or "/__tests__/" in lowered
        or ".test." in lowered
        or ".spec." in lowered
    )
    if is_test:
        return 1
    if suffix in _PRIORITY_SUFFIX_RANK0 and "test" not in lowered and "docs" not in lowered:
        # Exclude test/ or docs/ from rank 0 even if suffix matches.
        if (
            "/test" in lowered
            or lowered.startswith("test")
            or "/docs/" in lowered
            or lowered.startswith("docs/")
        ):
            return 1
        return 0
    if suffix in {".md", ".txt", ".rst", ".css", ".html", ".svg", ".json"}:
        return 2
    # Default: treat unknown as rank 1 (context awareness) unless docs/assets.
    if "/docs/" in lowered or lowered.startswith("docs/"):
        return 2
    return 1


def priority_rank(path: str, text: str | None = None) -> tuple[int, str]:
    return (_priority_rank(path), path)


def _snapshot_context(
    spec: ProjectSpec, snapshot: ProjectSnapshot, limits: ProjectWorkflowLimits
) -> tuple[ProjectWorkflowInput, list[str], list[str]]:
    """Select bounded UTF-8 inference context while retaining the full immutable sandbox snapshot."""
    selected: dict[str, str] = {}
    omitted: list[str] = []
    notes: list[str] = []
    selected_bytes = 0
    candidates: list[tuple[tuple[int, str], str, bytes]] = []
    for path in sorted(snapshot.files):
        content = snapshot.files[path]
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            omitted.append(path)
            continue
        candidates.append((priority_rank(path, text), path, content))
    candidates.sort(key=lambda item: item[0])
    for _, path, content in candidates:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            omitted.append(path)
            continue
        if len(selected) >= limits.max_context_files:
            omitted.append(path)
            continue
        if selected_bytes + len(content) > limits.max_context_bytes:
            omitted.append(path)
            continue
        selected[path] = text
        selected_bytes += len(content)
    if not selected:
        raise ProjectWorkflowError(
            "The project snapshot has no UTF-8 source within context limits."
        )
    if omitted:
        notes.append(
            f"Inference context included {len(selected)} of {len(snapshot.files)} files and "
            f"{selected_bytes} of {snapshot.total_bytes} bytes; {len(omitted)} paths were omitted "
            "because they were binary or exceeded the explicit 512-file/2-MiB context caps."
        )
    return (
        ProjectWorkflowInput(
            name=spec.path.name,
            files=selected,
            regression_command=list(spec.test_command),
            contract=spec.contract,
        ),
        omitted,
        notes,
    )


def _check_evidence(check: ProjectCheckResult, limit: int) -> ExecutionEvidence:
    output = "\n".join(part for part in (check.stdout, check.stderr) if part)
    exit_code = 2 if check.timed_out or check.exit_code is None else check.exit_code
    return ExecutionEvidence(exit_code=exit_code, output=_bounded(output, limit))


class DockerProjectSandbox:
    """Adapt DockerSandboxManager project primitives to fresh evidence snapshots."""

    def __init__(
        self,
        config: PurpleBoxConfig,
        spec: ProjectSpec,
        snapshot: ProjectSnapshot,
        *,
        manager_factory=DockerSandboxManager,
    ):
        self.config = config
        self.spec = spec
        self.base_snapshot = snapshot
        self.manager = manager_factory(config)
        self.network = None

    def require_base_images(self) -> None:
        self.manager.require_base_images()
        self.network = self.manager.create_isolated_network()

    def verify_project_snapshot(
        self,
        project: ProjectWorkflowInput,
        files: Mapping[str, str],
        verification_script_python: str,
        regression_command: Sequence[str],
        *,
        label: str,
    ) -> SnapshotVerification:
        del project, label
        if tuple(regression_command) != tuple(self.spec.test_command):
            raise SandboxError("Regression command changed after project intake.")
        if self.network is None:
            raise SandboxError("Project network was not initialized.")
        snapshot = replace_snapshot_files(self.base_snapshot, files)
        target = None
        try:
            target, _image = self.manager.start_project(self.network, self.spec, snapshot)
            # Best-effort readiness poll up to 2 seconds (mirrors workflow READY_SCRIPT).
            try:
                import time

                from modules.core.docker_manager import READY_SCRIPT

                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    try:
                        ready = target.exec_run(["python3", "-c", READY_SCRIPT])
                        if getattr(ready, "exit_code", 1) == 0:
                            break
                    except Exception:
                        pass
                    time.sleep(0.2)
            except Exception:
                pass
            regression_check = self.manager.run_project_check(
                self.network, self.spec, snapshot, command=list(self.spec.test_command)
            )
            regression_ev = _check_evidence(regression_check, 131_072)
            if regression_ev.exit_code != 0:
                # Do not run probe if baseline regression already fails.
                probe_ev = ExecutionEvidence(exit_code=2, output="Regression failed before probe.")
                return SnapshotVerification(
                    probe=probe_ev, regression=regression_ev, fresh_target=True
                )
            probe_check = self.manager.run_project_check(
                self.network, self.spec, snapshot, script=verification_script_python
            )
            probe_ev = _check_evidence(probe_check, 131_072)
            # Wave 8 R1: property normal-contract checks run in the same
            # capped container mechanism after regression green, mirroring the
            # probe call shape. The fixture id is the spec contract's first
            # line only when it names a known fixture; anything else skips
            # (properties stays None) so arbitrary projects are unaffected.
            properties_ev: ExecutionEvidence | None = None
            try:
                from modules.core.checks import project_property_script, property_fixture_supported

                fixture_id = (self.spec.contract or "").splitlines()[0].strip()
                if property_fixture_supported(fixture_id):
                    property_check = self.manager.run_project_check(
                        self.network,
                        self.spec,
                        snapshot,
                        script=project_property_script(fixture_id),
                    )
                    properties_ev = _check_evidence(property_check, 131_072)
            except Exception:
                properties_ev = ExecutionEvidence(
                    exit_code=2, output="Properties check did not run."
                )
            # SPEC 14.8 item 4: bounded mutation-count probes run in the same
            # capped container mechanism after regression green, mirroring the
            # probe call shape. PHP + MySQL only (this agent's lane); anything
            # else skips (mutations stays None) so other lanes are unaffected.
            mutations_ev: ExecutionEvidence | None = None
            try:
                from modules.core.checks import (
                    mutation_fixture_supported,
                    project_mutation_script,
                )

                mutation_id = (self.spec.contract or "").splitlines()[0].strip()
                if mutation_fixture_supported(mutation_id):
                    mutation_check = self.manager.run_project_check(
                        self.network,
                        self.spec,
                        snapshot,
                        script=project_mutation_script(mutation_id),
                    )
                    mutations_ev = _check_evidence(mutation_check, 131_072)
            except Exception:
                mutations_ev = ExecutionEvidence(exit_code=2, output="Mutations check did not run.")
            # Critical addition: post-probe liveness against same still-running target.
            # A blocked (1) or inconclusive (2) probe must not earn success if it
            # crashed the service; exit 0 (reachable) needs no liveness override.
            if probe_ev.exit_code in (1, 2):
                post_probe_ev = None
                try:
                    # Prefer exec inside the same still-running target when available.
                    exec_run = getattr(target, "exec_run", None)
                    if callable(exec_run):
                        try:
                            # Run the regression command via exec argv (no shell interpolation).
                            # Use shlex join to avoid interpolation; exec_run does not use shell.
                            result = exec_run(list(self.spec.test_command))
                            code = getattr(result, "exit_code", None)
                            out = ""
                            try:
                                output = getattr(result, "output", b"")
                                if isinstance(output, (bytes, bytearray)):
                                    out = bytes(output).decode("utf-8", errors="replace")
                                else:
                                    out = str(output)
                            except Exception:
                                out = ""
                            if isinstance(code, int):
                                post_probe_ev = ExecutionEvidence(
                                    exit_code=code, output=_bounded(out[-16384:], 131072)
                                )
                        except Exception:
                            post_probe_ev = None
                except Exception:
                    post_probe_ev = None
                if post_probe_ev is None:
                    try:
                        post_check = self.manager.run_project_check(
                            self.network, self.spec, snapshot, command=list(self.spec.test_command)
                        )
                        post_probe_ev = _check_evidence(post_check, 131_072)
                    except Exception:
                        post_probe_ev = None
                if post_probe_ev is not None and post_probe_ev.exit_code != 0:
                    # Override regression so a crashed/deadlocked service triggers rollback.
                    regression_ev = ExecutionEvidence(
                        exit_code=post_probe_ev.exit_code,
                        output=_bounded(
                            "Post-probe regression failed:\n" + post_probe_ev.output, 131072
                        ),
                    )
            return SnapshotVerification(
                probe=probe_ev,
                regression=regression_ev,
                fresh_target=True,
                properties=properties_ev,
                mutations=mutations_ev,
            )
        finally:
            if target is not None:
                self.manager.stop_project(target)

    def close(self) -> None:
        self.manager.close()


def _normalize_execution(value: Any, limit: int) -> ExecutionEvidence:
    if isinstance(value, ExecutionEvidence):
        return value.model_copy(update={"output": _bounded(value.output, limit)})
    if isinstance(value, VerificationResult):
        return ExecutionEvidence(exit_code=value.exit_code, output=_bounded(value.output, limit))
    if isinstance(value, Mapping):
        return ExecutionEvidence(
            exit_code=int(value["exit_code"]), output=_bounded(str(value.get("output", "")), limit)
        )
    return ExecutionEvidence(
        exit_code=int(value.exit_code),
        output=_bounded(str(getattr(value, "output", "")), limit),
    )


def normalize_snapshot_verification(value: Any, limit: int) -> SnapshotVerification:
    if isinstance(value, SnapshotVerification):
        return SnapshotVerification(
            probe=_normalize_execution(value.probe, limit),
            regression=_normalize_execution(value.regression, limit),
            fresh_target=value.fresh_target,
            properties=None
            if value.properties is None
            else _normalize_execution(value.properties, limit),
            mutations=None
            if value.mutations is None
            else _normalize_execution(value.mutations, limit),
        )
    if isinstance(value, Mapping):
        properties = value.get("properties")
        mutations = value.get("mutations")
        return SnapshotVerification(
            probe=_normalize_execution(value["probe"], limit),
            regression=_normalize_execution(value["regression"], limit),
            fresh_target=bool(value.get("fresh_target", True)),
            properties=None if properties is None else _normalize_execution(properties, limit),
            mutations=None if mutations is None else _normalize_execution(mutations, limit),
        )
    properties = getattr(value, "properties", None)
    mutations = getattr(value, "mutations", None)
    return SnapshotVerification(
        probe=_normalize_execution(value.probe, limit),
        regression=_normalize_execution(value.regression, limit),
        fresh_target=bool(getattr(value, "fresh_target", True)),
        properties=None if properties is None else _normalize_execution(properties, limit),
        mutations=None if mutations is None else _normalize_execution(mutations, limit),
    )


def _extract_signatures(source: str) -> tuple[dict[str, int], set[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"Invalid Python syntax: {exc}") from exc
    funcs: dict[str, int] = {}
    classes: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[node.name] = len(node.args.args)
        elif isinstance(node, ast.ClassDef):
            classes.add(node.name)
    return funcs, classes


_DANGEROUS_SINKS = {
    ".py": ["eval(", "exec(", "os.system(", "subprocess.Popen("],
    ".js": ["eval(", "exec(", "child_process"],
    ".php": ["eval(", "exec(", "shell_exec(", "system(", "passthru(", "os.system("],
}


def validate_replacements(
    proposal: BlueProposal,
    current_files: Mapping[str, str],
    *,
    max_changed_files: int,
    max_changed_bytes: int,
    protected_paths: Sequence[str] = (),
) -> tuple[ReplacementValidation, dict[str, str]]:
    """Fail closed on paths, hashes, duplicates, no-ops, and configured change bounds."""

    def _reject(
        guard_id: str, reason: str, trigger: str = ""
    ) -> tuple[ReplacementValidation, dict[str, str]]:
        return (
            ReplacementValidation(
                accepted=False,
                reason=reason,
                guard_rationale=GuardRationale(
                    guard_id=guard_id, reason=reason, trigger=trigger[:500]
                ),
            ),
            {},
        )

    if not proposal.replacements:
        return _reject("empty_proposal", "Blue proposed no replacements.")
    if len(proposal.replacements) > max_changed_files:
        return _reject("file_count_exceeded", "Replacement file limit exceeded.")

    changed: dict[str, str] = {}
    changed_bytes = 0
    protected = set(protected_paths)
    for replacement in proposal.replacements:
        try:
            validate_safe_path(replacement.path)
        except ValueError:
            return _reject(
                "unsafe_path",
                "Replacement path is unsafe.",
                replacement.path,
            )
        if replacement.path not in current_files:
            return _reject(
                "unknown_path",
                "Replacement path is not in the safe snapshot.",
                replacement.path,
            )
        if replacement.path in protected:
            return _reject(
                "protected_path",
                "Replacement targeted a protected regression-test path.",
                replacement.path,
            )
        if replacement.path in changed:
            return _reject(
                "duplicate_path",
                "Replacement paths are duplicated.",
                replacement.path,
            )
        original = current_files[replacement.path]
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
        if digest != replacement.original_sha256:
            return _reject(
                "hash_mismatch",
                "Replacement source hash does not match the current snapshot.",
                replacement.path,
            )
        if replacement.replacement_content == original:
            return _reject("noop_replacement", "Replacement is a no-op.", replacement.path)
        content = replacement.replacement_content
        if "\x00" in content:
            return _reject(
                "nul_bytes",
                "Replacement contains NUL bytes.",
                replacement.path,
            )
        if content.lstrip().startswith("```"):
            return _reject(
                "markdown_fences",
                "Replacement starts with markdown fences.",
                replacement.path,
            )
        # License header preservation
        for line in original.splitlines():
            if (
                "Required Notice:" in line or "polyformproject.org/licenses/" in line
            ) and line not in content:
                return _reject(
                    "license_notice_removed",
                    "Replacement removed a required license notice.",
                    line.strip(),
                )
        # Surgical edit ratio guard
        before_lines, after_lines = original.splitlines(), content.splitlines()
        changes = sum(
            max(i2 - i1, j2 - j1)
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
                a=before_lines, b=after_lines
            ).get_opcodes()
            if op != "equal"
        )
        budget = max(60, int(len(before_lines) * 0.35))
        if changes > budget:
            return _reject(
                "edit_budget_exceeded",
                "Replacement exceeds surgical sanitization line-change budget.",
                f"{changes} changed lines over {budget}-line budget in {replacement.path}",
            )
        # Python AST signature guard
        if replacement.path.endswith(".py"):
            try:
                orig_funcs, orig_classes = _extract_signatures(original)
            except ValueError:
                orig_funcs, orig_classes = {}, set()
            try:
                new_funcs, new_classes = _extract_signatures(content)
            except ValueError:
                return _reject(
                    "invalid_python_syntax",
                    "Replacement contains invalid Python syntax.",
                    replacement.path,
                )
            for name, param_count in orig_funcs.items():
                if name not in new_funcs:
                    return _reject(
                        "function_deleted",
                        f"Replacement deleted function: {name}",
                        name,
                    )
                if new_funcs[name] != param_count:
                    return _reject(
                        "function_signature_changed",
                        f"Replacement altered parameters of: {name}",
                        name,
                    )
            for name in orig_classes:
                if name not in new_classes:
                    return _reject(
                        "class_deleted",
                        f"Replacement deleted class: {name}",
                        name,
                    )
        # Dangerous primitive guard
        import pathlib as _pathlib

        suffix = _pathlib.PurePosixPath(replacement.path).suffix.lower()
        sinks = _DANGEROUS_SINKS.get(suffix, [])
        for sink in sinks:
            if sink in content and sink not in original:
                return _reject(
                    "forbidden_sink_introduced",
                    f"Replacement introduces forbidden sink: {sink}",
                    sink,
                )
        changed_bytes += len(content.encode("utf-8"))
        if changed_bytes > max_changed_bytes:
            return _reject(
                "byte_budget_exceeded",
                "Replacement byte limit exceeded.",
                replacement.path,
            )
        changed[replacement.path] = content
    return (
        ReplacementValidation(
            accepted=True,
            paths=sorted(changed),
            changed_bytes=changed_bytes,
            reason="Proposal is path-, hash-, and size-bounded; semantic review remains manual.",
        ),
        changed,
    )


def protected_regression_paths(
    paths: Sequence[str], regression_command: Sequence[str]
) -> list[str]:
    """Protect common test corpora and explicit existing argv file paths from Blue edits."""
    explicit = {
        PurePosixPath(part.removeprefix("./")).as_posix()
        for part in regression_command
        if part and not part.startswith("-")
    }
    protected: list[str] = []
    for path in paths:
        candidate = PurePosixPath(path)
        lowered_parts = {part.lower() for part in candidate.parts[:-1]}
        name = candidate.name.lower()
        common_test = (
            bool(lowered_parts & {"test", "tests", "__tests__"})
            or name.startswith("test_")
            or name.endswith("_test.py")
            or ".test." in name
            or ".spec." in name
        )
        if common_test or path in explicit:
            protected.append(path)
    return sorted(protected)


def render_diff(before: Mapping[str, str], after: Mapping[str, str], limit: int) -> str:
    pieces: list[str] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        pieces.extend(
            difflib.unified_diff(
                before.get(path, "").splitlines(keepends=True),
                after.get(path, "").splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
    return _bounded("".join(pieces), limit)


def differential_passed(baseline_exit: int | None, patched_exit: int | None) -> bool:
    """Explicit normal-contract differential gate: True only when both regressions passed.

    Fail-closed: a missing (None) exit code means the evidence was not observed,
    so the gate fails. Pure function over recorded exits; performs no Docker runs.
    """
    if baseline_exit is None or patched_exit is None:
        return False
    return baseline_exit == 0 and patched_exit == 0


def differential_class(exit_code: int | None) -> str:
    """Label one regression exit for audit records."""
    if exit_code is None:
        return "missing"
    return "pass" if exit_code == 0 else "fail"


def proposal_report_evidence(proposal: BlueProposal) -> dict[str, object]:
    """Remove full replacement bodies from later report prompts while preserving audit hashes."""
    return {
        "strategy": proposal.strategy,
        "limitations": proposal.limitations,
        "replacements": [
            {
                "path": item.path,
                "original_sha256": item.original_sha256,
                "replacement_sha256": hashlib.sha256(
                    item.replacement_content.encode("utf-8")
                ).hexdigest(),
                "replacement_bytes": len(item.replacement_content.encode("utf-8")),
                "rationale": item.rationale,
                "change_kind": item.change_kind,
            }
            for item in proposal.replacements
        ],
    }


async def execute_project_workflow(
    project: ProjectSpec | ProjectWorkflowInput | Mapping[str, Any] | Any,
    emit: Emit,
    *,
    cycles: int | None = None,
    config: PurpleBoxConfig | None = None,
    limits: ProjectWorkflowLimits | None = None,
    sandbox_factory: Callable[[PurpleBoxConfig], ProjectSandbox] | None = None,
    muse_factory: Callable[[PurpleBoxConfig], MetaMuseClient] = MetaMuseClient,
    agent_factory: Callable[
        [MetaMuseClient, PurpleBoxConfig], ProjectAgentRunner
    ] = ProjectAgentRunner,
) -> ProjectWorkflowResult:
    """Run up to twenty evidence-gated cycles without modifying the source project."""
    requested_cycles = (
        project.cycles if cycles is None and isinstance(project, ProjectSpec) else cycles
    )
    requested_cycles = 1 if requested_cycles is None else requested_cycles
    if not 1 <= requested_cycles <= 20:
        raise ValueError("cycles must be between 1 and 20.")
    bounds = limits or ProjectWorkflowLimits()
    payload_budget = bounds.max_payload_bytes
    if isinstance(project, ProjectSpec):
        payload_budget = resolve_payload_budget(payload_budget, project.context_budget)
    project_name = (
        project.path.name if isinstance(project, ProjectSpec) else coerce_project(project).name
    )
    profile_key = project.scan_profile if isinstance(project, ProjectSpec) else "custom"
    named_profile = profile_key != "custom"
    if named_profile and cycles is not None and cycles != project.cycles:
        raise ValueError("cycles cannot override a named scan profile.")
    passes_per_cycle = 2 if named_profile else 1
    red_agents = project.red_agents if isinstance(project, ProjectSpec) else 5
    blue_agents = project.blue_agents if isinstance(project, ProjectSpec) else 5
    result = ProjectWorkflowResult(
        project=project_name,
        cycles_requested=requested_cycles,
        scan_profile=profile_key,
        passes_per_cycle=passes_per_cycle,
        red_agents=red_agents,
        blue_agents=blue_agents,
    )
    project_digest = ""
    project_records: list[dict] = []
    sandbox: ProjectSandbox | None = None
    muse: MetaMuseClient | None = None
    safe_project: ProjectWorkflowInput | None = None
    original_files: dict[str, str] = {}
    cumulative_files: dict[str, str] = {}
    omitted_paths: list[str] = []
    coverage_notes: list[str] = []
    snapshot_total_paths = 0
    snapshot_total_bytes = 0
    verified_history: list[dict[str, object]] = []

    log = make_log(emit)

    try:
        settings = config or load_config()
        require_api_key(settings)
        if isinstance(project, ProjectSpec):
            if settings.inference_mode != "local" and not project.allow_remote_inference:
                raise ProjectWorkflowError(
                    "Remote inference consent is required before project source can be sent to Muse."
                )
            snapshot = await blocking(snapshot_project, project)
            safe_project, omitted_paths, coverage_notes = _snapshot_context(
                project, snapshot, bounds
            )
            snapshot_total_paths = len(snapshot.files)
            snapshot_total_bytes = snapshot.total_bytes
            if sandbox_factory is None:
                sandbox = await blocking(DockerProjectSandbox, settings, project, snapshot)
            else:
                sandbox = await blocking(sandbox_factory, settings)
        else:
            safe_project = coerce_project(project)
            snapshot_total_paths = len(safe_project.files)
            snapshot_total_bytes = sum(
                len(value.encode("utf-8")) for value in safe_project.files.values()
            )
            if sandbox_factory is None:
                raise ProjectWorkflowError(
                    "A ProjectSpec is required when using the default Docker project sandbox."
                )
            sandbox = await blocking(sandbox_factory, settings)
        original_files = dict(safe_project.files)
        cumulative_files = dict(original_files)
        muse = muse_factory(settings)
        agents = agent_factory(muse, settings)
        if settings.research_enabled:
            try:
                from modules.workflows.workflow import _gather_research as _fixture_gather

                project_digest, project_records = await _fixture_gather(
                    muse,
                    settings,
                    safe_project.name,
                    safe_project.contract,
                    log,
                )
                await log(
                    "research",
                    f"[phase intel] Project intel pass complete: "
                    f"{len(project_records)} records stored on the report.",
                )
            except Exception as exc:
                await log(
                    "research",
                    f"[phase intel] Project intel unavailable "
                    f"({type(exc).__name__}); continuing ungrounded.",
                )
        await blocking(sandbox.require_base_images)

        protected_paths = protected_regression_paths(
            list(cumulative_files), safe_project.regression_command
        )
        await log(
            "system",
            "[phase baseline] Running original-project baseline checks in isolated containers.",
        )
        baseline_raw = await blocking(
            sandbox.verify_project_snapshot,
            safe_project,
            dict(cumulative_files),
            "import sys\nsys.exit(1)",
            tuple(safe_project.regression_command),
            label="baseline",
        )
        baseline = normalize_snapshot_verification(baseline_raw, bounds.max_evidence_chars)
        result.baseline_verification = baseline
        if not baseline.fresh_target or baseline.regression.exit_code != 0:
            raise SandboxError("Original project failed its preserved regression command.")

        await log("system", "[phase baseline] Original-project normal-input checks passed.")

        for round_index in range(requested_cycles * passes_per_cycle):
            cycle = round_index // passes_per_cycle + 1
            pass_number = round_index % passes_per_cycle + 1
            if named_profile:
                agents.configure_review(
                    profile_key=profile_key,
                    cycle=cycle,
                    pass_number=pass_number,
                    red_agents=red_agents,
                    blue_agents=blue_agents,
                )
            await log(
                "red",
                f"[phase red review] Cycle {cycle}/{requested_cycles}, "
                f"pass {pass_number}/{passes_per_cycle}: "
                "reviewing the cumulative verified snapshot.",
            )
            try:
                if named_profile and profile_key == "ultra_heavy":
                    await log("red", chatter("leader_red", n=red_agents, seed=cycle))
                    await log("blue", chatter("leader_blue", n=blue_agents, seed=cycle))
                else:
                    await log(
                        "red",
                        chatter(
                            "red_start",
                            persona=red_persona(1).name,
                            path="",
                            seed=cycle * 10 + pass_number,
                        ),
                    )
            except Exception:
                pass
            documents = documents_from_mapping(cumulative_files)
            red = await agents.analyze_red(
                documents,
                project_name=safe_project.name,
                cycle=cycle,
                max_batch_bytes=bounds.max_batch_bytes,
                contract=safe_project.contract
                + (f"\n\nGrounded intel:\n{project_digest}" if project_digest else ""),
                total_paths=snapshot_total_paths,
                total_bytes=snapshot_total_bytes,
                omitted_paths=omitted_paths,
                coverage_notes=coverage_notes,
                max_payload_bytes=payload_budget,
                prior_verified_history=verified_history,
            )
            result.context_coverage.append(red.coverage)
            evidence = CycleEvidence(red=red)
            if red.report.outcome == "no_finding":
                final = await agents.final_blue_report(
                    project_name=safe_project.name,
                    cycle=cycle,
                    contract=safe_project.contract,
                    max_payload_bytes=payload_budget,
                    stage_evidence={
                        "red_report": red.report.model_dump(),
                        "coverage": red.coverage.model_dump(),
                        "disposition": "no_change",
                    },
                )
                evidence.final_blue_report = final
                result.cycle_reports.append(
                    ProjectCycleReport(
                        cycle=cycle,
                        pass_number=pass_number,
                        status="no_finding",
                        message="The bounded review produced no testable finding; this is not a security guarantee.",
                        evidence=evidence,
                    )
                )
                result.cycles_completed += int(pass_number == passes_per_cycle)
                if named_profile:
                    continue
                break

            unknown_paths = sorted(set(red.report.affected_paths) - set(cumulative_files))
            if unknown_paths:
                raise ProjectWorkflowError("Red report referenced paths outside the safe snapshot.")

            await log(
                "red",
                f"[phase verify] Cycle {cycle}/{requested_cycles} "
                f"pass {pass_number}/{passes_per_cycle}: "
                "proving the finding before requesting changes.",
            )
            pre_raw = await blocking(
                sandbox.verify_project_snapshot,
                safe_project,
                dict(cumulative_files),
                red.report.verification_script_python,
                tuple(safe_project.regression_command),
                label=f"cycle-{cycle}-pass-{pass_number}-pre"
                if named_profile
                else f"cycle-{cycle}-pre",
            )
            pre = normalize_snapshot_verification(pre_raw, bounds.max_evidence_chars)
            evidence.pre_verification = pre
            if not pre.fresh_target:
                raise SandboxError("Pre-verification did not use a fresh target.")
            if pre.regression.exit_code != 0:
                raise SandboxError(
                    "The cumulative snapshot failed the original regression command."
                )
            if pre.probe.inconclusive:
                final = await agents.final_blue_report(
                    project_name=safe_project.name,
                    cycle=cycle,
                    contract=safe_project.contract,
                    max_payload_bytes=payload_budget,
                    stage_evidence={
                        "red_report": red.report.model_dump(),
                        "pre_verification": pre.model_dump(),
                        "disposition": "no_change",
                    },
                )
                evidence.final_blue_report = final
                result.cycle_reports.append(
                    ProjectCycleReport(
                        cycle=cycle,
                        pass_number=pass_number,
                        status="inconclusive",
                        message="The pre-change probe was inconclusive; no changes were requested.",
                        evidence=evidence,
                    )
                )
                result.cycles_completed += int(pass_number == passes_per_cycle)
                if named_profile:
                    continue
                break
            if pre.probe.blocked:
                final = await agents.final_blue_report(
                    project_name=safe_project.name,
                    cycle=cycle,
                    contract=safe_project.contract,
                    max_payload_bytes=payload_budget,
                    stage_evidence={
                        "red_report": red.report.model_dump(),
                        "pre_verification": pre.model_dump(),
                        "disposition": "no_change",
                    },
                )
                evidence.final_blue_report = final
                result.cycle_reports.append(
                    ProjectCycleReport(
                        cycle=cycle,
                        pass_number=pass_number,
                        status="not_confirmed",
                        message="The original probe did not confirm the reported vulnerability; no changes were requested.",
                        evidence=evidence,
                    )
                )
                result.cycles_completed += int(pass_number == passes_per_cycle)
                if named_profile:
                    continue
                break

            try:
                await log(
                    "red",
                    chatter(
                        "red_proof",
                        persona=red_persona((round_index % 5) + 1).name,
                        path=(red.report.affected_paths[0] if red.report.affected_paths else ""),
                        code=pre.probe.exit_code,
                        seed=cycle * 100 + pass_number,
                    ),
                )
            except Exception:
                pass
            await log(
                "blue",
                f"[phase blue patch] Cycle {cycle}/{requested_cycles} "
                f"pass {pass_number}/{passes_per_cycle}: "
                "requesting bounded sanitation-only replacements.",
            )
            proposal = await agents.propose_blue(
                documents,
                project_name=safe_project.name,
                cycle=cycle,
                red_report=red.report,
                pre_verification=pre.model_dump(),
                contract=safe_project.contract,
                protected_paths=protected_paths,
                max_changed_files=bounds.max_changed_files,
                max_changed_bytes=bounds.max_changed_bytes,
                max_payload_bytes=payload_budget,
            )
            evidence.blue_proposal = proposal
            validation, replacements = validate_replacements(
                proposal,
                cumulative_files,
                max_changed_files=bounds.max_changed_files,
                max_changed_bytes=bounds.max_changed_bytes,
                protected_paths=protected_paths,
            )
            evidence.replacement_validation = validation
            if not validation.accepted:
                final = await agents.final_blue_report(
                    project_name=safe_project.name,
                    cycle=cycle,
                    contract=safe_project.contract,
                    max_payload_bytes=payload_budget,
                    stage_evidence={
                        "red_report": red.report.model_dump(),
                        "pre_verification": pre.model_dump(),
                        "proposal": proposal_report_evidence(proposal),
                        "replacement_validation": validation.model_dump(),
                        "disposition": "rolled_back",
                    },
                )
                evidence.final_blue_report = final
                result.cycle_reports.append(
                    ProjectCycleReport(
                        cycle=cycle,
                        pass_number=pass_number,
                        status="rolled_back",
                        message=validation.reason,
                        evidence=evidence,
                    )
                )
                result.cycles_completed += int(pass_number == passes_per_cycle)
                continue

            candidate_files = dict(cumulative_files)
            candidate_files.update(replacements)
            candidate_diff = render_diff(cumulative_files, candidate_files, bounds.max_diff_chars)
            await log(
                "system",
                f"[phase verify] Cycle {cycle}/{requested_cycles} pass {pass_number}/{passes_per_cycle}: "
                "verifying a fresh target with the original probe and regression command.",
            )
            patched_raw = await blocking(
                sandbox.verify_project_snapshot,
                safe_project,
                candidate_files,
                red.report.verification_script_python,
                tuple(safe_project.regression_command),
                label=f"cycle-{cycle}-pass-{pass_number}-patched"
                if named_profile
                else f"cycle-{cycle}-patched",
            )
            patched = normalize_snapshot_verification(patched_raw, bounds.max_evidence_chars)
            evidence.patched_verification = patched
            evidence.differential_passed = differential_passed(
                result.baseline_verification.regression.exit_code
                if result.baseline_verification is not None
                else None,
                patched.regression.exit_code,
            )
            if not patched.fresh_target:
                raise SandboxError("Patched verification did not use a fresh target.")

            independent_red: RedAnalysisArtifacts | None = None
            independent_same_finding = False
            if patched.probe.blocked and patched.regression.exit_code == 0:
                independent_red = await agents.analyze_red(
                    documents_from_mapping(candidate_files),
                    project_name=safe_project.name,
                    cycle=cycle,
                    phase="verification",
                    max_batch_bytes=bounds.max_batch_bytes,
                    contract=safe_project.contract,
                    total_paths=snapshot_total_paths,
                    total_bytes=snapshot_total_bytes,
                    omitted_paths=omitted_paths,
                    coverage_notes=coverage_notes,
                    max_payload_bytes=payload_budget,
                    prior_verified_history=verified_history,
                )
                evidence.independent_red = independent_red
                result.context_coverage.append(independent_red.coverage)
                if independent_red.report.outcome == "finding":
                    independent_same_finding = (
                        independent_red.report.vulnerability.strip().casefold()
                        == red.report.vulnerability.strip().casefold()
                    )
                    if independent_same_finding:
                        independent_raw = await blocking(
                            sandbox.verify_project_snapshot,
                            safe_project,
                            candidate_files,
                            independent_red.report.verification_script_python,
                            tuple(safe_project.regression_command),
                            label=(
                                f"cycle-{cycle}-pass-{pass_number}-independent-red"
                                if named_profile
                                else f"cycle-{cycle}-independent-red"
                            ),
                        )
                        evidence.independent_verification = normalize_snapshot_verification(
                            independent_raw, bounds.max_evidence_chars
                        )

            retained = (
                patched.probe.blocked
                and patched.regression.exit_code == 0
                and not patched.probe.inconclusive
                # Explicit differential gate: equivalent to the already-required
                # (baseline exit 0 via the L895 raise + patched exit 0 above), so it
                # changes no retain/rollback verdict — it only records the check.
                and evidence.differential_passed
                # Wave 8 R1 fail-closed property gate: a recorded properties
                # exit other than 0 vetoes the retain even when the probe is
                # blocked and regression is green (properties None skips).
                and property_gate_passed(patched)
                # SPEC 14.8 item 4 fail-closed mutation gate: a recorded
                # mutations exit other than 0 vetoes the retain even when the
                # probe is blocked and regression is green (mutations None
                # skips, e.g. arbitrary projects and other lanes' fixtures).
                and mutation_gate_passed(patched)
            )
            if independent_same_finding:
                independent_check = evidence.independent_verification
                retained = bool(
                    retained
                    and independent_check is not None
                    and independent_check.fresh_target
                    and independent_check.probe.blocked
                    and independent_check.regression.exit_code == 0
                    and property_gate_passed(independent_check)
                    and mutation_gate_passed(independent_check)
                )
            disposition = "retained" if retained else "rolled_back"
            try:
                await log(
                    "blue",
                    chatter(
                        "blue_done",
                        persona=blue_persona((round_index % 5) + 1).name,
                        path=(sorted(replacements)[0] if retained and replacements else ""),
                        code=patched.probe.exit_code,
                        seed=cycle * 1000 + pass_number,
                    ),
                )
            except Exception:
                pass
            stage_evidence = {
                "red_report": red.report.model_dump(),
                "pre_verification": pre.model_dump(),
                "proposal": proposal_report_evidence(proposal),
                "replacement_validation": validation.model_dump(),
                "patched_verification": patched.model_dump(),
                "independent_red": (
                    {
                        "report": independent_red.report.model_dump(),
                        "coverage": independent_red.coverage.model_dump(),
                        "same_finding": independent_same_finding,
                    }
                    if independent_red
                    else None
                ),
                "independent_verification": (
                    evidence.independent_verification.model_dump()
                    if evidence.independent_verification
                    else None
                ),
                "candidate_diff": candidate_diff,
                "disposition": disposition,
                "semantic_guarantee": False,
            }
            final = await agents.final_blue_report(
                project_name=safe_project.name,
                cycle=cycle,
                contract=safe_project.contract,
                max_payload_bytes=payload_budget,
                stage_evidence=stage_evidence,
            )
            evidence.final_blue_report = final
            if final.disposition != disposition:
                raise ProjectWorkflowError("Final blue report contradicted observed disposition.")

            if retained:
                cumulative_files = candidate_files
                verified_history.append(
                    {
                        "cycle": cycle,
                        "pass_number": pass_number,
                        "vulnerability": red.report.vulnerability,
                        "changed_paths": sorted(replacements),
                        "pre_probe_exit": pre.probe.exit_code,
                        "post_probe_exit": patched.probe.exit_code,
                        "regression_exit": patched.regression.exit_code,
                    }
                )
                status = "retained"
                message = (
                    "Candidate replacements were retained after the same probe was blocked on a fresh "
                    "target and the original regression command passed; no general security claim is made."
                )
            else:
                status = "rolled_back"
                message = (
                    "Candidate replacements were rolled back because the same probe was not blocked or "
                    "the original regression command did not pass."
                )
            receipt = None
            if retained:
                receipt = build_cycle_receipt(
                    fixture=safe_project.name,
                    pre=pre,
                    patched=patched,
                    baseline_regression_exit=(
                        result.baseline_verification.regression.exit_code
                        if result.baseline_verification is not None
                        else 2
                    ),
                    differential_passed=evidence.differential_passed,
                    candidate_diff=candidate_diff,
                )
            result.cycle_reports.append(
                ProjectCycleReport(
                    cycle=cycle,
                    pass_number=pass_number,
                    status=status,
                    message=message,
                    changed_paths=sorted(replacements) if retained else [],
                    diff=candidate_diff,
                    receipt=receipt,
                    evidence=evidence,
                )
            )
            result.cycles_completed += int(pass_number == passes_per_cycle)

        statuses = [report.status for report in result.cycle_reports]
        if statuses and all(status == "no_finding" for status in statuses):
            result.status = "no_findings"
            result.message = "The bounded review produced no testable finding; this is not a general security claim."
        elif "retained" in statuses and not any(
            status in ("rolled_back", "not_confirmed", "inconclusive", "error")
            for status in statuses
        ):
            result.status = "verified"
            result.message = "Evidence-gated candidate replacements were retained. Review the reports and diff manually."
        else:
            result.status = "partial"
            result.message = "The workflow completed without a fully verified outcome; review rollbacks and evidence."
    except asyncio.CancelledError:
        raise
    except (ConfigurationError, AgentError, ProjectWorkflowError, SandboxError, ValueError) as exc:
        result.status = "error"
        result.message = str(exc)
    except Exception as exc:
        result.status = "error"
        result.message = (
            f"Project workflow failed ({type(exc).__name__}); no unverified changes retained."
        )
    finally:
        result.cumulative_diff = render_diff(
            original_files, cumulative_files, bounds.max_diff_chars
        )
        result.research_records = project_records
        try:
            if sandbox is not None:
                result.cleanup.attempted = True
                await log(
                    "system",
                    "[phase cleanup] Removing project session containers, snapshots, and network.",
                )
                try:
                    await blocking(sandbox.close)
                except Exception as exc:
                    result.cleanup.succeeded = False
                    result.cleanup.error = (
                        str(exc)
                        if isinstance(exc, SandboxError)
                        else "Docker cleanup failed; inspect session resources."
                    )
                    result.status = "error"
                    result.message = result.cleanup.error
        finally:
            if muse is not None:
                calls = getattr(muse, "usage", None)
                if isinstance(calls, list):
                    result.usage = ScanUsage(calls=calls)
                    result.total_tokens = result.usage.total_tokens
                    result.total_cost_usd = result.usage.cost_usd
                try:
                    await muse.aclose()
                except Exception:
                    pass
    await log(
        "system",
        f"[done] {result.cycles_completed}/{requested_cycles} cycles complete: {result.message}",
    )
    return result


from modules.shared.sms_redact import EXPLOIT_REDACTED as EXPLOIT_REDACTED  # noqa: E402 (re-export shim; canonical defs live in sms_redact)
from modules.shared.sms_redact import redact_cycle_evidence as redact_cycle_evidence  # noqa: E402,F401 (re-export; canonical def lives in sms_redact)
from modules.shared.sms_redact import redact_project_result as _redact_project  # noqa: E402 (re-export shim; canonical defs live in sms_redact)


def redact_report_for_user(result: "ProjectWorkflowResult") -> dict:
    """Return a user-safe report: patched code only, no exploit scripts or payloads."""
    return _redact_project(result)
