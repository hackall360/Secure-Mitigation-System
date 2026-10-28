# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Scanner transports: canned-report mapping + absent-binary degradation."""

import scanner_binaries as sb
import scanner_dtrack as dt


def test_trivy_mapping():
    payload = {
        "Results": [
            {
                "Target": "package-lock.json",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2024-10491",
                        "PkgName": "express",
                        "InstalledVersion": "4.18.0",
                        "FixedVersion": "4.21.2",
                        "Severity": "HIGH",
                        "Title": "express vulnerable",
                        "Description": "x" * 5000,
                        "CVSS": {"nvd": {"V3Score": 8.1}},
                        "CweIDs": ["CWE-400"],
                        "References": ["https://example.invalid/a"],
                    }
                ],
            }
        ]
    }
    recs = sb.parse_trivy_report(payload)
    assert len(recs) == 1
    r = recs[0]
    assert (r.scanner, r.cve_id, r.package) == ("trivy", "CVE-2024-10491", "express")
    assert r.fixed_version == "4.21.2" and r.cvss == "8.1"
    assert len(r.summary) == 1500 and r.cwe == ("CWE-400",)


def test_grype_mapping():
    payload = {
        "matches": [
            {
                "vulnerability": {
                    "id": "CVE-2024-3094",
                    "severity": "Critical",
                    "description": "xz backdoor",
                    "fix": {"versions": ["5.6.2"]},
                    "cvss": [{"version": "3.1", "metrics": {"baseScore": 9.0}}],
                    "urls": [{"url": "https://example.invalid/b"}],
                },
                "artifact": {"name": "xz", "version": "5.6.1"},
            }
        ]
    }
    (r,) = sb.parse_grype_report(payload)
    assert (r.scanner, r.cve_id, r.fixed_version) == ("grype", "CVE-2024-3094", "5.6.2")
    assert r.cvss == "9.0"


