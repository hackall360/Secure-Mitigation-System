# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import asyncio
import hashlib
import threading
from collections import deque

import pytest

from agents import AgentError
from config import PurpleBoxConfig
from pricing import CallUsage
from project_agents import (
    BlueProposal,
    FileReplacement,
    FinalBlueReport,
    ProjectAgentRunner,
    RedBatchEvidence,
    RedCandidate,
    RedReport,
    SourceDocument,
    build_source_batches,
)
from project_workflow import (
    ExecutionEvidence,
    ProjectWorkflowInput,
    ProjectWorkflowLimits,
    SnapshotVerification,
    execute_project_workflow,
    protected_regression_paths,
    validate_replacements,
)
from projects import ProjectSpec


async def silent_emit(_team, _message):
    return None


def verification(probe: int, regression: int = 0, output: str = "evidence"):
    return SnapshotVerification(
        probe=ExecutionEvidence(exit_code=probe, output=output),
        regression=ExecutionEvidence(exit_code=regression, output="regression"),
        fresh_target=True,
    )


class FakeMuse:
    def __init__(self, *, red_outcomes=None, invalid_path=None, no_replacements=False):
        self.red_outcomes = deque(red_outcomes or ["finding", "no_finding"])
        self.invalid_path = invalid_path
        self.no_replacements = no_replacements
        self.calls = []
        self.closed = False
        self.usage = [
            CallUsage(
                role="seed",
                model="muse-spark-1.3",
                prompt_tokens=7,
                completion_tokens=3,
                cost_usd=0.001,
            )
        ]

    async def _request(self, model, system, payload, schema, role=""):
        self.calls.append(
            {"model": model, "system": system, "payload": payload, "schema": schema, "role": role}
        )
        assert "messages" not in payload and "conversation" not in payload
        if schema is RedBatchEvidence:
            path = payload["batch"]["chunks"][0]["path"]
            return RedBatchEvidence(
                candidates=[
                    RedCandidate(
                        vulnerability="injection",
                        affected_paths=[path],
                        evidence="untrusted input reaches a sink",
                        verification_script_python="import sys\nsys.exit(0)",
                        confidence="high",
                    )
                ],
                observations=["reviewed supplied chunk only"],
            )
        if schema is RedReport:
            outcome = self.red_outcomes.popleft() if self.red_outcomes else "no_finding"
            if outcome == "no_finding":
                return RedReport(
                    outcome="no_finding",
                    analysis_summary="No testable finding in the supplied bounded context.",
                    limitations=["Not a general security claim."],
                )
            evidence_items = payload["evidence_digests"]
            candidate = evidence_items[0]["candidates"][0]
            return RedReport(
                outcome="finding",
                vulnerability=candidate["vulnerability"],
                affected_paths=candidate["affected_paths"],
                analysis_summary="A concrete testable input boundary was identified.",
                verification_script_python=candidate["verification_script_python"],
                limitations=["Only supplied source was reviewed."],
            )
        if schema is BlueProposal:
            selected = payload["safe_snapshot_files"]
            if self.no_replacements:
                return BlueProposal(strategy="Evidence was insufficient.", replacements=[])
            source = selected[0]
            path = self.invalid_path or source["path"]
            return BlueProposal(
                strategy="Add a bounded input validation guard without changing business behavior.",
                replacements=[
                    FileReplacement(
                        path=path,
                        original_sha256=source["sha256"],
                        replacement_content=source["content"] + "\n# validated input\n",
                        rationale="Reject malformed input before it reaches the sink.",
                        change_kind="input_validation",
                    )
                ],
                limitations=["Semantic correctness still requires human review."],
            )
        if schema is FinalBlueReport:
            disposition = payload["stage_evidence"]["disposition"]
            return FinalBlueReport(
                disposition=disposition,
                summary="Report reflects only observed probe and regression evidence.",
                evidence=["stage artifacts supplied independently"],
                changed_paths=[],
                limitations=["The project is not labeled secure."],
            )
        raise AssertionError(f"Unexpected response schema: {schema}")

    async def aclose(self):
        self.closed = True


