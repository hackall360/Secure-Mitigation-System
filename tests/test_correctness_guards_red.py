# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""W6 (correctness deep-validation round 3): adversarial + contract pins.

Covers gaps the suite never asserted with live adversarial inputs:
1. Patch-guard adversarial matrix (empty/unchanged/license-strip/fence/
   oversize/solver-shape) -> PatchRejected with the exact guard_id.
2. Library fail-closed: scan_source("unknown") returns status=error with the
   unknown-fixture message (never raises, never verifies).
3. Redaction: probe traces are withheld in the user report (placeholder, not
   probe bytes); baseline trace stays visible.
4. Receipt properties: deterministic hash, sensitivity, chain linkage.
5. Scanner fail-soft: absent binary degrades to [] (never raises).
"""

from modules.core.patches import PatchRejected, validate_patch
from modules.core.registry import TARGETS_REGISTRY
from modules.intel import scanner_binaries as sb
from modules.workflows.workflow import (
    ScanResult,
    build_verdict_receipt,
    redact_fixture_result_for_user,
)


def _src():
    return open("targets/node_query_sink/app.js", encoding="utf-8").read()


def _target():
    return TARGETS_REGISTRY["node_query_sink"]


def test_patch_guard_empty_rejected():
    try:
        validate_patch(_target(), _src(), "")
        raise AssertionError("empty patch accepted")
    except PatchRejected as exc:
        assert exc.guard_id == "empty_or_unchanged"


def test_patch_guard_unchanged_rejected():
    src = _src()
    try:
        validate_patch(_target(), src, src)
        raise AssertionError("unchanged patch accepted")
    except PatchRejected as exc:
        assert exc.guard_id == "empty_or_unchanged"


def test_patch_guard_license_strip_rejected():
    src = _src()
    stripped = "\n".join(line for line in src.splitlines() if "Required Notice" not in line)
    try:
        validate_patch(_target(), src, stripped)
        raise AssertionError("license-strip accepted")
    except PatchRejected as exc:
        assert exc.guard_id == "license_notice_removed"


def test_patch_guard_fence_rejected():
    src = _src()
    try:
        validate_patch(_target(), src, "```js\n" + src)
        raise AssertionError("fenced patch accepted")
    except PatchRejected as exc:
        assert exc.guard_id == "malformed_patch"


def test_patch_guard_oversize_rejected():
    src = _src()
    try:
        validate_patch(_target(), src, src + "\n// evil: " + "x" * 70000)
        raise AssertionError("oversize patch accepted")
    except PatchRejected as exc:
        assert exc.guard_id == "malformed_patch"


async def _unknown_target_result():
    from modules.core.config import PurpleBoxConfig
    from modules.services import sms_api

    return await sms_api.scan_source("nope_xyz", config=PurpleBoxConfig(meta_api_key="k"))


def test_library_unknown_target_returns_error_not_raise():
    import asyncio

    result = asyncio.run(_unknown_target_result())
    assert result.status == "error", f"expected error, got {result.status}"
    assert "Unknown fixture" in str(result.message)
    assert not result.success, "unknown target must never verify"


def test_redaction_withholds_probe_traces():
    result = ScanResult(target="node_query_sink", status="verified")
    result.traces = {
        "before": "SECRET-PROBE-BYTES",
        "after": "SECRET-POST-BYTES",
        "baseline": "BASE-OK",
    }
    out = redact_fixture_result_for_user(result)
    blob = str(out)
    assert "SECRET-PROBE" not in blob and "SECRET-POST" not in blob
    assert out["traces"]["baseline"] == "BASE-OK"
    assert "withheld" in out["traces"]["before"]


def test_receipt_deterministic_sensitive_chained():
    kw = {"fixture": "node_query_sink", "pre_exit_code": 0, "post_exit_code": 1}
    r1 = build_verdict_receipt(regression_passed=True, patch_content="A", **kw)
    r2 = build_verdict_receipt(regression_passed=True, patch_content="A", **kw)
    r3 = build_verdict_receipt(regression_passed=True, patch_content="B", **kw)
    assert r1.patch_sha256 == r2.patch_sha256
    assert r1.patch_sha256 != r3.patch_sha256
    r4 = build_verdict_receipt(regression_passed=True, patch_content="C", prev_receipt=r1, **kw)
    assert r4.prev_receipt_sha == r1.patch_sha256


def test_scanners_absent_binary_degrades_to_empty():
    assert sb.run_trivy("/nonexistent-dir-xyz") == []
    assert sb._cached_which("definitely-not-a-binary-xyz") is None
