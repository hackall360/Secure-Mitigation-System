# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Scanner transports: canned-report mapping + absent-binary degradation."""

import modules.intel.scanner_binaries as sb
import modules.intel.scanner_dtrack as dt


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
    import modules.intel.research as _research

    def fake_circl(cve):
        return _research.ResearchRecord(source="circl", cve_id=cve, title="t", summary="s")

    def fake_osv(cve):
        raise RuntimeError("osv down")

    def fake_epss(cve):
        return _research.ResearchRecord(source="epss", cve_id=cve, title="e", summary="s")

    monkeypatch.setattr(_research, "circl_lookup", fake_circl)
    monkeypatch.setattr(_research, "osv_lookup", fake_osv)
    monkeypatch.setattr(_research, "epss_score", fake_epss)
    monkeypatch.setattr(_research, "ghsa_lookup_by_cve", lambda cve: [])
    recs = _research.cve_records(["CVE-2024-3094", "bogus!!", "CVE-2024-3094"])
    assert [r.source for r in recs] == ["circl", "epss"]
    assert all(r.cve_id == "CVE-2024-3094" for r in recs)


def test_cve_records_empty_for_no_valid_ids():
    import modules.intel.research as _research

    assert _research.cve_records([]) == []
    assert _research.cve_records(["not-a-cve"]) == []


