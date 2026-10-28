# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Shared record shaping: CVE-id normalization, summary caps, dict export.

Scattered across research/intel/deep_scan/scanner/workflow before; one home
now. Primitives only (no Record imports): every transport shapes through
these so truncation and casing stay consistent. Leaf module.
"""

from __future__ import annotations

import re
from typing import Any

SUMMARY_LIMIT = 1500
DIGEST_SUMMARY_LIMIT = 600
CVE_ID_LIMIT = 32

_CVE_SAFE = re.compile(r"[^A-Za-z0-9\-_:.]")


def sanitize_cve_id(raw: Any, limit: int = CVE_ID_LIMIT) -> str:
    """Strip unsafe URL chars from a CVE id, uppercase, bounded."""
    return _CVE_SAFE.sub("", str(raw or "").strip().upper())[:limit]


def sanitize_cve_id_strict(raw: Any) -> str:
    """sanitize_cve_id plus full CVE-YYYY-NNNN shape check; '' when invalid."""
    safe = sanitize_cve_id(raw)
    if re.fullmatch(r"CVE-\d{4}-\d{4,7}", safe):
        return safe
    return ""


def truncate_summary(text: Any, limit: int = SUMMARY_LIMIT) -> str:
    """Bound free-text summaries; non-strings become ''."""
    if not isinstance(text, str):
        return ""
    return text[:limit]


def to_record_dict(record: Any, summary_limit: int = DIGEST_SUMMARY_LIMIT) -> dict:
    """Shape a ResearchRecord/ScannerRecord into the digest dict Muse sees."""
    get = getattr
    return {
        "source": get(record, "source", get(record, "scanner", "?")),
        "cve_id": get(record, "cve_id", ""),
        "title": get(record, "title", ""),
        "summary": truncate_summary(get(record, "summary", ""), summary_limit),
        "severity": get(record, "severity", ""),
        "cvss": get(record, "cvss", ""),
        "cwe": list(get(record, "cwe", []) or []),
    }


def dedupe_records(records: list) -> list:
    """Drop source+cve/title duplicates, order preserved."""
    seen: set[str] = set()
    out: list = []
    for rec in records:
        if rec is None:
            continue
        get = getattr
        key = f"{get(rec, 'source', get(rec, 'scanner', '?'))}:{get(rec, 'cve_id', '') or get(rec, 'title', '')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out
