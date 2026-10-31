# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (C48 hotspot revisit): contradiction reports must fail validation.

C48's proven root cause: Red's second pass returned outcome=no_finding WITH
a full verification_script_python, contradicting its own pass-1 exit-0
proof (6 captures, same signature). The harness fails closed via
RedReport.validate_outcome — this test pins that branch directly so the
fail-closed behavior can never silently regress.
"""

import pytest


def test_no_finding_with_probe_is_rejected():
    from modules.services.project_agents import RedReport

    with pytest.raises(Exception, match="no-finding report must not include finding fields"):
        RedReport(
            outcome="no_finding",
            analysis_summary="reviewed",
            verification_script_python="import sys\nsys.exit(0)\n",
        )


def test_finding_without_probe_is_rejected():
    from modules.services.project_agents import RedReport

    with pytest.raises(Exception, match="requires vulnerability"):
        RedReport(
            outcome="finding",
            vulnerability="injection",
            affected_paths=["app.py"],
            analysis_summary="found",
            verification_script_python="",
        )


def test_clean_no_finding_passes():
    from modules.services.project_agents import RedReport

    report = RedReport(outcome="no_finding", analysis_summary="reviewed")
    assert report.outcome == "no_finding"