def test_web_notes_canned_search_plus_extract(monkeypatch):
    """I4: web notes use search hits + intro extracts, dedupe, never raise."""
    import modules.intel.research as _research

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
    import modules.intel.research as _research

    monkeypatch.setattr(
        _research, "_get_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    assert _research.web_notes(["sql injection"]) == []
    assert _research.web_notes([]) == []


def _canned_ghsa_advisories():
    return [
        {
            "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
            "cve_id": "CVE-2024-3094",
            "summary": "xz backdoor",
            "description": "Malicious code in xz.",
            "severity": "critical",
            "cwes": [{"cwe_id": "CWE-506"}],
            "references": ["https://example.invalid/ghsa"],
            "epss": {"percentage": 0.12, "percentile": 0.34},
            "cvss_severities": {
                "cvss_v4": {"score": 9.1, "vector_string": "CVSS:4.0/AV:N/AC:L"},
                "cvss_v3": {"score": 8.0, "vector_string": "CVSS:3.1/AV:N/AC:L"},
            },
            "vulnerabilities": [{"package": {"name": "xz"}, "first_patched_version": "5.6.2"}],
        }
    ]


def test_ghsa_lookup_by_cve_uses_cve_id_param(monkeypatch):
    """O1: CVE-id lookup queries ?cve_id=, carries EPSS + CVSSv4 fields."""
    import modules.intel.research as _research

    calls = {}

    def fake_get(url, *, params=None, headers=None):
        calls["url"] = url
        calls["params"] = dict(params or {})
        calls["headers"] = dict(headers or {})
        return _canned_ghsa_advisories()

    monkeypatch.setattr(_research, "_get_json", fake_get)
    recs = _research.ghsa_lookup_by_cve("CVE-2024-3094")
    assert len(recs) == 1
    assert calls["params"].get("cve_id") == "CVE-2024-3094"
    assert "package" not in calls["params"]
    assert calls["url"] == "https://api.github.com/advisories"
    r = recs[0]
    assert (r.source, r.cve_id) == ("ghsa", "CVE-2024-3094")
    assert r.cvss == "9.1"  # cvss v4 preferred over v3
    assert r.extra["epss_percentile"] == "0.34"
    assert r.extra["first_patched_version"] == "5.6.2"


def test_cve_records_uses_ghsa_cve_lookup(monkeypatch):
    """O1: cve_records surfaces the GHSA record for the CVE."""
    import modules.intel.research as _research

    monkeypatch.setattr(_research, "circl_lookup", lambda cve: None)
    monkeypatch.setattr(_research, "osv_lookup", lambda cve: None)
    monkeypatch.setattr(_research, "epss_score", lambda cve: None)
    monkeypatch.setattr(
        _research,
        "ghsa_lookup_by_cve",
        lambda cve, **kw: [
            _research.ResearchRecord(source="ghsa", cve_id=cve, title="t", summary="s")
        ],
    )
    recs = _research.cve_records(["CVE-2024-3094"])
    assert [(r.source, r.cve_id) for r in recs] == [("ghsa", "CVE-2024-3094")]


def test_ghsa_lookup_by_cve_never_raises(monkeypatch):
    """O1: invalid CVE id -> []; transport failure -> []."""
    import modules.intel.research as _research

    assert _research.ghsa_lookup_by_cve("bogus!!") == []
    assert _research.ghsa_lookup_by_cve("") == []
    monkeypatch.setattr(
        _research, "_get_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    assert _research.ghsa_lookup_by_cve("CVE-2024-3094") == []


def test_http_leaf_back_compat_aliases_match_sms_http():
    """research._pace/_get_json/_post_json are re-exports of the moved leaf."""
    import modules.intel.research as _research
    import modules.shared.sms_http as _leaf

    assert _research._pace is _leaf._pace
    assert _research._get_json is _leaf.paced_get_json
    assert _research._post_json is _leaf.paced_post_json
    assert _research.USER_AGENT == _leaf.USER_AGENT
    assert _research.MAX_BODY_BYTES == _leaf.DEFAULT_MAX_BYTES


def test_http_leaf_pacing_is_per_host(monkeypatch):
    """One host's backoff must not stall an unrelated host."""
    import modules.shared.sms_http as _leaf

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
    import modules.intel.intel_search as _intel

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
    import modules.intel.scanner_dtrack as _dt

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
    import modules.intel.scanner_binaries as _sb

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
    from modules.core.agents import _SCHEMA_CACHE, _extract_json_object, _schema_for
    from modules.core.agents import RedTeamFinding as _Red

    _SCHEMA_CACHE.clear()
    first = _schema_for(_Red)
    assert _schema_for(_Red) is first
    assert _extract_json_object('```json\n{"a": "x { y } z", "b": 1}\n```') == (
        '{"a": "x { y } z", "b": 1}'
    )
    assert _extract_json_object('lead {"x": 1, "s": "a}b"} tail') == '{"x": 1, "s": "a}b"}'
    assert _extract_json_object("no braces here") == "no braces here"


def test_kev_lookup_canned_match_and_miss(monkeypatch):
    """O2 red: kev_lookup finds cveID in the CISA KEV catalog, else None."""
    import modules.intel.research as _research

    _research._kev_cache_clear()
    catalog = {
        "count": 1,
        "vulnerabilities": [
            {
                "cveID": "CVE-2024-3094",
                "vulnerabilityName": "XZ Utils Backdoor",
                "shortDescription": "XZ backdoor.",
                "dueDate": "2024-05-02",
                "knownRansomwareCampaignUse": "Unknown",
            }
        ],
    }
    monkeypatch.setattr(_research, "_get_json", lambda *a, **k: catalog)
    rec = _research.kev_lookup("CVE-2024-3094")
    assert rec is not None and rec.source == "kev"
    assert rec.cve_id == "CVE-2024-3094"
    assert rec.extra["kev_listed"] is True
    assert rec.extra["due_date"] == "2024-05-02"
    assert rec.extra["ransomware"] == "Unknown"
    assert _research.kev_lookup("CVE-2024-9999") is None
    assert _research.kev_lookup("bogus!!") is None


def test_kev_lookup_caches_catalog_across_ids(monkeypatch):
    """Q2: two kev_lookup calls for different ids trigger exactly one fetch."""
    import modules.intel.research as _research

    _research._kev_cache_clear()
    catalog = {
        "count": 1,
        "vulnerabilities": [
            {
                "cveID": "CVE-2024-3094",
                "vulnerabilityName": "XZ Utils Backdoor",
                "shortDescription": "XZ backdoor.",
                "dueDate": "2024-05-02",
                "knownRansomwareCampaignUse": "Unknown",
            }
        ],
    }
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        return catalog

    monkeypatch.setattr(_research, "_get_json", fake_get)
    try:
        rec = _research.kev_lookup("CVE-2024-3094")
        assert rec is not None and rec.source == "kev"
        assert _research.kev_lookup("CVE-2024-9999") is None
        assert calls["n"] == 1
    finally:
        _research._kev_cache_clear()


def test_kev_lookup_failures_not_cached_then_success(monkeypatch):
    """Q2: RuntimeError / non-dict fetches are NOT cached; next call retries."""
    import modules.intel.research as _research

    _research._kev_cache_clear()
    catalog = {
        "count": 1,
        "vulnerabilities": [
            {
                "cveID": "CVE-2024-3094",
                "vulnerabilityName": "XZ Utils Backdoor",
                "shortDescription": "XZ backdoor.",
                "dueDate": "2024-05-02",
                "knownRansomwareCampaignUse": "Unknown",
            }
        ],
    }
    calls = {"n": 0}
    mode = {"kind": "raise"}

    def fake_get(*a, **k):
        calls["n"] += 1
        if mode["kind"] == "raise":
            raise RuntimeError("down")
        if mode["kind"] == "nondict":
            return ["not", "a", "dict"]
        return catalog

    monkeypatch.setattr(_research, "_get_json", fake_get)
    try:
        assert _research.kev_lookup("CVE-2024-3094") is None
        mode["kind"] = "nondict"
        assert _research.kev_lookup("CVE-2024-3094") is None
        mode["kind"] = "ok"
        rec = _research.kev_lookup("CVE-2024-3094")
        assert rec is not None and rec.source == "kev"
        assert calls["n"] == 3
    finally:
        _research._kev_cache_clear()


def test_kev_lookup_transport_failure_degrades_to_none(monkeypatch):
    """O2 red: KEV oversize-cap/transport failure degrades to None, never raises."""
    import modules.intel.research as _research

    _research._kev_cache_clear()
    monkeypatch.setattr(
        _research, "_get_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    assert _research.kev_lookup("CVE-2024-3094") is None


def test_cve_records_includes_kev_record(monkeypatch):
    """O2 red: cve_records fans out to kev_lookup as a 5th source per CVE."""
    import modules.intel.research as _research

    monkeypatch.setattr(_research, "circl_lookup", lambda cve: None)
    monkeypatch.setattr(_research, "osv_lookup", lambda cve: None)
    monkeypatch.setattr(_research, "epss_score", lambda cve: None)
    monkeypatch.setattr(_research, "ghsa_lookup_by_cve", lambda cve: [])
    monkeypatch.setattr(
        _research,
        "kev_lookup",
        lambda cve: _research.ResearchRecord(
            source="kev", cve_id=cve, title="t", summary="s", extra={"kev_listed": True}
        ),
    )
    recs = _research.cve_records(["CVE-2024-3094"])
    assert [r.source for r in recs] == ["kev"]
    assert all(r.cve_id == "CVE-2024-3094" for r in recs)


def test_dtrack_poll_backs_off_and_exits_early(monkeypatch):
    """Poll uses exponential backoff; instant-done exits without sleeping."""
    import modules.intel.scanner_dtrack as _dt

    sleeps = []
    monkeypatch.setattr(_dt.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(_dt, "configured", lambda: ("http://x", "k"))
    monkeypatch.setattr(_dt, "build_bom", lambda *a: {})
    calls = {"n": 0}

    def fake_request(base, key, method, path, body=None, **kwargs):
        calls["n"] += 1
        if "bom/token" in path:
            return {"processing": False, "project": "uuid-1"}
        if path == "/api/v1/bom":
            return {"token": "t"}
        return []

    monkeypatch.setattr(_dt, "_request", fake_request)
    out = _dt.scan_packages("p", [("a", "1")])
    assert calls["n"] == 3 and sleeps == [] and out == []


def test_r2_osv_and_circl_lookups_use_raised_cap(monkeypatch):
    """R2: OSV/CIRCL direct CVE fetches use MAX_MAX_BYTES like the KEV path."""
    import modules.intel.research as _research
    from modules.shared.sms_http import MAX_MAX_BYTES

    caps: dict[str, int] = {}

    def fake_get(url, **kwargs):
        caps[url] = kwargs.get("max_bytes", -1)
        return {"id": "CVE-2024-3094", "summary": "s"}

    monkeypatch.setattr(_research, "_get_json", fake_get)
    assert _research.osv_lookup("CVE-2024-3094") is not None
    assert _research.circl_lookup("CVE-2024-3094") is not None
    assert caps["https://api.osv.dev/v1/vulns/CVE-2024-3094"] == MAX_MAX_BYTES
    assert caps["https://cve.circl.lu/api/cve/CVE-2024-3094"] == MAX_MAX_BYTES


def test_r2_epss_score_sanitizes_cve_id(monkeypatch):
    """R2: epss_score normalizes through sanitize_cve_id (not ad-hoc casing)."""
    import modules.intel.research as _research

    seen: dict[str, str] = {}

    def fake_get(url, params=None, **kwargs):
        seen["cve"] = (params or {}).get("cve", "")
        return {"data": [{"epss": "0.5", "percentile": "0.9", "date": "2024-01-01"}]}

    monkeypatch.setattr(_research, "_get_json", fake_get)
    rec = _research.epss_score("  cve-2024-3094/ ")
    assert rec is not None and rec.source == "epss"
    assert rec.cve_id == "CVE-2024-3094"
    assert seen["cve"] == "CVE-2024-3094"


def test_r2_intel_osv_lookup_rejects_bad_cve_shape(monkeypatch):
    """R2: osv_lookup_by_cve validates CVE shape pre-fetch; invalid => None."""
    import modules.intel.intel_search as _intel

    def _boom(*a, **k):
        raise AssertionError("transport must not run for a malformed CVE id")

    monkeypatch.setattr(_intel, "paced_get_json", _boom)
    assert _intel.osv_lookup_by_cve("not-a-cve!!!") is None
    assert _intel.osv_lookup_by_cve("") is None


def _w5v2_1_osv_record():
    """W5 item 1 fixture: real OSV shape with one CVE alias, fix, CWE-502."""
    return {
        "id": "GHSA-xxxx",
        "summary": "Unsafe deserialization in widget",
        "details": "Deserialization of untrusted data CWE-502 allows code execution.",
        "published": "2024-01-01T00:00:00Z",
        "modified": "2024-01-02T00:00:00Z",
        "aliases": ["CVE-2024-1234"],
        "severity": [{"type": "CVSS_V3", "score": "9.8"}],
        "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.0"}]}]}],
        "references": [],
    }


