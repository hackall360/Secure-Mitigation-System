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
