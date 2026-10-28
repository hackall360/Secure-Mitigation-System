# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Dependency-Track client: upload a CycloneDX BOM, poll findings, map records.

Dependency-Track is a SERVER, not a CLI scanner: it needs a running instance
plus an API key. Both come from env and both unset means "skip silently":

- PURPLEBOX_DTRACK_URL (e.g. https://dtrack.internal)
- PURPLEBOX_DTRACK_API_KEY

Flow: build a minimal CycloneDX BOM from a requirements-style package list,
PUT it to /api/v1/bom, poll /api/v1/analysis per project until the scan
settles, map findings to ScannerRecord (scanner="dependency-track").
Uses only stdlib urllib like research.py: same pacing/backoff/cap discipline.
Never raises: any failure degrades to [].
"""

from __future__ import annotations

import base64
import json
import os
import random
import time
import urllib.parse
import urllib.request

from scanner_binaries import ScannerRecord

USER_AGENT = "Secure-Mitigation-System/0.1 dtrack-client"
MAX_BODY_BYTES = 8 * 1024 * 1024


def configured() -> tuple[str, str] | None:
    """(base_url, api_key) when both env vars are set, else None."""
    url = os.getenv("PURPLEBOX_DTRACK_URL", "").strip().rstrip("/")
    key = os.getenv("PURPLEBOX_DTRACK_API_KEY", "").strip()
    if url and key:
        return url, key
    return None


def _request(
    base: str,
    key: str,
    method: str,
    path: str,
    body: dict | None = None,
    *,
    timeout: float = 30.0,
    tries: int = 3,
) -> dict | list | None:
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(tries):
        time.sleep(1.0 + random.uniform(0, 1.0))
        request = urllib.request.Request(
            base + path,
            data=data,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Api-Key": key,
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_BODY_BYTES + 1)
            if len(raw) > MAX_BODY_BYTES:
                return None
            return json.loads(raw.decode("utf-8"))
        except Exception:
            time.sleep(2**attempt + random.uniform(0, 1.0))
    return None


def build_bom(project_name: str, packages: list[tuple[str, str]]) -> dict:
    """Minimal CycloneDX 1.5 BOM from (name, version) pairs."""
    components = [
        {
            "type": "library",
            "bom-ref": f"{name}@{version}",
            "name": name[:128],
            "version": version[:64],
            "purl": f"pkg:pypi/{urllib.parse.quote(name)}@{urllib.parse.quote(version)}",
        }
        for name, version in packages[:200]
        if name.strip()
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": project_name[:128]}},
        "components": components,
    }


def parse_dtrack_findings(payload: dict | list) -> list[ScannerRecord]:
    """Map Dependency-Track /api/v1/finding/project/{uuid} rows to records."""
    rows = payload if isinstance(payload, list) else []
    out: list[ScannerRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        vuln = row.get("vulnerability") or {}
        comp = row.get("component") or {}
        analysis = row.get("analysis") or {}
        if isinstance(analysis, dict) and analysis.get("state") == "FALSE_POSITIVE":
            continue
        out.append(
            ScannerRecord(
                scanner="dependency-track",
                cve_id=str(vuln.get("vulnId", "")),
                package=str(comp.get("name", ""))[:128],
                installed_version=str(comp.get("version", ""))[:64],
                severity=str(vuln.get("severity", ""))[:16],
                cvss=str(vuln.get("cvssV3BaseScore") or vuln.get("cvssV2BaseScore") or "")[:16],
                title=str(vuln.get("title", ""))[:256],
                summary=str(vuln.get("description", "")),
                cwe=tuple(str(c)[:16] for c in (vuln.get("cwes") or [])[:8]),
            )
        )
    return out


def scan_packages(
    project_name: str,
    packages: list[tuple[str, str]],
    *,
    timeout: float = 30.0,
    poll_tries: int = 12,
) -> list[ScannerRecord]:
    """Upload BOM, poll for findings. [] when unconfigured or on any failure."""
    cfg = configured()
    if not cfg:
        return []
    base, key = cfg
    if not packages:
        return []
    bom = build_bom(project_name, packages)
    token_resp = _request(
        base,
        key,
        "PUT",
        "/api/v1/bom",
        {
            "projectName": project_name[:128],
            "bom": base64.b64encode(json.dumps(bom).encode()).decode(),
        },
        timeout=timeout,
    )
    if not isinstance(token_resp, dict) or not token_resp.get("token"):
        return []
    token = token_resp["token"]
    project_uuid: str | None = None
    for _ in range(poll_tries):
        status = _request(
            base,
            key,
            "GET",
            f"/api/v1/bom/token/{urllib.parse.quote(str(token))}",
            timeout=timeout,
            tries=1,
        )
        if isinstance(status, dict) and status.get("processing") is False:
            project_uuid = str(status.get("project") or "") or None
            break
        time.sleep(5)
    lookup = project_uuid or project_name
    findings = _request(
        base,
        key,
        "GET",
        f"/api/v1/finding/project/{urllib.parse.quote(lookup)}",
        timeout=timeout,
        tries=2,
    )
    return parse_dtrack_findings(findings) if isinstance(findings, list) else []