def _w5v2_1_findings():
    from modules.workflows.deep_scan import StaticFinding

    return [
        StaticFinding(
            rule_id="py-pickle",
            title="Unsafe deserialization",
            severity="high",
            path="app.py",
            line=2,
            snippet="data = pickle.loads(blob)",
            cwe="CWE-502",
        )
    ]


def test_w5v2_1_stale_sources_dropped_from_queue_evidence(monkeypatch):
    """W5-1 RED: stale (>1d) KEV/EPSS dates drop to absent via real enrich path."""
    import datetime as _dt

    import modules.workflows.cve_workflow as _cw
    from modules.intel.research import ResearchRecord

    stale = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=2)).date().isoformat()

    def fake_kev(cve_id):
        return ResearchRecord(
            source="kev",
            cve_id=cve_id,
            title="t",
            summary="s",
            extra={"kev_listed": True, "kev_date": stale},
        )

    def fake_epss(cve_id):
        return ResearchRecord(
            source="epss",
            cve_id=cve_id,
            title="t",
            summary="s",
            extra={"epss": "0.9", "percentile": "0.95", "epss_date": stale},
        )

    monkeypatch.setattr(_cw, "kev_lookup", fake_kev)
    monkeypatch.setattr(_cw, "epss_score", fake_epss)
    summary = _cw.summarize_osv_vuln(_w5v2_1_osv_record())
    _cw._enrich_reach_signals(summary)
    assert summary["kev_listed"] is True
    assert summary["epss_percentile"] == 0.95
    ev = _cw._queue_evidence(summary)
    assert f"kev:stale:{stale}" in ev
    assert f"epss:stale:{stale}" in ev