class FakeSandbox:
    def __init__(self, outcomes=()):
        self.outcomes = iter(outcomes)
        self.calls = []
        self.closed = False
        self.required = False

    def require_base_images(self):
        self.required = True

    def verify_project_snapshot(
        self, project, files, verification_script_python, regression_command, *, label
    ):
        self.calls.append(
            {
                "project": project,
                "files": dict(files),
                "probe": verification_script_python,
                "regression_command": tuple(regression_command),
                "label": label,
            }
        )
        return next(self.outcomes)

    def close(self):
        self.closed = True


PROJECT = ProjectWorkflowInput(
    name="demo",
    files={"src/app.py": "value = input()\nprint(value)\n"},
    regression_command=["pytest", "-q"],
)
CONFIG = PurpleBoxConfig(meta_api_key="unit-test-key")


async def run_workflow(*, muse, sandbox, cycles=1, project=PROJECT, limits=None):
    result = await execute_project_workflow(
        project,
        silent_emit,
        cycles=cycles,
        config=CONFIG,
        limits=limits,
        sandbox_factory=lambda _settings: sandbox,
        muse_factory=lambda _settings: muse,
    )
    assert muse.closed and sandbox.closed
    return result


def test_bounded_batches_cover_every_utf8_byte_without_silent_truncation():
    content = ("abc😀\n" * 450) + "tail"
    documents = [SourceDocument(path="src/large.py", content=content)]
    batches, coverage = build_source_batches(documents, max_batch_bytes=1024)
    chunks = [chunk for batch in batches for chunk in batch.chunks]
    assert b"".join(chunk.content.encode() for chunk in chunks) == content.encode()
    assert all(batch.source_bytes <= 1024 for batch in batches)
    assert coverage.complete
    assert coverage.covered_bytes == coverage.total_bytes == len(content.encode())
    assert chunks[0].start_byte == 0 and chunks[-1].end_byte == len(content.encode())


async def test_agent_calls_are_fresh_stateless_and_reports_are_separate_calls():
    muse = FakeMuse(red_outcomes=["finding"])
    runner = ProjectAgentRunner(muse, CONFIG)
    documents = [
        SourceDocument(path="a.py", content="a" * 900),
        SourceDocument(path="b.py", content="b" * 900),
    ]
    artifacts = await runner.analyze_red(
        documents, project_name="demo", cycle=1, max_batch_bytes=1024
    )
    assert artifacts.coverage.complete and artifacts.coverage.batches == 2
    assert len(muse.calls) == 3
    assert [call["role"] for call in muse.calls] == [
        "project_red_initial_evidence_cycle_1_batch_0",
        "project_red_initial_evidence_cycle_1_batch_1",
        "project_red_initial_report_cycle_1",
    ]
    assert "batch" in muse.calls[0]["payload"]
    assert "batch" not in muse.calls[-1]["payload"]
    assert "evidence_digests" in muse.calls[-1]["payload"]
    assert all("response_schema" in call["payload"] for call in muse.calls)
    assert len({id(call["payload"]) for call in muse.calls}) == 3


async def test_complete_cycle_retains_only_verified_candidate_and_preserves_source():
    original = dict(PROJECT.files)
    muse = FakeMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeSandbox([verification(1), verification(0), verification(1)])
    result = await run_workflow(muse=muse, sandbox=sandbox)

    assert result.success and result.status == "verified"
    assert result.cycle_reports[0].status == "retained"
    assert result.cycle_reports[0].evidence.independent_red is not None
    assert "validated input" in result.cumulative_diff
    assert PROJECT.files == original
    assert [call["probe"] for call in sandbox.calls] == [
        "import sys\nsys.exit(1)",
        "import sys\nsys.exit(0)",
        "import sys\nsys.exit(0)",
    ]
    assert all(call["regression_command"] == ("pytest", "-q") for call in sandbox.calls)
    assert sandbox.calls[0]["files"] == original
    assert sandbox.calls[1]["files"] == original
    assert "validated input" in sandbox.calls[2]["files"]["src/app.py"]
    dumped = result.model_dump()
    assert dumped["success"] is True
    assert dumped["total_tokens"] == 10 and dumped["total_cost_usd"] == 0.001
    assert dumped["cleanup"]["succeeded"] is True


async def test_failed_patch_is_rolled_back_and_not_carried_into_next_cycle():
    muse = FakeMuse(red_outcomes=["finding", "finding", "no_finding"])
    sandbox = FakeSandbox(
        [
            verification(1),
            verification(0),
            verification(0),
            verification(0),
            verification(1),
        ]
    )
    result = await run_workflow(muse=muse, sandbox=sandbox, cycles=2)
    assert [report.status for report in result.cycle_reports] == ["rolled_back", "retained"]
    assert sandbox.calls[3]["files"] == PROJECT.files
    assert result.cumulative_diff.count("validated input") == 1


