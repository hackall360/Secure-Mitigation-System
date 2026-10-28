# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Shared scanner-field shaping: CVSS picks, CWE lists, reference lists.

parse_trivy/grype/osv/depcheck each re-implemented "first score wins",
"stringify+cap CWE ids", "stringify+cap reference URLs". One home. May only
depend on sms_records (never the reverse). Leaf-ish.
"""

from __future__ import annotations

from typing import Any

CWE_LIMIT = 16
CWE_COUNT = 8
REF_LIMIT = 256
REF_COUNT = 5


def cwe_list(raw: Any, count: int = CWE_COUNT, limit: int = CWE_LIMIT) -> tuple[str, ...]:
    """Stringify + cap CWE ids from a list of strings or {cwe_id,name} dicts."""
    out: list[str] = []
    for item in (raw or [])[:count]:
        if isinstance(item, dict):
            item = item.get("cwe_id", item.get("name", ""))
        if isinstance(item, str) and item.strip():
            out.append(item.strip()[:limit])
    return tuple(out)


def ref_list(raw: Any, count: int = REF_COUNT, limit: int = REF_LIMIT) -> tuple[str, ...]:
    """Stringify + cap reference URLs, strings only."""
    return tuple(str(r)[:limit] for r in (raw or [])[:count] if isinstance(r, str))


def cvss_from_map(cvss: Any, keys: tuple[str, ...] = ("V3Score", "V40Score", "V2Score")) -> str:
    """First non-null score from a vendor->metrics map (Trivy shape)."""
    if not isinstance(cvss, dict):
        return ""
    for entry in cvss.values():
        if isinstance(entry, dict):
            for key in keys:
                if entry.get(key) is not None:
                    return str(entry[key])
    return ""


def cvss_from_vendor_map(
    cvss: Any,
    vendors: tuple[str, ...] = ("nvd", "redhat", "ghsa"),
    keys: tuple[str, ...] = ("V3Score", "V40Score", "V2Score"),
) -> str:
    """Trivy shape: preferred vendors first, then any vendor."""
    if not isinstance(cvss, dict):
        return ""
    for vendor in vendors:
        entry = cvss.get(vendor)
        if isinstance(entry, dict):
            for key in keys:
                if entry.get(key) is not None:
                    return str(entry[key])
    return cvss_from_map(cvss, keys)


def cvss_best(entries: Any) -> str:
    """Grype shape: highest baseScore across [{metrics: {baseScore}}]."""
    best = ""
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        metrics = entry.get("metrics") or {}
        score = metrics.get("baseScore") if isinstance(metrics, dict) else None
        if score is not None:
            try:
                if not best or float(score or 0) > float(best or 0):
                    best = str(score)
            except (TypeError, ValueError):
                continue
    return best