def test_w5v2_1_fresh_sources_kept_in_queue_evidence(monkeypatch):
    """W5-1: fresh (today) KEV/EPSS dates keep listed/percentile in queue."""
    import datetime as _dt

    import modules.workflows.cve_workflow as _cw
    from modules.intel.research import ResearchRecord

    fresh = _dt.datetime.now(_dt.timezone.utc).date().isoformat()

    def fake_kev(cve_id):
        return ResearchRecord(
            source="kev",
            cve_id=cve_id,
            title="t",
            summary="s",
            extra={"kev_listed": True, "kev_date": fresh},
        )

    def fake_epss(cve_id):
        return ResearchRecord(
            source="epss",
            cve_id=cve_id,
            title="t",
            summary="s",
            extra={"epss": "0.9", "percentile": "0.95", "epss_date": fresh},
        )

    monkeypatch.setattr(_cw, "kev_lookup", fake_kev)
    monkeypatch.setattr(_cw, "epss_score", fake_epss)
    summary = _cw.summarize_osv_vuln(_w5v2_1_osv_record())
    _cw._enrich_reach_signals(summary)
    ev = _cw._queue_evidence(summary)
    assert "kev:listed" in ev
    assert "epss:0.95" in ev


def test_w5v2_1_research_stamps_live_epss_date(monkeypatch):
    """W5-1 RED: epss_score stamps the live EPSS row date fail-closed."""
    import modules.intel.research as _research

    def fake_get(url, params=None, **kwargs):
        assert params.get("cve") == "CVE-2024-3094"
        return {"data": [{"epss": "0.909", "percentile": "0.99805", "date": "2026-10-28"}]}

    monkeypatch.setattr(_research, "_get_json", fake_get)
    rec = _research.epss_score("CVE-2024-3094")
    assert rec is not None and rec.source == "epss"
    assert rec.extra.get("epss_date") == "2026-10-28"
    assert rec.extra.get("percentile") == "0.99805"


