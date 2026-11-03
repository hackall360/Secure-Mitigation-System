# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Parity W1 RED-FIRST: intel provenance summary (canned records only, no network)."""

from __future__ import annotations

import dataclasses

from library.intel.research import ResearchRecord
from library.services.sms_api import summarize_intel_provenance

_ALLOWED_KEYS = {"source", "cve_id", "summary_snippet", "epss", "kev"}
_FORBIDDEN_SUBSTRINGS = ("key", "blob", "payload", "secret", "token", "auth")


def _canned_records() -> list[ResearchRecord]:
    return [
        ResearchRecord(
            source="osv",
            cve_id="CVE-2024-1234",
            title="OSV CVE-2024-1234",
            summary="A buffer overflow in example-lib allows remote code execution. " * 10,
        ),
        ResearchRecord(
            source="epss",
            cve_id="CVE-2024-1234",
            title="EPSS 0.85 (percentile 0.97)",
            summary="Exploit-prediction score 0.85 dated 2026-01-01.",
            extra={"epss": "0.85", "percentile": "0.97"},
        ),
        ResearchRecord(
            source="kev",
            cve_id="CVE-2024-1234",
            title="Known exploited",
            summary="Listed as known-exploited.",
            extra={"kev_listed": True, "due_date": "2026-02-01"},
        ),
    ]


def test_empty_input_returns_empty() -> None:
    assert summarize_intel_provenance([]) == []


def test_objects_shape_and_snippet_bound() -> None:
    out = summarize_intel_provenance(_canned_records())
    assert len(out) == 3
    for row in out:
        assert set(row) == _ALLOWED_KEYS
        assert len(row["summary_snippet"]) <= 160


def test_dict_inputs_supported() -> None:
    dicts = [dataclasses.asdict(r) for r in _canned_records()]
    out = summarize_intel_provenance(dicts)
    assert len(out) == 3
    assert out[0]["source"] == "osv"
    assert out[0]["cve_id"] == "CVE-2024-1234"


def test_epss_and_kev_extracted() -> None:
    out = summarize_intel_provenance(_canned_records())
    by_source = {row["source"]: row for row in out}
    assert by_source["epss"]["epss"] == "0.85"
    assert by_source["kev"]["kev"] is True
    assert by_source["osv"]["kev"] is False


def test_hostile_input_stripped() -> None:
    hostile = {
        "source": "osv",
        "cve_id": "CVE-2024-9999",
        "title": "evil",
        "summary": "x" * 500,
        "payload": {"nested": "blob-data"},
        "blob": "raw-bytes",
        "api_key": "sk-live-123",
        "secret": "shh",
        "extra": {"payload": "nested-evil", "epss": "0.1"},
    }
    out = summarize_intel_provenance([hostile])
    assert len(out) == 1
    row = out[0]
    assert set(row) == _ALLOWED_KEYS
    text = repr(row).lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in text, f"leaked {forbidden!r} in {row!r}"
    assert len(row["summary_snippet"]) <= 160
