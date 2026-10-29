# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Consolidated unit-test doubles for fixture and project workflow tests.

Shared fakes live here so tests/test_workflow.py, tests/test_project_workflow.py,
and tests/test_cycle_profiles_workflow.py do not drift apart. Per-file quirks
stay available as constructor/run parameters rather than forked classes.
"""

from collections import deque

from modules.core.config import PurpleBoxConfig

TEST_API_KEY = "unit-test-key"
TEST_CONFIG = PurpleBoxConfig(meta_api_key=TEST_API_KEY)


async def silent_emit(_team, _message):
    """Event sink for workflow tests that need no UI traffic."""
    return None


def project_verification(probe: int, regression: int = 0, output: str = "evidence"):
    """Build a fresh-target project SnapshotVerification for a FakeProjectSandbox."""
    from modules.workflows.project_workflow import ExecutionEvidence, SnapshotVerification

    return SnapshotVerification(
        probe=ExecutionEvidence(exit_code=probe, output=output),
        regression=ExecutionEvidence(exit_code=regression, output="regression"),
        fresh_target=True,
    )


class FakeProjectMuse:
    """Stateless-role project agent double (union of per-file quirks as params)."""

    def __init__(self, *, red_outcomes=None, invalid_path=None, no_replacements=False):
        from modules.core.pricing import CallUsage

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
        from modules.services.project_agents import (
            BlueProposal,
            FileReplacement,
            FinalBlueReport,
            RedBatchEvidence,
            RedCandidate,
            RedReport,
        )

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


class FakeProjectSandbox:
    """Project snapshot verifier with scripted SnapshotVerification outcomes."""

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


async def run_project_workflow(*, muse, sandbox, cycles=1, project=None, limits=None, config=None):
    """Execute the project workflow with fakes and assert both halves closed.

    ``project`` defaults to the shared demo input so call sites can omit it.
    """
    from modules.workflows.project_workflow import ProjectWorkflowInput, execute_project_workflow

    if project is None:
        project = ProjectWorkflowInput(
            name="demo",
            files={"src/app.py": "value = input()\nprint(value)\n"},
            regression_command=["pytest", "-q"],
        )

    result = await execute_project_workflow(
        project,
        silent_emit,
        cycles=cycles,
        config=config or TEST_CONFIG,
        limits=limits,
        sandbox_factory=lambda _settings: sandbox,
        muse_factory=lambda _settings: muse,
    )
    assert muse.closed and sandbox.closed
    return result


class FakeFixtureMuse:
    """Red/blue double for execute_purple_workflow fixture tests."""

    def __init__(self):
        self.blue_calls = 0
        self.closed = False

    async def run_red_team_analysis(self, *args):
        from modules.core.agents import RedTeamFinding

        return RedTeamFinding(
            vulnerability_class="test boundary",
            sink_location="app.js",
            analysis_summary="Test-only injected agent.",
            verification_script_python="import sys\nsys.exit(0)",
        )

    async def run_blue_team_sanitizer(self, *args):
        from test_patches import node_patch

        from modules.core.agents import BlueTeamPatch
        from modules.core.registry import TARGETS_REGISTRY

        self.blue_calls += 1
        return BlueTeamPatch(
            sanitization_strategy="Validate IDs",
            diff_summary="Add a guard",
            patched_file_content=node_patch(TARGETS_REGISTRY["node_query_sink"].read_source()),
        )

    async def aclose(self):
        self.closed = True


class FakeFixtureSandbox:
    """Docker-manager double returning scripted exit codes as VerificationResult."""

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
        from modules.core.docker_manager import VerificationResult

        return VerificationResult(next(self.codes), "test evidence")

    def close(self):
        self.closed = True


async def run_fixture_workflow(codes, emit=silent_emit, sandbox=None, config=None):
    """Execute the purple fixture workflow with fakes and assert both halves closed."""
    from modules.workflows.workflow import execute_purple_workflow

    sandbox = sandbox or FakeFixtureSandbox(codes)
    muse = FakeFixtureMuse()
    result = await execute_purple_workflow(
        "node_query_sink",
        emit,
        config=config or TEST_CONFIG,
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: muse,
    )
    assert sandbox.closed and muse.closed
    return result, sandbox, muse


class ResearchFakeFixtureMuse(FakeFixtureMuse):
    """FakeFixtureMuse plus research sidecar methods returning grounded digests."""

    def __init__(self):
        super().__init__()
        self.red_research_calls = 0
        self.blue_research_calls = 0

    async def run_red_research(self, sink_description, intel_records):
        from modules.core.agents import RedResearchDigest

        self.red_research_calls += 1
        assert isinstance(intel_records, list)
        return RedResearchDigest(
            queries=["test query"],
            attack_patterns=["grounded pattern"],
            cwe_hints=["CWE-78"],
        )

    async def run_blue_research(self, sink_description, intel_records):
        from modules.core.agents import BlueResearchDigest

        self.blue_research_calls += 1
        return BlueResearchDigest(
            queries=["test query"],
            fix_patterns=["grounded fix"],
            cwe_hints=["CWE-78"],
        )
