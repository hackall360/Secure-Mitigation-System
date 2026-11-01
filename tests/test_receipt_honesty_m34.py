# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""M3/M4 receipt-honesty pins (audit lane M34, LAW 9B).

M3: verify_receipt is shape-only (digest shape + exit ranges, never
recomputes the digest from patch bytes) and no production caller threads
prev receipts, so chain_ok is always False in production (genesis).
M4: on fixture loops differential_passed aliases regression_passed
(single regression gate); the test pins the alias so a future real
differential gate must update the test.
"""

import inspect

import modules.services.sms_api as api
from modules.workflows.workflow import build_verdict_receipt

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64


def _base_receipt(**overrides):
    receipt = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="patched content",
    )
    data = receipt.model_dump()
    data.update(overrides)
    return data


# --- M3 behavior pins (green on unedited code; pin current contract) ---


def test_m3_unlinked_receipt_valid_but_chain_broken():
    verdict = api.verify_receipt(_base_receipt(prev_receipt_sha=None))
    assert verdict["valid"] is True
    assert verdict["chain_ok"] is False


def test_m3_genesis_sentinel_valid_but_chain_broken():
    verdict = api.verify_receipt(_base_receipt(prev_receipt_sha="0" * 64))
    assert verdict["valid"] is True
    assert verdict["chain_ok"] is False


def test_m3_mismatched_live_link_invalid():
    candidate = _base_receipt()
    assert candidate["patch_sha256"] != _DIGEST_A  # live link must differ
    verdict = api.verify_receipt(_base_receipt(prev_receipt_sha=_DIGEST_A))
    assert verdict["valid"] is False
    assert verdict["chain_ok"] is False


def test_m3_no_production_caller_threads_prev_receipt():
    """Genesis pin: no fixture/binary/sweep loop passes prev_receipt today.

    Allowed evolution: if a loop starts threading prev receipts, update
    this test AND the verify_receipt docstring genesis claim together.
    """
    import modules.workflows.binary_sweep as binary_sweep
    import modules.workflows.sweep as sweep
    import modules.workflows.workflow as workflow

    for mod in (workflow, sweep, binary_sweep):
        source = inspect.getsource(mod)
        assert "prev_receipt=" not in source, (
            f"{mod.__name__} threads prev_receipt; update this pin + docstring"
        )


# --- M4 alias pin (green on unedited code; pins current contract) ---


def test_m4_differential_aliases_regression_on_fixture_loop():
    """LAW 9B: differential shares the single regression-gate signal today.

    A future real differential gate must flip this test deliberately.
    """
    for regression in (True, False):
        receipt = build_verdict_receipt(
            fixture="node_query_sink",
            pre_exit_code=0,
            post_exit_code=1,
            regression_passed=regression,
            patch_content="patched content",
        )
        assert receipt.differential_passed == receipt.regression_passed is regression


# --- Docstring/comment honesty pins (RED before the M34 edit) ---


def test_m3_docstring_states_structural_only_and_genesis():
    doc = " ".join((api.verify_receipt.__doc__ or "").lower().split())
    assert "structural-only" in doc
    assert "docker evidence" in doc
    assert "genesis" in doc
    assert "no caller threads prev receipts today" in doc


def test_m4_alias_comment_points_at_receipt_docstring():
    import modules.workflows.workflow as workflow

    source = inspect.getsource(workflow)
    idx = source.index("differential_passed=regression_passed")
    window = source[max(0, idx - 400): idx + 100].lower()
    assert "verdictreceipt" in window
    assert "single" in window and "gate" in window
