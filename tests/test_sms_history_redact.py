"""M2 (LAW 9 RED-first): verified_history must go through redact_cycle_evidence.

Finding: redact_project_result copied verified_history items verbatim
({k: v for k, v in item.items()}), so any verification_script_python or
probe output riding in a history item shipped unredacted, while
cycle_reports above got redact_cycle_evidence. These tests pin parity.
Scope: history loop only; does not touch redact_probe_output (M1) or the
normal-trace block (L3).
"""

import copy
import json

from library.shared.sms_redact import (
    EXPLOIT_REDACTED,
    redact_project_result,
)


def _evil_evidence():
    return {
        "red": {
            "batch_evidence": [
                {
                    "candidates": [
                        {
                            "verification_script_python": "evil()",
                            "evidence": "payload",
                        }
                    ]
                }
            ],
            "report": {"verification_script_python": "evil()"},
        },
        "independent_red": {"report": {"verification_script_python": "evil()"}},
        "pre_verification": {"probe": {"output": "short payload", "exit_code": 0}},
        "patched_verification": {"probe": {"output": "x" * 600, "exit_code": 1}},
    }


def _proj(history, cycles=None):
    class Proj:
        def model_dump(self):
            return {
                "cycle_reports": copy.deepcopy(cycles or []),
                "verified_history": copy.deepcopy(history),
            }

    return Proj()


def test_m2_history_item_scripts_and_probe_output_redacted():
    """A history item carrying verification_script_python + probe output
    must come back redacted (currently ships verbatim -> RED)."""
    hist = [
        {
            "cycle": 1,
            "target": "t",
            "status": "verified",
            "verification_script_python": "evil()",
            "evidence": _evil_evidence(),
        }
    ]
    data = redact_project_result(_proj(hist))
    item = data["verified_history"][0]
    assert item["verification_script_python"] == EXPLOIT_REDACTED
    blob = json.dumps(item["evidence"])
    assert "evil()" not in blob
    assert "short payload" not in blob
    assert "x" * 600 not in blob
    # exit codes survive, like the cycle path
    assert item["evidence"]["pre_verification"]["probe"]["exit_code"] == 0
    assert item["evidence"]["patched_verification"]["probe"]["exit_code"] == 1


def test_m2_history_cycles_redaction_parity():
    """The same evidence dict placed in verified_history and in
    cycle_reports must redact identically."""
    ev = _evil_evidence()
    data = redact_project_result(
        _proj(
            [{"cycle": 1, "evidence": ev}],
            cycles=[{"evidence": ev}],
        )
    )
    assert data["verified_history"][0]["evidence"] == data["cycle_reports"][0]["evidence"]


def test_m2_history_without_evidence_passes_through():
    """Items without evidence (today's production shape: exit codes,
    paths, class names) are untouched."""
    hist = [
        {
            "cycle": 1,
            "pass_number": 1,
            "vulnerability": "SQLi class",
            "changed_paths": ["src/app.py"],
            "pre_probe_exit": 0,
            "post_probe_exit": 1,
            "regression_exit": 0,
        },
        {"target": "u", "status": "verified"},
    ]
    data = redact_project_result(_proj(hist))
    assert data["verified_history"] == hist
