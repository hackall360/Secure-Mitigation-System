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

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Mapping, Sequence

NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns"


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
    url = NVD_BASE + "?" + urllib.parse.urlencode(params)
    headers = {
        "User-Agent": "Secure-Mitigation-System/0.1",
        "Accept": "application/json",
    }
    api_key = os.getenv("NVD_API_KEY", "").strip()
    if api_key:
        headers["apiKey"] = api_key
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(4 * 1024 * 1024)
    return json.loads(body.decode("utf-8"))


def nvd_lookup(cve_id: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Fetch one NVD record by CVE ID."""
    cve_id = cve_id.strip().upper()[:32]
    if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", cve_id):
        raise ValueError(f"Invalid CVE ID: {cve_id!r}.")
    params = {"cveId": cve_id}
    url = NVD_BASE + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "Secure-Mitigation-System/0.1", "Accept": "application/json"}
    api_key = os.getenv("NVD_API_KEY", "").strip()
    if api_key:
        headers["apiKey"] = api_key
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(2 * 1024 * 1024)
    return json.loads(body.decode("utf-8"))


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


def osv_lookup_by_cve(cve_id: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Fetch an OSV record by CVE alias (OSV indexes CVE IDs directly)."""
    safe = re.sub(r"[^A-Za-z0-9\-_:.]", "", cve_id.strip().upper())[:32]
    request = urllib.request.Request(
        f"{OSV_VULN_URL}/{safe}",
        headers={"User-Agent": "Secure-Mitigation-System/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(2 * 1024 * 1024)
    return json.loads(body.decode("utf-8"))


async def intel_for_demo(
    themes: Sequence[str],
    *,
    per_theme: int = 5,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Gather recent CVE context for AI demo generation (blocking network in thread)."""
    import asyncio as _asyncio

    def _fetch() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for theme in themes[:6]:
            try:
                payload = nvd_search(theme, results_per_page=per_theme, timeout=timeout)
                out.extend(summarize_nvd_search(payload, limit=per_theme))
            except Exception as exc:
                out.append({"theme": theme, "error": f"{type(exc).__name__}"})
        return out[:30]

    return await _asyncio.to_thread(_fetch)
