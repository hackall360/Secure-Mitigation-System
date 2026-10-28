# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0

from config import PurpleBoxConfig
from pricing import CallUsage
from project_agents import (
    BlueProposal,
    FileReplacement,
    FinalBlueReport,
    ProjectAgentRunner,
    RedBatchEvidence,
    RedReport,
    ReviewAssignment,
    ReviewTeamPlan,
    SourceDocument,
)
from scan_profiles import SCAN_PROFILES

CONFIG = PurpleBoxConfig(meta_api_key="unit-test-key")


class TeamMuse:
    def __init__(self, *, invalid_plan: bool = False):
        self.calls = []
        self.usage = []
        self.invalid_plan = invalid_plan

    async def _request(self, model, system, payload, schema, role=""):
        self.calls.append(
            {
                "model": model,
                "system": system,
                "payload": payload,
                "schema": schema,
                "role": role,
            }
        )
        self.usage.append(
            CallUsage(
                role=role,
                model=model,
                prompt_tokens=1,
                completion_tokens=1,
                cost_usd=0.0001,
            )
        )
        if schema is ReviewTeamPlan:
            count = payload["requested_worker_count"]
            indices = range(1, count + 1)
            if self.invalid_plan:
                indices = range(2, count + 2)
            return ReviewTeamPlan(
                strategy=f"Divide {payload['team']} review into independent scopes.",
                assignments=[
                    ReviewAssignment(
                        agent_index=index,
                        focus=f"scope {index}",
                        objective=f"Review bounded evidence for scope {index}.",
                    )
                    for index in indices
                ],
                limitations=["Assignments do not override stage safety rules."],
            )
        if schema is RedBatchEvidence:
            return RedBatchEvidence(
                candidates=[],
                observations=["Reviewed only the supplied bounded chunk."],
                no_candidate_reason="No testable candidate in this worker scope.",
            )
        if schema is RedReport:
            return RedReport(
                outcome="no_finding",
                analysis_summary="No testable finding was selected from bounded worker evidence.",
                limitations=["This is not a general security claim."],
            )
        if schema is BlueProposal:
            if "worker_proposals" not in payload:
                return BlueProposal(
                    strategy="Worker recommends a bounded validation guard.",
                    replacements=[],
                    limitations=["Leader synthesis is required."],
                )
            source = payload["safe_snapshot_files"][0]
            return BlueProposal(
                strategy="Leader retained one sanitation-only input validation change.",
                replacements=[
                    FileReplacement(
                        path=source["path"],
                        original_sha256=source["sha256"],
                        replacement_content=source["content"] + "\n# validate input\n",
                        rationale="Reject malformed input before it reaches the sink.",
                        change_kind="input_validation",
                    )
                ],
                limitations=["Runtime verification remains required."],
            )
        if schema is FinalBlueReport:
            return FinalBlueReport(
                disposition="no_change",
                summary="Bounded report only.",
                limitations=["Not a general security claim."],
            )
        raise AssertionError(f"Unexpected schema: {schema}")


async def test_named_profiles_send_cumulative_focus_that_expands_by_cycle_and_pass():
    for profile_key in ("extra_light", "light", "medium", "heavy", "super_heavy"):
        muse = TeamMuse()
        runner = ProjectAgentRunner(muse, CONFIG)
        focuses = []
        rounds = [(1, 1), (1, 2)]
        if SCAN_PROFILES[profile_key].cycles > 1:
            rounds.append((2, 1))
        for cycle, pass_number in rounds:
            runner.configure_review(
                profile_key=profile_key,
                cycle=cycle,
                red_agents=5,
                blue_agents=5,
                pass_number=pass_number,
            )
            await runner.final_blue_report(
                project_name="demo",
                cycle=cycle,
                stage_evidence={"disposition": "no_change"},
            )
            review = muse.calls[-1]["payload"]["review"]
            assert review["profile_key"] == profile_key
            assert review["cycle"] == cycle
            assert review["pass_number"] == pass_number
            focuses.append(review["cumulative_focus"])
        assert focuses[0]
        assert focuses[1][: len(focuses[0])] == focuses[0]
        if len(focuses) == 3:
            assert focuses[2][: len(focuses[1])] == focuses[1]
        assert all(
            len(left) <= len(right)
            for left, right in zip(focuses, focuses[1:], strict=False)
        )
        assert all("leader_plan" not in call["role"] for call in muse.calls)


