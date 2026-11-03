# Coordinator gap-fill (verification sweep P1/P4): uncovered pure branches.
"""RED-first: each test below targets lines no existing test executes."""

import pytest


def test_usage_from_response_missing_and_negative_fields_count_zero():
    from modules.core.pricing import usage_from_response

    call = usage_from_response("red", "muse-spark-1.3", {}, 1.0)
    assert (call.prompt_tokens, call.completion_tokens) == (0, 0)
    assert (call.cached_tokens, call.reasoning_tokens) == (0, 0)
    call = usage_from_response(
        "blue",
        "muse-wonder-1.0",
        {"usage": {"prompt_tokens": -5, "completion_tokens": "x"}},
        2.0,
    )
    assert (call.prompt_tokens, call.completion_tokens) == (0, 0)


def test_usage_from_response_non_dict_body_counts_zero():
    from modules.core.pricing import usage_from_response

    call = usage_from_response("red", "muse-spark-1.3", ["not", "a", "dict"], 1.0)
    assert (call.prompt_tokens, call.cached_tokens) == (0, 0)


def test_scan_usage_cost_none_when_any_call_unpriced():
    from modules.core.pricing import CallUsage, ScanUsage

    priced = CallUsage(
        role="red", model="muse-spark-1.3", prompt_tokens=10, completion_tokens=5, cost_usd=0.001
    )
    unpriced = CallUsage(
        role="red", model="muse-spark-1.3", prompt_tokens=10, completion_tokens=5, cost_usd=None
    )
    assert ScanUsage(calls=[priced, unpriced]).cost_usd is None
    assert ScanUsage(calls=[]).cost_usd is None
    assert ScanUsage(calls=[priced]).cost_usd == 0.001


def test_apply_profile_rejects_unknown_key_on_meta_host():
    from modules.core.config import PurpleBoxConfig
    from modules.core.profiles import ProfileError, apply_profile

    with pytest.raises(ProfileError):
        apply_profile(PurpleBoxConfig(), "no-such-profile")


def test_check_payload_budget_raises_naming_context():
    from modules.shared.sms_budget import check_payload_budget

    with pytest.raises(ValueError, match="demo-ctx"):
        check_payload_budget({"k": "v" * 100}, 10, "demo-ctx")


def test_resolve_payload_budget_floor_and_cap():
    from modules.shared.sms_budget import DEFAULT_FLOOR_BYTES, resolve_payload_budget

    assert resolve_payload_budget(10**9, 100) == max(DEFAULT_FLOOR_BYTES, 400)
    assert resolve_payload_budget(100, 10**9) == 100