async def test_multiple_verified_cycles_carry_cumulative_snapshot_only():
    muse = FakeMuse(red_outcomes=["finding", "no_finding", "finding", "no_finding"])
    sandbox = FakeSandbox(
        [verification(1), verification(0), verification(1), verification(0), verification(1)]
    )
    result = await run_workflow(muse=muse, sandbox=sandbox, cycles=2)
    assert [report.status for report in result.cycle_reports] == ["retained", "retained"]
    assert sandbox.calls[3]["files"]["src/app.py"].count("validated input") == 1
    assert sandbox.calls[4]["files"]["src/app.py"].count("validated input") == 2
    assert result.cumulative_diff.count("validated input") == 2


@pytest.mark.parametrize("invalid_path", ["../escape.py", "/absolute.py", "new.py"])
async def test_invalid_or_non_snapshot_replacement_paths_are_rejected(invalid_path):
    muse = FakeMuse(red_outcomes=["finding"], invalid_path=invalid_path)
    sandbox = FakeSandbox([verification(1), verification(0)])
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert not result.success and result.status == "partial"
    assert result.cycle_reports[0].status == "rolled_back"
    assert result.cumulative_diff == ""
    assert len(sandbox.calls) == 2


async def test_no_finding_generates_fresh_final_report_without_touching_sandbox_target():
    muse = FakeMuse(red_outcomes=["no_finding"])
    sandbox = FakeSandbox([verification(1)])
    result = await run_workflow(muse=muse, sandbox=sandbox, cycles=5)
    assert result.success and result.status == "no_findings" and result.cycles_completed == 1
    assert result.cycle_reports[0].status == "no_finding"
    assert len(sandbox.calls) == 1
    assert any(call["role"] == "project_blue_final_report_cycle_1" for call in muse.calls)


async def test_context_and_report_limits_are_explicit():
    large_project = ProjectWorkflowInput(
        name="large",
        files={"src/app.py": "x" * 2500},
        regression_command=["python", "-m", "pytest"],
    )
    muse = FakeMuse(red_outcomes=["finding"])
    sandbox = FakeSandbox(
        [
            verification(1),
            verification(0, output="e" * 5000),
            verification(0, output="p" * 5000),
        ]
    )
    limits = ProjectWorkflowLimits(
        max_batch_bytes=1024,
        max_changed_files=2,
        max_changed_bytes=10_000,
        max_evidence_chars=1000,
        max_diff_chars=1000,
    )
    result = await run_workflow(muse=muse, sandbox=sandbox, project=large_project, limits=limits)
    coverage = result.context_coverage[0]
    assert coverage.batches == 3 and coverage.covered_bytes == 2500 and coverage.complete
    pre_output = result.cycle_reports[0].evidence.pre_verification.probe.output
    assert "report limit reached" in pre_output
    assert len(pre_output) < 1100


async def test_cancellation_waits_for_in_flight_verification_and_cleans_up():
    started, release = threading.Event(), threading.Event()
    muse = FakeMuse(red_outcomes=["finding"])
    sandbox = FakeSandbox()

    def verify_project_snapshot(*args, **kwargs):
        started.set()
        assert release.wait(timeout=5)
        return verification(0)

    sandbox.verify_project_snapshot = verify_project_snapshot
    task = asyncio.create_task(
        execute_project_workflow(
            PROJECT,
            silent_emit,
            config=CONFIG,
            sandbox_factory=lambda _settings: sandbox,
            muse_factory=lambda _settings: muse,
        )
    )
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sandbox.closed and muse.closed


async def test_cleanup_failure_prevents_success():
    muse = FakeMuse(red_outcomes=["no_finding"])
    sandbox = FakeSandbox()

    def close():
        sandbox.closed = True
        raise RuntimeError("boom")

    sandbox.close = close
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert not result.success and not result.cleanup.succeeded
    assert result.status == "error"


