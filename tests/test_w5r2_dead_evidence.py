# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first (SPEC 14.9 item 4, V3-Lane-A first half): dead evidence fields.

1. ``reachability_score`` counts stale KEV/EPSS toward the 30-cap lift while
   ``_queue_evidence``/``_fast_lane_rank`` treat the same signals as absent:
   two views of one verdict disagree, so a stale-signal record can outrank a
   clean one in the non-fast-lane path (wrong verdict).
2. ``CycleReceipt``/``VerdictReceipt`` carry ``property_exit``/``retained``/
   ``verified`` fields no gate reads and no dedicated display: dead audit
   wire (MED). Fix removes them, so this test FAILS while they exist and
   PASSES once the dead wire is cut. (``property_passed`` is already
   display-surfaced by sms_cli; it is not part of this dead set.)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.workflows import cve_workflow as _cw  # noqa: E402
from modules.workflows import project_workflow as _pw  # noqa: E402
from modules.workflows import workflow as _fw  # noqa: E402
from modules.workflows.deep_scan import reachability_score as _reach  # noqa: E402


def test_stale_kev_does_not_lift_reach_cap():
    """Stale KEV must not add +5: fail-closed absent, like the fast lane."""
    stale = "2000-01-01"
    summary = {
        "id": "CVE-2000-0001",
        "cves": ["CVE-2000-0001"],
        "fixed_versions": [],
        "kev_listed": True,
        "kev_date": stale,
        "epss_percentile": 0.0,
        "summary": "",
        "details": "",
    }
    score, evidence = _reach(summary, [])
    assert score == 10, f"stale KEV lifted uncapped record to {score}: {evidence}"
    assert _cw._queue_evidence(summary).split("kev:")[1].startswith("stale:")
    key = _cw._fast_lane_rank(summary)
    assert key[2] is True, f"fast lane should rank stale KEV as absent: {key}"


def test_stale_epss_does_not_lift_reach_cap():
    """Stale high EPSS must not add +5 either."""
    stale = "2000-01-01"
    summary = {
        "id": "CVE-2000-0002",
        "cves": ["CVE-2000-0002"],
        "fixed_versions": [],
        "epss_percentile": 0.99,
        "epss_date": stale,
        "summary": "",
        "details": "",
    }
    score, evidence = _reach(summary, [])
    assert score == 10, f"stale EPSS lifted uncapped record to {score}: {evidence}"


def test_receipt_dead_fields_removed():
    """Dead receipt wire is cut: no gate, model, or payload carries it.

    Pre-fix this fails (``property_exit`` on CycleReceipt, ``retained`` on
    CycleReceipt, ``verified`` on VerdictReceipt exist but no gate reads
    them). Post-fix the fields are gone from the models and from every
    payload constructor, while the live twins (``property_passed``,
    report ``status``) keep flowing.
    """
    import sms_cli as _cli

    src = Path(_cli.__file__).read_text(encoding="utf-8")
    for token in ("differential_passed", "property_exit"):
        assert token in src, f"sms_cli stopped mentioning receipt.{token}"
    for token in (
        'receipt.get("retained")',
        "receipt.get('retained')",
        'receipt["retained"]',
        '["retained"]',
        'receipt.get("verified")',
        "receipt.get('verified')",
        'receipt["verified"]',
    ):
        assert token not in src, f"sms_cli reads receipt field {token}; update audit"
    src_pw = Path(_pw.__file__).read_text(encoding="utf-8")
    assert "differential_passed" in src_pw  # gate still consumes the gate output
    assert "property_exit: int | None" not in src_pw
    assert "retained: bool" not in src_pw
    assert _fw.ScanResult.model_config.get("extra") == "forbid"
    try:
        _fw.ScanResult(target="t", bogus_lane_a_field=1)
    except Exception:
        pass
    else:
        raise AssertionError("ScanResult silently ignores unknown fields")
    assert "verified: bool" not in Path(_fw.__file__).read_text(encoding="utf-8")