def test_w5v2_1_research_stamps_live_kev_date(monkeypatch):
    """W5-1 RED: kev_lookup stamps the live KEV dateAdded fail-closed."""
    import modules.intel.research as _research

    _research._kev_cache_clear()
    catalog = {
        "vulnerabilities": [
            {
                "cveID": "CVE-2024-3094",
                "vulnerabilityName": "XZ Utils Backdoor",
                "shortDescription": "XZ backdoor.",
                "dateAdded": "2024-05-01",
                "dueDate": "2024-05-22",
                "knownRansomwareCampaignUse": "Unknown",
            }
        ]
    }
    monkeypatch.setattr(_research, "_get_json", lambda *a, **k: catalog)
    try:
        rec = _research.kev_lookup("CVE-2024-3094")
        assert rec is not None and rec.source == "kev"
        assert rec.extra.get("kev_date") == "2024-05-01"
    finally:
        _research._kev_cache_clear()


async def test_w5v2_1_fast_lane_stale_never_blocks_scan(monkeypatch):
    """W5-1 RED: stale intel through the real fast-lane path still completes."""
    import datetime as _dt

    import modules.workflows.cve_workflow as _cw
    from modules.intel.research import ResearchRecord
    from modules.workflows.cve_workflow import execute_cve_scan

    stale = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=2)).date().isoformat()
    record = _w5v2_1_osv_record()
    monkeypatch.setattr(
        _cw, "query_osv_batch", lambda deps: {"results": [{"vulns": [{"id": "GHSA-xxxx"}]}]}
    )
    monkeypatch.setattr(_cw, "fetch_osv_vuln", lambda vid: dict(record))
    monkeypatch.setattr(
        _cw,
        "kev_lookup",
        lambda cve: ResearchRecord(
            source="kev",
            cve_id=cve,
            title="t",
            summary="s",
            extra={"kev_listed": True, "kev_date": stale},
        ),
    )
    monkeypatch.setattr(
        _cw,
        "epss_score",
        lambda cve: ResearchRecord(
            source="epss",
            cve_id=cve,
            title="t",
            summary="s",
            extra={"epss": "0.9", "percentile": "0.95", "epss_date": stale},
        ),
    )

    async def emit(team, message):
        return None

    files = {
        "requirements.txt": "widget==1.0.0\n",
        "app.py": "import pickle\ndata = pickle.loads(blob)\n",
    }
    report = await execute_cve_scan(files, emit, fast_lane=True)
    assert report.success
    assert len(report.vulnerabilities) == 1
    ev = report.vulnerabilities[0].get("queue_evidence", "")
    assert "kev:stale:" in ev and "epss:stale:" in ev
