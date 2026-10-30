# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9) receipt-chain tests per W1-receipt-proof.

Fails today: VerdictReceipt has no created_at/prev_receipt_sha/signature
fields and no chain_ok from verify_receipt (extra=forbid strict model).
GREEN requires the chained-receipt feature without changing verdict
provenance (verdict still from Docker evidence only).
"""

import hashlib

import pytest
from pydantic import ValidationError

from modules.services.sms_api import verify_receipt
from modules.workflows.workflow import build_verdict_receipt, VerdictReceipt

PATCH = "diff --git a/f b/f\n+fixed\n"


def _prev() -> VerdictReceipt:
    return build_verdict_receipt(
        fixture="node-expr",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content=PATCH,
    )


def test_receipt_accepts_optional_chain_fields_strict_compat():
    prev = _prev()
    # Old constructor calls unchanged (strict compat).
    assert prev.patch_sha256 == hashlib.sha256(PATCH.encode()).hexdigest()
    # New optional fields must be accepted with defaults.
    chained = VerdictReceipt(
        fixture="node-expr",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        differential_passed=True,
        patch_sha256=prev.patch_sha256,
        created_at="2026-10-30T00:00:00+00:00",
        prev_receipt_sha=prev.patch_sha256,
    )
    assert chained.prev_receipt_sha == prev.patch_sha256
    assert chained.created_at == "2026-10-30T00:00:00+00:00"
    with pytest.raises(ValidationError):
        VerdictReceipt(
            fixture="node-expr",
            pre_exit_code=0,
            post_exit_code=1,
            regression_passed=True,
            differential_passed=True,
            patch_sha256=prev.patch_sha256,
            bogus_field="nope",
        )


def test_build_verdict_receipt_chains_prev_link():
    prev = _prev()
    chained = build_verdict_receipt(
        fixture="node-expr",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content=PATCH,
        prev_receipt=prev,
    )
    assert chained.prev_receipt_sha == prev.patch_sha256


def test_verify_receipt_chain_ok_intact_and_tampered():
    prev = _prev()
    chained = build_verdict_receipt(
        fixture="node-expr",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content=PATCH,
        prev_receipt=prev,
    )
    intact = verify_receipt(chained.model_dump())
    assert intact["chain_ok"] is True
    # Verdict decision still from Docker evidence only, not the chain flag.
    assert intact["valid"] is True
    tampered = dict(chained.model_dump())
    tampered["prev_receipt_sha"] = "0" * 64
    bad = verify_receipt(tampered)
    assert bad["chain_ok"] is False
    assert bad["valid"] is True  # chain break must not change verdict


def test_verify_receipt_tampered_digest_fails():
    prev = _prev()
    chained = build_verdict_receipt(
        fixture="node-expr",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content=PATCH,
        prev_receipt=prev,
    )
    tampered = dict(chained.model_dump())
    tampered["patch_sha256"] = "f" * 64
    assert verify_receipt(tampered)["valid"] is False
