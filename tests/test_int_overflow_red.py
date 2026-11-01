# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: int(inf) OverflowError siblings (overnight task-009).

Same defect class as task-008 (sms_http clamps): int() on inf raises
OverflowError past (TypeError, ValueError) guards. generate_demo_project's
docstring promises "Invalid values never raise: they clamp or fall back";
_leader_decision_message formats server-side counters that must not crash
the sweep. float() sites need no fix: inf is a valid float.
"""

import pytest

from modules.services.project_agents import (
    ReviewAssignment,
    ReviewTeamPlan,
    _leader_decision_message,
)


def _plan():
    return ReviewTeamPlan(
        strategy="s",
        assignments=[ReviewAssignment(agent_index=1, focus="f", objective="o")],
    )


def test_leader_message_survives_inf_cycle():
    line = _leader_decision_message(
        leader_name="L",
        worker_noun="w",
        sector_noun="s",
        plan=_plan(),
        cycle=float("inf"),
        pass_number=float("-inf"),
    )
    assert "cycle 0 pass 0" in line


@pytest.mark.asyncio
async def test_demo_generation_survives_inf_flaw_and_seed(monkeypatch):
    """generate_demo_project with flaw_count/seed=inf must fall back, never raise."""
    import modules.services.demo_gen as dg

    captured = {}

    class FakeClient:
        config = type("C", (), {"red_team_model": "m"})()

        async def _request(self, *args, **kwargs):
            payload = args[2] if len(args) > 2 else kwargs.get("payload")
            captured["flaw_count"] = payload.get("flaw_count")
            captured["seed"] = payload.get("seed")
            from modules.services.demo_gen import DemoProjectFiles

            return DemoProjectFiles(
                app_py="x",
                test_contract_py="y",
                contract="c",
            )

    out = await dg.generate_demo_project(  # noqa: F841 (return shape asserted below)
        FakeClient(),
        theme="t",
        build_brief="b",
        vulns=["a", "b", "c"],
        intel_context=[],
        flaw_count=float("inf"),
        size="standard",
        seed=float("inf"),
    )
    assert out.app_py == "x"
    assert captured["flaw_count"] == 3, captured
    assert captured["seed"] is None, captured