async def test_independent_red_same_finding_must_also_be_blocked_or_patch_rolls_back():
    muse = FakeMuse(red_outcomes=["finding", "finding"])
    sandbox = FakeSandbox([verification(1), verification(0), verification(1), verification(0)])
    result = await run_workflow(muse=muse, sandbox=sandbox)
    report = result.cycle_reports[0]
    assert report.status == "rolled_back"
    assert report.evidence.independent_verification.probe.exit_code == 0
    assert result.cumulative_diff == "" and result.status == "partial"


def test_common_and_explicit_regression_paths_are_never_replaceable():
    paths = ["src/app.py", "tests/test_app.py", "web/app.spec.js", "fixtures/golden.json"]
    protected = protected_regression_paths(paths, ["pytest", "fixtures/golden.json"])
    assert protected == ["fixtures/golden.json", "tests/test_app.py", "web/app.spec.js"]
    content = "assert True\n"
    proposal = BlueProposal(
        strategy="bad",
        replacements=[
            FileReplacement(
                path="tests/test_app.py",
                original_sha256=hashlib.sha256(content.encode()).hexdigest(),
                replacement_content="assert True  # bypassed\n",
                rationale="not allowed",
                change_kind="input_validation",
            )
        ],
    )
    validation, replacements = validate_replacements(
        proposal,
        {"tests/test_app.py": content},
        max_changed_files=2,
        max_changed_bytes=10_000,
        protected_paths=protected,
    )
    assert not validation.accepted and not replacements
    assert "protected regression-test" in validation.reason


async def test_project_spec_path_is_never_hosted_and_contract_is_sent(tmp_path):
    (tmp_path / "app.py").write_text("print(input())\n", encoding="utf-8")
    spec = ProjectSpec(
        path=tmp_path,
        command=["python", "app.py"],
        test_command=["python", "-m", "pytest"],
        contract="HTTP service listens on port 8080 as target-service.",
        allow_remote_inference=True,
    )
    muse = FakeMuse(red_outcomes=["no_finding"])
    sandbox = FakeSandbox([verification(1)])
    result = await execute_project_workflow(
        spec,
        silent_emit,
        config=CONFIG,
        sandbox_factory=lambda _settings: sandbox,
        muse_factory=lambda _settings: muse,
    )
    assert result.project == tmp_path.name and result.status == "no_findings"
    serialized_payloads = "\n".join(str(call["payload"]) for call in muse.calls)
    assert str(tmp_path) not in serialized_payloads
    assert spec.contract in serialized_payloads
    assert all(call["payload"]["project"] == tmp_path.name for call in muse.calls)


async def test_full_payload_budget_fails_closed_without_truncating_contract_or_source():
    muse = FakeMuse(red_outcomes=["finding"])
    runner = ProjectAgentRunner(muse, CONFIG)
    with pytest.raises(AgentError, match="no content was silently truncated"):
        await runner.analyze_red(
            [SourceDocument(path="src/app.py", content="x" * 4096)],
            project_name="demo",
            cycle=1,
            contract="contract-data-" * 2000,
            max_batch_bytes=1024,
            max_payload_bytes=16_384,
        )
    assert muse.calls == []


async def test_blue_never_receives_protected_test_source_as_patchable_context():
    muse = FakeMuse()
    runner = ProjectAgentRunner(muse, CONFIG)
    report = RedReport(
        outcome="finding",
        vulnerability="test bypass",
        affected_paths=["tests/test_app.py"],
        analysis_summary="The reported issue is in a protected regression file.",
        verification_script_python="import sys\nsys.exit(0)",
    )
    proposal = await runner.propose_blue(
        [SourceDocument(path="tests/test_app.py", content="assert True\n")],
        project_name="demo",
        cycle=1,
        red_report=report,
        pre_verification={"probe": {"exit_code": 0}},
        contract="tests are evidence only",
        protected_paths=["tests/test_app.py"],
        max_changed_files=2,
        max_changed_bytes=10_000,
    )
    assert proposal.replacements == []
    assert muse.calls == []
    assert "never model-replaceable" in proposal.limitations[0]


async def test_project_spec_requires_remote_inference_consent_before_external_setup(tmp_path):
    (tmp_path / "app.py").write_text("print('safe')\n", encoding="utf-8")
    spec = ProjectSpec(
        path=tmp_path,
        command=["python", "app.py"],
        test_command=["python", "-m", "pytest"],
        contract="Local test project.",
        allow_remote_inference=False,
    )

    def forbidden(_settings):
        raise AssertionError("External clients must not be created without consent")

    result = await execute_project_workflow(
        spec,
        silent_emit,
        config=CONFIG,
        sandbox_factory=forbidden,
        muse_factory=forbidden,
    )
    assert result.status == "error" and not result.success
    assert "Remote inference consent" in result.message
    assert not result.cleanup.attempted


