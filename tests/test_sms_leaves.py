"""Shared-leaf unit tests: sms_records, sms_text, sms_budget, sms_scan_parse, sms_redact.

Each leaf is behavior-identical to the code it replaced; these pin the
semantics so future extractions cannot drift them.
"""
from sms_budget import check_payload_budget, resolve_payload_budget
from sms_records import (
    dedupe_records,
    sanitize_cve_id,
    sanitize_cve_id_strict,
    to_record_dict,
    truncate_summary,
)
from sms_redact import (
    EXPLOIT_REDACTED,
    redact_fixture_result,
)
from sms_scan_parse import cvss_best, cvss_from_vendor_map, cwe_list, ref_list
from sms_text import bounded, take_utf8_prefix


def test_sanitize_cve_id_shapes():
    assert sanitize_cve_id(" cve-2024-3094 ") == "CVE-2024-3094"
    assert sanitize_cve_id("CVE-2024-3094; rm -rf") == "CVE-2024-3094RM-RF"
    assert sanitize_cve_id_strict("CVE-2024-3094") == "CVE-2024-3094"
    assert sanitize_cve_id_strict("bogus") == ""


def test_truncate_and_bounded_never_silent():
    assert truncate_summary("x" * 2000) == "x" * 1500
    assert truncate_summary(None) == ""
    cut = bounded("y" * 100, 10)
    assert cut.startswith("y" * 10) and "90 characters omitted" in cut


def test_take_utf8_prefix_boundary():
    text, rest = take_utf8_prefix("abc😀def", 4)
    assert text == "abc" and rest == "😀def"


def test_budget_checks():
    payload = {"a": "x" * 100}
    import json as _json

    size = len(_json.dumps(payload).encode())
    assert check_payload_budget(payload, size + 1, "ctx") == size
    try:
        check_payload_budget(payload, size - 1, "ctx")
    except ValueError as exc:
        assert "ctx" in str(exc)
    else:
        raise AssertionError("expected budget error")
    assert resolve_payload_budget(1000, 100) == 1000
    assert resolve_payload_budget(100_000, 100) == 16_384


def test_scan_parse_shapes():
    assert cvss_from_vendor_map({"nvd": {"V3Score": 9.8}}) == "9.8"
    assert cvss_best([{"metrics": {"baseScore": 5.0}}, {"metrics": {"baseScore": 7.1}}]) == "7.1"
    assert cwe_list(["CWE-78", {"cwe_id": "CWE-89"}, ""]) == ("CWE-78", "CWE-89")
    assert ref_list(["https://a", 42, "https://b"]) == ("https://a", "https://b")


def test_redact_never_leaks_scripts():
    class R:
        def model_dump(self):
            return {
                "finding": {"verification_script_python": "evil()"},
                "traces": {"before": "payload", "baseline": "x" * 3000},
            }

    safe = redact_fixture_result(R())
    assert safe["finding"]["verification_script_python"] == EXPLOIT_REDACTED
    assert "withheld" in safe["traces"]["before"]
    assert "truncated" in safe["traces"]["baseline"]


def test_record_dict_and_dedupe():
    class R:
        source = "circl"
        cve_id = "CVE-1"
        title = "t"
        summary = "s" * 700
        severity = ""
        cvss = ""
        cwe = []

    d = to_record_dict(R())
    assert d["source"] == "circl" and len(d["summary"]) == 600
    assert len(dedupe_records([R(), R(), None])) == 1
