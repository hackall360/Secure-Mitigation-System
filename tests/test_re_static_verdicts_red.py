# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): RE static stage reaches red + terminal verdicts for project scan.

Two gaps found firsthand:

1. The static reversing profile (file/strings/readelf) is collected at
   binary_sweep.py:141 but the REASON red found nothing on binaries is
   unclear: does the profile text reach the red prompt input, or does red
   only see raw blob metadata? The profile must ground red: section list,
   imported symbols, and suspicious strings must appear in the red user
   message for the binary pass. Fail until a test proves the wiring.

2. AnyCam ended "partial" (attempt 11: 1 finding, patch rolled back).
   A cyber team delivers a terminal verdict: either the finding holds
   (verified) or it does not hold (failed/rejected). "Partial" leaves the
   decision to the reader. Project scan must map mixed outcomes to a
   terminal pair: every candidate rolled back with live evidence =
   "failed" (finding did not hold under patch); at least one retained
   with nothing contradicting = "verified". Reserve "partial" for runs
   where evidence genuinely conflicts within itself.
"""

from __future__ import annotations


def test_binary_static_profile_reaches_red_prompt():
    import inspect

    import library.workflows.binary_sweep as bs

    src = inspect.getsource(bs.execute_binary_sweep)
    assert "binary_static_profile" in src, "static profile must be collected"
    # The profile text must be threaded into the red call's source/contract
    # input — not just emitted as a log line.
    call_site = src.split("run_red_team_pass_analysis")[1].split("SweepPassResult")[0]
    assert "profile" in call_site.lower(), (
        "static profile text must reach the red analysis call, not stop at the emit log"
    )


def test_project_scan_terminal_verdicts():
    import inspect

    import library.workflows.project_workflow as pw

    src = inspect.getsource(pw.execute_project_workflow)
    # Mixed-but-decisive outcomes need terminals: all-rolled-back with
    # live pre-patch evidence is a failed candidate (did not hold), not
    # an eternal partial.
    assert '"partial"' in src or "'partial'" in src
    tail = src.split('result.status = "partial"')[0][-1500:]
    assert "rolled_back" in tail or "failed" in tail, (
        "the partial branch must distinguish terminal failure "
        "(all candidates rolled back under live evidence) from "
        "genuinely conflicting evidence"
    )