def test_cycles_are_bounded_before_external_resources_are_created():
    with pytest.raises(ValueError, match="between 1 and 20"):
        asyncio.run(execute_project_workflow(PROJECT, silent_emit, cycles=21, config=CONFIG))


def test_project_input_rejects_unsafe_source_paths():
    with pytest.raises(ValueError):
        ProjectWorkflowInput(name="bad", files={"../secret": "x"}, regression_command=["pytest"])


def test_replacement_hash_binds_proposal_to_current_snapshot():
    original = "safe"
    replacement = FileReplacement(
        path="app.py",
        original_sha256=hashlib.sha256(original.encode()).hexdigest(),
        replacement_content="safer",
        rationale="validate",
        change_kind="input_validation",
    )
    assert replacement.original_sha256 != hashlib.sha256(b"changed concurrently").hexdigest()


async def test_local_project_does_not_require_remote_consent(tmp_path):
    (tmp_path / "app.py").write_text("print('safe')\n", encoding="utf-8")
    spec = ProjectSpec(
        path=tmp_path,
        command=["python", "app.py"],
        test_command=["python", "-m", "unittest"],
        contract="Local test project.",
    )
    reached_sandbox = []

    def sandbox(settings):
        reached_sandbox.append(settings.inference_mode)
        raise RuntimeError("local sandbox reached")

    result = await execute_project_workflow(
        spec,
        silent_emit,
        config=PurpleBoxConfig(inference_mode="local", meta_base_url="http://127.0.0.1:8081/v1"),
        sandbox_factory=sandbox,
    )
    assert reached_sandbox == ["local"]
    assert "Remote inference consent" not in result.message


async def test_original_baseline_is_exported_as_observed_evidence():
    sandbox = FakeSandbox([verification(1)])
    result = await execute_project_workflow(
        PROJECT,
        silent_emit,
        config=CONFIG,
        sandbox_factory=lambda _: sandbox,
        muse_factory=lambda _: FakeMuse(red_outcomes=["no_finding"]),
    )
    assert result.baseline_verification is not None
    assert result.baseline_verification.regression.exit_code == 0
    assert result.model_dump()["baseline_verification"]["fresh_target"] is True


async def test_project_research_on_runs_grounding_and_stores_records(monkeypatch):
    """H5: opt-in project intel grounds the red contract and lands on the report."""
    import project_workflow as _pw
    import workflow as _workflow

    async def fake_gather(muse, settings, filename, contract, log):
        await log("research", "fake intel pass")
        return "Grounded attack patterns: fake", [
            {"source": "circl", "cve_id": "CVE-9-TEST", "title": "t", "summary": "s",
             "severity": "HIGH", "cvss": 9.0, "cwe": ["CWE-78"]}
        ]

    monkeypatch.setattr(_workflow, "_gather_research", fake_gather)

    seen_contracts = []
    muse = FakeMuse(red_outcomes=["no_finding"])
    orig_analyze = ProjectAgentRunner.analyze_red

    async def observing(self, documents, **kwargs):
        seen_contracts.append(kwargs.get("contract", ""))
        return await orig_analyze(self, documents, **kwargs)

    monkeypatch.setattr(ProjectAgentRunner, "analyze_red", observing)
    sandbox = FakeSandbox([verification(1)])
    result = await execute_project_workflow(
        PROJECT,
        silent_emit,
        config=PurpleBoxConfig(meta_api_key="unit-test-key", research_enabled=True),
        sandbox_factory=lambda _: sandbox,
        muse_factory=lambda _: muse,
    )
    assert result.status == "no_findings"
    assert len(result.research_records) == 1
    assert result.research_records[0]["cve_id"] == "CVE-9-TEST"
    assert any("Grounded intel" in c for c in seen_contracts)


async def test_project_research_off_by_default_stores_nothing():
    """H5: default config runs zero intel and keeps the report clean."""
    muse = FakeMuse(red_outcomes=["no_finding"])
    sandbox = FakeSandbox([verification(1)])
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert result.research_records == []
