# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Cycle semantics and cumulative, evidence-gated named-profile execution."""

import pytest
from helpers import (
    TEST_CONFIG as CONFIG,
)
from helpers import (
    FakeProjectMuse as FakeMuse,
)
from helpers import (
    FakeProjectSandbox as FakeSandbox,
)
from helpers import (
    project_verification as verification,
)
from helpers import (
    silent_emit,
)

from project_agents import ProjectAgentRunner
from project_workflow import execute_project_workflow
from projects import ProjectSpec


def make_spec(tmp_path, profile="extra_light", **overrides):
    (tmp_path / "app.py").write_text("value = input()\nprint(value)\n")
    return ProjectSpec(
        path=tmp_path,
        command=["python3", "app.py"],
        test_command=["python3", "-m", "unittest"],
        contract="Preserve valid input. Only sanitize input boundaries.",
        allow_remote_inference=True,
        scan_profile=profile,
        **overrides,
    )


async def execute(spec, muse, sandbox, **kwargs):
    return await execute_project_workflow(
        spec,
        silent_emit,
        config=CONFIG,
        sandbox_factory=lambda _: sandbox,
        muse_factory=lambda _: muse,
        **kwargs,
    )


async def test_one_named_cycle_performs_two_real_cumulative_patch_rounds(tmp_path):
    spec = make_spec(tmp_path)
    muse = FakeMuse(red_outcomes=["finding", "no_finding", "finding", "no_finding"])
    sandbox = FakeSandbox(
        [
            verification(1),
            verification(0),
            verification(1),
            verification(0),
            verification(1),
        ]
    )
    result = await execute(spec, muse, sandbox)
    assert result.success, result.message
    assert result.cycles_requested == result.cycles_completed == 1
    assert result.passes_per_cycle == 2
    assert [(r.cycle, r.pass_number, r.status) for r in result.cycle_reports] == [
        (1, 1, "retained"),
        (1, 2, "retained"),
    ]
    proposals = [c for c in muse.calls if c["schema"].__name__ == "BlueProposal"]
    assert len(proposals) == 2
    first_source = proposals[0]["payload"]["safe_snapshot_files"][0]["content"]
    second_source = proposals[1]["payload"]["safe_snapshot_files"][0]["content"]
    assert second_source == first_source + "\n# validated input\n"
    assert len({call["label"] for call in sandbox.calls}) == len(sandbox.calls)
    assert sandbox.calls[3]["files"]["app.py"] == second_source
    assert (tmp_path / "app.py").read_text() == first_source
    assert muse.closed and sandbox.closed


@pytest.mark.parametrize(
    "profile,cycles",
    [
        ("extra_light", 1),
        ("light", 3),
        ("medium", 5),
        ("heavy", 8),
        ("super_heavy", 12),
    ],
)
async def test_named_profiles_do_not_stop_at_an_early_empty_pass(tmp_path, profile, cycles):
    spec = make_spec(tmp_path, profile)
    muse = FakeMuse(red_outcomes=["no_finding"] * cycles * 2)
    sandbox = FakeSandbox([verification(1)])
    result = await execute(spec, muse, sandbox)
    assert result.success, result.message
    assert result.status == "no_findings"
    assert result.cycles_requested == result.cycles_completed == cycles
    assert len(result.cycle_reports) == cycles * 2
    assert [(r.cycle, r.pass_number) for r in result.cycle_reports] == [
        (cycle, pass_number) for cycle in range(1, cycles + 1) for pass_number in (1, 2)
    ]
    assert len(sandbox.calls) == 1  # No unproven patches or probes.


async def test_named_profile_second_pass_runs_after_first_probe_is_inconclusive(tmp_path):
    muse = FakeMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeSandbox([verification(1), verification(2)])
    result = await execute(make_spec(tmp_path), muse, sandbox)
    assert result.status == "partial"
    assert result.cycles_completed == 1
    assert [r.status for r in result.cycle_reports] == ["inconclusive", "no_finding"]
    assert all(c["schema"].__name__ != "BlueProposal" for c in muse.calls)


async def test_profile_cannot_be_silently_overridden_by_workflow_argument(tmp_path):
    with pytest.raises(ValueError, match="override"):
        await execute(make_spec(tmp_path), FakeMuse(), FakeSandbox(), cycles=2)


async def test_ultra_profile_forwards_independent_team_sizes(tmp_path):
    configured = []

    class RecordingRunner(ProjectAgentRunner):
        def configure_review(self, **kwargs):
            configured.append(kwargs)
            # Avoid spending model calls on teams in this workflow-boundary test.

    spec = make_spec(tmp_path, "ultra_heavy", red_agents=3, blue_agents=7)
    muse = FakeMuse(red_outcomes=["no_finding"] * 24)
    sandbox = FakeSandbox([verification(1)])
    result = await execute(spec, muse, sandbox, agent_factory=RecordingRunner)
    assert result.success, result.message
    assert result.cycles_completed == 12
    assert len(configured) == 24
    assert all(c["red_agents"] == 3 and c["blue_agents"] == 7 for c in configured)
    assert all(c["profile_key"] == "ultra_heavy" for c in configured)
    assert result.model_dump()["red_agents"] == 3
    assert result.model_dump()["blue_agents"] == 7


async def test_failed_second_patch_preserves_only_first_verified_change(tmp_path):
    muse = FakeMuse(red_outcomes=["finding", "no_finding", "finding"])
    sandbox = FakeSandbox(
        [
            verification(1),
            verification(0),
            verification(1),
            verification(0),
            verification(0),
        ]
    )
    result = await execute(make_spec(tmp_path), muse, sandbox)
    assert result.status == "partial"
    assert result.cycles_completed == 1
    assert [r.status for r in result.cycle_reports] == ["retained", "rolled_back"]
    assert result.cumulative_diff.count("+# validated input") == 1
    assert (tmp_path / "app.py").read_text().count("validated input") == 0
    assert muse.closed and sandbox.closed
