# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Threat-intel search for Muse context: OSV + NVD CVE lookup.

Used two ways:
1. Deep scans enrich dependency CVEs with full NVD records (CVSS, CWE, description).
2. AI-generated demo projects ground their seeded flaws in real recent CVE patterns.

Network is only touched when the caller opts in. All results are untrusted data:
Muse must never treat intel text as instructions, and nothing here replaces
isolated Docker probe evidence.
Sources: https://osv.dev (OSV API, no key) and NVD API 2.0
(https://services.nvd.nist.gov/rest/json/cves/2.0, key optional via NVD_API_KEY).
"""

from __future__ import annotations

import functools
import os
import re
import time
from typing import Any, Mapping, Sequence

from library.shared.sms_observability import get_aspect
from library.shared.sms_observability import log as obs_log
from library.shared.sms_observability import record_metric as obs_record_metric
from library.shared.sms_observability import trace as obs_trace
from modules.shared.sms_http import paced_get_json
from modules.shared.sms_records import sanitize_cve_id

NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns"

# Response caps: NVD pages are large; OSV records are smaller.
NVD_SEARCH_MAX_BYTES = 4 * 1024 * 1024
NVD_LOOKUP_MAX_BYTES = 2 * 1024 * 1024
OSV_LOOKUP_MAX_BYTES = 2 * 1024 * 1024

_SEARCH_ASPECT = get_aspect("intel.search")


def _observed_lookup(operation: str):
    """Decorator: trace one intel lookup, log count + degraded reason.

    LAW 4: only CVE ids (already bounded/sanitized at the call site),
    counts, and fixed failure reasons are logged — never intel payload
    text. Bodies untouched (decorator lines only). Sibling of the
    research/scanner runner decorators.
    """

    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            started = time.monotonic()
            degraded = False
            reason = ""
            count = 0
            try:
                with obs_trace(_SEARCH_ASPECT, operation):
                    result = fn(*args, **kwargs)
            except Exception:
                degraded = True
                reason = "error"
                raise
            else:
                if isinstance(result, list):
                    count = len(result)
                elif isinstance(result, dict):
                    vulns = result.get("vulnerabilities")
                    count = len(vulns) if isinstance(vulns, list) else 1
                elif result is not None:
                    count = 1
                reason = "" if count else "empty"
                degraded = not count
            finally:
                duration_ms = round((time.monotonic() - started) * 1000, 3)
                obs_log(
                    _SEARCH_ASPECT,
                    f"{operation}.result",
                    message=f"{operation} finished",
                    count=count,
                    degraded=degraded,
                    reason=reason,
                    duration_ms=duration_ms,
                )
                obs_record_metric(
                    _SEARCH_ASPECT, f"{operation}.duration_ms", duration_ms, unit="ms"
                )
            return result

        return inner

    return wrap


@_observed_lookup("nvd_search")
def nvd_search(
    keyword: str,
    *,
    results_per_page: int = 10,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Keyword search NVD for recent CVE records. Optional NVD_API_KEY raises rate limits."""
    keyword = keyword.strip()[:256]
    if not keyword:
        raise ValueError("NVD search keyword must be non-empty.")
    params = {
        "keywordSearch": keyword,
        "resultsPerPage": str(max(1, min(results_per_page, 50))),
    }
    headers = {
        "User-Agent": "Secure-Mitigation-System/0.1",
        "Accept": "application/json",
    }
    api_key = os.getenv("NVD_API_KEY", "").strip()
    if api_key:
        headers["apiKey"] = api_key
    return paced_get_json(
        NVD_BASE, params=params, headers=headers, timeout=timeout, max_bytes=NVD_SEARCH_MAX_BYTES
    )


@_observed_lookup("nvd_lookup")
def nvd_lookup(cve_id: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Fetch one NVD record by CVE ID."""
    cve_id = cve_id.strip().upper()[:32]
    if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", cve_id):
        raise ValueError(f"Invalid CVE ID: {cve_id!r}.")
    params = {"cveId": cve_id}
    headers = {"User-Agent": "Secure-Mitigation-System/0.1", "Accept": "application/json"}
    api_key = os.getenv("NVD_API_KEY", "").strip()
    if api_key:
        headers["apiKey"] = api_key
    return paced_get_json(
        NVD_BASE, params=params, headers=headers, timeout=timeout, max_bytes=NVD_LOOKUP_MAX_BYTES
    )


def summarize_nvd_record(item: Mapping[str, Any]) -> dict[str, Any]:
    """Extract CVE ID, description, CVSS, CWE, references from one NVD cve item."""
    cve = item.get("cve", item) if isinstance(item, Mapping) else {}
    cve_id = cve.get("id", "")
    descriptions = cve.get("descriptions") or []
    description = ""
    for d in descriptions:
        if isinstance(d, dict) and d.get("lang") == "en" and d.get("value"):
            description = str(d["value"])
            break
    metrics = cve.get("metrics") or {}
    cvss: list[dict[str, str]] = []
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for entry in metrics.get(key) or []:
            data = (entry or {}).get("cvssData") or {}
            if data.get("baseScore") is not None:
                cvss.append(
                    {
                        "version": str(data.get("version", "")),
                        "baseScore": str(data.get("baseScore")),
                        "vector": str(data.get("vectorString", "")),
                        "severity": str(data.get("baseSeverity", "")),
                    }
                )
    weaknesses = []
    for w in cve.get("weaknesses") or []:
        for d in (w or {}).get("description") or []:
            if isinstance(d, dict) and d.get("value"):
                weaknesses.append(str(d["value"]))
    references = []
    for r in cve.get("references") or []:
        if isinstance(r, dict) and r.get("url"):
            references.append({"url": str(r["url"]), "source": str(r.get("source", ""))})
    return {
        "cve_id": cve_id,
        "description": description[:2000],
        "cvss": cvss[:4],
        "cwe": sorted(set(weaknesses))[:8],
        "published": cve.get("published"),
        "lastModified": cve.get("lastModified"),
        "references": references[:10],
    }


def summarize_nvd_search(payload: Mapping[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    vulns = payload.get("vulnerabilities") or []
    for item in vulns[:limit]:
        try:
            out.append(summarize_nvd_record(item))
        except Exception:
            continue
    return out


@_observed_lookup("osv_lookup")
def osv_lookup_by_cve(cve_id: str, *, timeout: float = 30.0) -> dict[str, Any] | None:
    """Fetch an OSV record by CVE alias (OSV indexes CVE IDs directly).

    Used by the CVE workflow as a keyless second opinion alongside NVD:
    OSV often carries the fix commit / fixed-version range NVD omits.
    Malformed CVE ids return None without touching the network.
    """
    safe = sanitize_cve_id(cve_id)
    if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", safe):
        return None
    return paced_get_json(
        f"{OSV_VULN_URL}/{safe}",
        timeout=timeout,
        max_bytes=OSV_LOOKUP_MAX_BYTES,
    )


async def intel_for_demo(
    themes: Sequence[str],
    *,
    per_theme: int = 5,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Gather recent CVE context for AI demo generation (blocking network in thread)."""
    import asyncio as _asyncio

    theme_count = len(list(themes)[:6])
    obs_log(
        _SEARCH_ASPECT,
        "intel_for_demo.start",
        message="demo intel gather started",
        theme_count=theme_count,
        per_theme=per_theme,
    )
    started = time.monotonic()
    status = "ok"

    def _fetch() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for theme in themes[:6]:
            try:
                payload = nvd_search(theme, results_per_page=per_theme, timeout=timeout)
                out.extend(summarize_nvd_search(payload, limit=per_theme))
            except Exception as exc:
                out.append({"theme": theme, "error": f"{type(exc).__name__}"})
        return out[:30]

    try:
        with obs_trace(_SEARCH_ASPECT, "intel_for_demo"):
            gathered = await _asyncio.to_thread(_fetch)
    except Exception:
        status = "error"
        raise
    else:
        return gathered
    finally:
        duration_ms = round((time.monotonic() - started) * 1000, 3)
        fields: dict[str, Any] = {"status": status, "theme_count": theme_count}
        if status != "error":
            try:
                fields["record_count"] = len(gathered)
            except Exception:
                pass
        # LAW 4: theme names are caller-supplied words, not intel text, but
        # only their count is logged — never gathered CVE text.
        obs_log(
            _SEARCH_ASPECT,
            "intel_for_demo.result",
            message="demo intel gather finished",
            duration_ms=duration_ms,
            **fields,
        )
        obs_record_metric(_SEARCH_ASPECT, "intel_for_demo.duration_ms", duration_ms, unit="ms")
