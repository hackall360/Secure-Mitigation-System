# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: fail-closed evidence gates must return False on inf (task-012).

mutation/property/repeat gates promise fail-closed (bad evidence -> False).
Mapping-form evidence comes from deserialized JSON where json.loads delivers
float inf (Infinity/1e999). int(inf) raises OverflowError past the
(TypeError, ValueError) guards -> crash instead of False. Post-fix: False.
"""

from modules.workflows.project_workflow import (
    mutation_gate_passed,
    property_gate_passed,
    repeat_stability_passed,
)


def test_mutation_gate_rejects_inf_evidence():
    assert mutation_gate_passed({"mutations": {"exit_code": float("inf")}}) is False


def test_property_gate_rejects_inf_evidence():
    assert property_gate_passed({"properties": {"exit_code": float("inf")}}) is False


def test_repeat_gate_rejects_inf_evidence():
    assert (
        repeat_stability_passed(
            {
                "regression": {"exit_code": 0},
                "repeat_regression": {"exit_code": float("inf")},
            }
        )
        is False
    )


def test_gates_still_pass_clean_evidence():
    assert mutation_gate_passed({"mutations": {"exit_code": 0}}) is True
    assert property_gate_passed({"properties": {"exit_code": 0}}) is True
    assert (
        repeat_stability_passed(
            {
                "regression": {"exit_code": 0},
                "repeat_regression": {"exit_code": 0},
            }
        )
        is True
    )