def test_osv_scanner_mapping():
    payload = {
        "results": [
            {
                "source": {"path": "req.txt", "type": "lockfile"},
                "packages": [
                    {
                        "package": {"name": "django", "version": "3.2", "ecosystem": "PyPI"},
                        "vulnerabilities": [
                            {
                                "id": "GHSA-x",
                                "summary": "s",
                                "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N"}],
                                "references": [{"url": "https://example.invalid/c"}],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    (r,) = sb.parse_osv_scanner_report(payload)
    assert (r.scanner, r.package, r.severity) == ("osv-scanner", "django", "CVSS:3.1/AV:N")


def test_depcheck_mapping():
    payload = {
        "dependencies": [
            {
                "fileName": "spring-core-5.3.jar",
                "vulnerabilities": [
                    {
                        "name": "CVE-2022-22965",
                        "severity": "Critical",
                        "description": "Spring4Shell",
                        "cvssv3": {"baseScore": 9.8},
                        "cwes": [{"name": "CWE-94"}],
                    }
                ],
            }
        ]
    }
    (r,) = sb.parse_depcheck_report(payload)
    assert (r.scanner, r.cve_id, r.cvss) == ("dependency-check", "CVE-2022-22965", "9.8")
    assert r.cwe == ("CWE-94",)


def test_dtrack_mapping_skips_false_positives():
    payload = [
        {
            "vulnerability": {
                "vulnId": "CVE-2021-1",
                "severity": "HIGH",
                "title": "t",
                "description": "d",
            },
            "component": {"name": "lodash", "version": "4.17.20"},
            "analysis": {"state": "FALSE_POSITIVE"},
        },
        {
            "vulnerability": {
                "vulnId": "CVE-2021-2",
                "severity": "MEDIUM",
                "cvssV3BaseScore": 5.4,
            },
            "component": {"name": "lodash", "version": "4.17.20"},
            "analysis": {"state": "EXPLOITABLE"},
        },
    ]
    (r,) = dt.parse_dtrack_findings(payload)
    assert (r.scanner, r.cve_id, r.cvss) == ("dependency-track", "CVE-2021-2", "5.4")


def test_dtrack_bom_shape():
    bom = dt.build_bom("proj", [("django", "3.2.25")])
    assert bom["bomFormat"] == "CycloneDX"
    assert bom["components"][0]["name"] == "django"


def test_absent_binaries_degrade_to_empty():
    assert sb.run_trivy("/nonexistent", timeout=1) == []
    assert sb.run_grype("/nonexistent", timeout=1) == []
    assert sb.run_osv_scanner("/nonexistent", timeout=1) == []
    assert sb.run_dependency_check("/nonexistent", timeout=1) == []
    # dtrack unconfigured (no env in tests) -> []
    assert dt.scan_packages("p", [("a", "1")]) == []
    # malformed payloads never raise
    assert sb.parse_trivy_report({}) == []
    assert sb.parse_grype_report([]) == []


def test_cve_records_series_never_raises_and_dedupes(monkeypatch):
    """I3: the CVE series fans out per id, dedupes, and never raises."""
    import research as _research

    def fake_circl(cve):
        return _research.ResearchRecord(source="circl", cve_id=cve, title="t", summary="s")

    def fake_osv(cve):
        raise RuntimeError("osv down")

    def fake_epss(cve):
        return _research.ResearchRecord(source="epss", cve_id=cve, title="e", summary="s")

    monkeypatch.setattr(_research, "circl_lookup", fake_circl)
    monkeypatch.setattr(_research, "osv_lookup", fake_osv)
    monkeypatch.setattr(_research, "epss_score", fake_epss)
    monkeypatch.setattr(_research, "ghsa_search", lambda package: [])
    recs = _research.cve_records(["CVE-2024-3094", "bogus!!", "CVE-2024-3094"])
    assert [r.source for r in recs] == ["circl", "epss"]
    assert all(r.cve_id == "CVE-2024-3094" for r in recs)


def test_cve_records_empty_for_no_valid_ids():
    import research as _research

    assert _research.cve_records([]) == []
    assert _research.cve_records(["not-a-cve"]) == []


def test_web_notes_canned_search_plus_extract(monkeypatch):
    """I4: web notes use search hits + intro extracts, dedupe, never raise."""
    import research as _research

    calls = []

    def fake_get(url, *, params=None, headers=None):
        calls.append(params)
        if params.get("list") == "search":
            return {
                "query": {
                    "search": [
                        {"title": "SQL injection", "snippet": "bad <b>query</b>"},
                    ]
                }
            }
        return {"query": {"pages": {"1": {"extract": "Intro text here."}}}}

    monkeypatch.setattr(_research, "_get_json", fake_get)
    recs = _research.web_notes(["sql injection", "x"])
    assert len(recs) == 1
    assert recs[0].source == "web"
    assert recs[0].title == "SQL injection"
    assert recs[0].summary == "Intro text here."
    assert recs[0].extra == {"query": "sql injection"}


def test_web_notes_transport_failure_degrades_to_empty(monkeypatch):
    import research as _research

    monkeypatch.setattr(
        _research, "_get_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    assert _research.web_notes(["sql injection"]) == []
    assert _research.web_notes([]) == []


def test_http_leaf_back_compat_aliases_match_sms_http():
    """research._pace/_get_json/_post_json are re-exports of the moved leaf."""
    import research as _research
    import sms_http as _leaf

    assert _research._pace is _leaf._pace
    assert _research._get_json is _leaf.paced_get_json
    assert _research._post_json is _leaf.paced_post_json
    assert _research.USER_AGENT == _leaf.USER_AGENT
    assert _research.MAX_BODY_BYTES == _leaf.DEFAULT_MAX_BYTES


def test_http_leaf_pacing_is_per_host(monkeypatch):
    """One host's backoff must not stall an unrelated host."""
    import sms_http as _leaf

    monkeypatch.setattr(_leaf, "_last_calls", {})
    seen: list[str] = []
    monkeypatch.setattr(_leaf.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(_leaf.time, "sleep", lambda s: seen.append(f"sleep:{s:.0f}"))
    monkeypatch.setattr(_leaf.random, "uniform", lambda a, b: 0.0)
    _leaf._pace("a.example")
    assert seen == []  # first touch of a host never sleeps
    _leaf._pace("a.example")
    assert len(seen) == 1  # same host back-to-back enforces the minimum gap
    _leaf._pace("b.example")
    assert len(seen) == 1  # a fresh host is not stalled by a.example's clock
    _leaf._last_calls["slow.example"] = 100.0
    _leaf._pace("slow.example")
    assert len(seen) == 2
    assert _leaf._last_calls["a.example"] == 100.0


def test_intel_search_routes_through_sms_http(monkeypatch):
    """nvd_search/nvd_lookup/osv_lookup_by_cve call paced_get_json with caps."""
    import intel_search as _intel

    calls: list[tuple] = []

    def fake_paced(url, params=None, headers=None, timeout=30.0, tries=3, max_bytes=0):
        calls.append((url, params, max_bytes))
        return {"ok": True}

    monkeypatch.setattr(_intel, "paced_get_json", fake_paced)
    assert _intel.nvd_search("openssl") == {"ok": True}
    assert _intel.nvd_lookup("CVE-2024-3094") == {"ok": True}
    assert _intel.osv_lookup_by_cve("CVE-2024-3094") == {"ok": True}
    urls = [c[0] for c in calls]
    assert urls[0].startswith(_intel.NVD_BASE) and urls[1].startswith(_intel.NVD_BASE)
    assert urls[2].startswith(_intel.OSV_VULN_URL)
    assert calls[0][2] == _intel.NVD_SEARCH_MAX_BYTES
    assert calls[1][2] == _intel.NVD_LOOKUP_MAX_BYTES
    assert calls[2][2] == _intel.OSV_LOOKUP_MAX_BYTES


def test_dtrack_request_uses_shared_paced_transport(monkeypatch):
    """scanner_dtrack._request delegates to sms_http, never raises."""
    import scanner_dtrack as _dt

    calls: list[tuple] = []

    def fake_paced(method, url, *, body=None, headers=None, timeout=30.0, tries=3, max_bytes=0):
        calls.append((method, url, headers, max_bytes))
        return [{"vulnerability": {"vulnId": "CVE-1"}, "component": {}}]

    monkeypatch.setattr(_dt, "paced_request_json", fake_paced)
    out = _dt._request("https://dtrack.internal", "k", "GET", "/api/v1/finding/x")
    assert isinstance(out, list)
    method, url, headers, cap = calls[0]
    assert method == "GET" and url == "https://dtrack.internal/api/v1/finding/x"
    assert headers["X-Api-Key"] == "k" and cap == _dt.MAX_BODY_BYTES
    monkeypatch.setattr(
        _dt, "paced_request_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    assert _dt._request("https://dtrack.internal", "k", "GET", "/x") is None


def test_scanner_which_cache_and_stdout_cap(monkeypatch):
    """PATH lookups cached; oversize stdout degrades to None."""
    import scanner_binaries as _sb

    monkeypatch.setattr(_sb, "_WHICH_CACHE", {})
    lookups: list[str] = []
    monkeypatch.setattr(_sb.shutil, "which", lambda b: lookups.append(b) or None)
    assert _sb._cached_which("definitely-not-a-scanner-xyz") is None
    assert _sb._cached_which("definitely-not-a-scanner-xyz") is None
    assert lookups == ["definitely-not-a-scanner-xyz"]
    monkeypatch.setattr(_sb, "_cached_which", lambda b: "/bin/true")
    monkeypatch.setattr(_sb, "STDOUT_CAP_BYTES", 4)

    class _Proc:
        stdout = b"12345"

    monkeypatch.setattr(_sb.subprocess, "run", lambda *a, **k: _Proc())
    assert _sb._run_json("trivy", ["x"]) is None


def test_agents_schema_cache_and_single_pass_extractor():
    """Schema dict reused per model class; extractor is brace-aware in one pass."""
    from agents import _SCHEMA_CACHE, _extract_json_object, _schema_for
    from agents import RedTeamFinding as _Red

    _SCHEMA_CACHE.clear()
    first = _schema_for(_Red)
    assert _schema_for(_Red) is first
    assert _extract_json_object('```json\n{"a": "x { y } z", "b": 1}\n```') == (
        '{"a": "x { y } z", "b": 1}'
    )
    assert _extract_json_object('lead {"x": 1, "s": "a}b"} tail') == '{"x": 1, "s": "a}b"}'
    assert _extract_json_object("no braces here") == "no braces here"