async def test_ultra_heavy_red_uses_model_plan_five_workers_and_leader_synthesis():
    muse = TeamMuse()
    runner = ProjectAgentRunner(muse, CONFIG)
    runner.configure_review(profile_key="ultra_heavy", cycle=1, red_agents=5, blue_agents=5)

    artifacts = await runner.analyze_red(
        [SourceDocument(path="src/app.py", content="value = input()\nprint(value)\n")],
        project_name="demo",
        cycle=1,
        max_batch_bytes=1024,
    )

    roles = [call["role"] for call in muse.calls]
    assert roles[0] == "project_red_leader_plan_cycle_1"
    assert roles[1:6] == [
        f"project_red_initial_evidence_cycle_1_batch_0_worker_{index}"
        for index in range(1, 6)
    ]
    assert roles[6] == "project_red_initial_leader_synthesis_cycle_1"
    assert len(artifacts.batch_evidence) == 5
    assert artifacts.leader_plan is not None
    assert [item.agent_index for item in artifacts.leader_plan.assignments] == list(range(1, 6))
    assert artifacts.report.outcome == "no_finding"
    assert [item.role for item in muse.usage] == roles
    for call in muse.calls[1:6]:
        assert call["payload"]["leader_assignment"]["agent_index"] in range(1, 6)
        assert "untrusted model output" in call["system"]


async def test_ultra_heavy_blue_uses_five_workers_and_sanitation_only_leader_synthesis():
    muse = TeamMuse()
    runner = ProjectAgentRunner(muse, CONFIG)
    runner.configure_review(profile_key="ultra_heavy", cycle=2, red_agents=5, blue_agents=5)
    source = SourceDocument(path="src/app.py", content="value = input()\nprint(value)\n")
    report = RedReport(
        outcome="finding",
        vulnerability="unvalidated input",
        affected_paths=[source.path],
        analysis_summary="Untrusted input reaches a sensitive boundary.",
        verification_script_python="import sys\nsys.exit(0)",
        limitations=["Only supplied source was reviewed."],
    )

    proposal = await runner.propose_blue(
        [source],
        project_name="demo",
        cycle=2,
        red_report=report,
        pre_verification={"probe": {"exit_code": 0}},
        contract="Preserve behavior and add validation only.",
        max_changed_files=1,
        max_changed_bytes=4096,
    )

    roles = [call["role"] for call in muse.calls]
    assert roles[0] == "project_blue_leader_plan_cycle_2"
    assert roles[1:6] == [
        f"project_blue_proposal_cycle_2_batch_0_worker_{index}" for index in range(1, 6)
    ]
    assert roles[6] == "project_blue_leader_synthesis_cycle_2_batch_0"
    assert len(proposal.replacements) == 1
    replacement = proposal.replacements[0]
    assert replacement.path == source.path
    assert replacement.original_sha256 == source.sha256
    assert replacement.change_kind == "input_validation"
    synthesis = muse.calls[-1]
    assert len(synthesis["payload"]["worker_proposals"]) == 5
    assert "untrusted evidence" in synthesis["system"]
    assert [item.role for item in muse.usage] == roles


def test_configure_review_keeps_requested_interface_and_validates_bounds():
    runner = ProjectAgentRunner(TeamMuse(), CONFIG)
    runner.configure_review(
        profile_key="ultra_heavy", cycle=1, red_agents=5, blue_agents=5
    )

    for kwargs in (
        {"profile_key": "light", "cycle": 0},
        {"profile_key": "light", "cycle": 1, "red_agents": 0},
        {"profile_key": "light", "cycle": 1, "blue_agents": 13},
        {"profile_key": "light", "cycle": 1, "pass_number": 3},
    ):
        try:
            runner.configure_review(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid configuration was accepted: {kwargs}")
