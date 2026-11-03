# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED-FIRST (parity wave W1): per-cycle evidence summary in sms_api.

Pre-change this file FAILS (no summarize_cycle_evidence); post-change green.
Pure functions only: no Muse, no Docker, no I/O.
"""

import main
from library.services import sms_api


def _receipt(cycle: int) -> dict:
    return {
        "fixture": "node_query_sink",
        "cycle": cycle,
        "pass_number": 1,
        "pre_probe_exit": 0,
        "post_probe_exit": 1,
        "baseline_regression_exit": 0,
        "patched_regression_exit": 0,
        "differential_passed": True,
        "property_passed": True,
        "patch_sha256": "a" * 64,
    }


def _cycle(cycle: int) -> dict:
    return {
        "cycle": cycle,
        "pass_number": 1,
        "status": "retained",
        "message": "cycle retained",
        "changed_paths": [],
        "diff": "",
        "receipt": _receipt(cycle),
        "evidence": {
            "differential_passed": True,
            "pre_verification": {"probe": {"exit_code": 0}},
            "patched_verification": {
                "probe": {"exit_code": 1},
                "regression": {"exit_code": 0},
                "mutations": {"exit_code": 0},
                "properties": {"exit_code": 0},
                "repeat_regression": {"exit_code": 0},
            },
        },
    }


def _canned_report() -> dict:
    return {
        "target": "node_query_sink",
        "status": "verified",
        "receipt": None,
        "verdict_receipt": None,
        "cycle_reports": [_cycle(1), _cycle(2)],
    }


def test_summarize_cycle_evidence_per_cycle_shape():
    rows = sms_api.summarize_cycle_evidence(_canned_report())
    assert len(rows) == 2
    first = rows[0]
    assert first["cycle"] == 1
    assert first["pre_exit"] == 0
    assert first["post_exit"] == 1
    assert first["gates"] == {"mutation": True, "property": True, "repeat": True}
    assert first["verdict"] == "retained"


def test_summarize_cycle_evidence_empty_or_missing():
    assert sms_api.summarize_cycle_evidence({}) == []
    assert sms_api.summarize_cycle_evidence({"cycles": []}) == []
    assert sms_api.summarize_cycle_evidence({"cycle_reports": []}) == []
    assert sms_api.summarize_cycle_evidence(None) == []


def test_summarize_agrees_with_extract_cycle_receipts():
    report = _canned_report()
    rows = sms_api.summarize_cycle_evidence(report)
    assert len(rows) == len(main.extract_cycle_receipts(report)) == 2
