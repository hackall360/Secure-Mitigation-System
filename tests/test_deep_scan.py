# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Deep scan tests: static signals, manifests, OSV summarization, offline CVE workflow."""

from deep_scan import (
    extract_dependencies,
    run_static_scan,
    summarize_osv_vuln,
)


def test_static_scan_flags_dangerous_sinks_with_cwe():
    files = {
        "app.py": "import pickle\ndata = pickle.loads(blob)\n",
        "web.js": "el.innerHTML = user;\n",
        "run.php": "<?php $o = shell_exec($h); ?>\n",
    }
    findings = run_static_scan(files)
    by_rule = {f.rule_id for f in findings}
    assert "py-pickle" in by_rule
    assert "js-innerhtml" in by_rule
    assert "php-shell" in by_rule
    assert all(f.cwe.startswith("CWE-") for f in findings)
    assert all(f.snippet for f in findings)


def test_extract_dependencies_parses_requirements_and_package_json():
    files = {
        "requirements.txt": "jinja2==3.1.4\nrequests>=2.31.0\n# comment\n",
        "package.json": '{"dependencies": {"lodash": "^4.17.21"}, "devDependencies": {}}',
    }
    deps = extract_dependencies(files)
    assert {"ecosystem": "PyPI", "name": "jinja2", "version": "3.1.4"} in deps
    assert {"ecosystem": "npm", "name": "lodash", "version": "4.17.21"} in deps


def test_summarize_osv_vuln_extracts_cve_cvss_and_fixes():
    record = {
        "id": "GHSA-xxxx",
        "summary": "Test vuln",
        "details": "d",
        "published": "2024-01-01T00:00:00Z",
        "modified": "2024-01-02T00:00:00Z",
        "aliases": ["CVE-2024-1234", "GHSA-xxxx"],
        "severity": [{"type": "CVSS_V3", "score": "9.8"}],
        "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.0"}]}]}],
        "references": [{"type": "ADVISORY", "url": "https://example.com"}],
    }
    summary = summarize_osv_vuln(record)
    assert summary["cves"] == ["CVE-2024-1234"]
    assert summary["severity"] == [{"type": "CVSS_V3", "score": "9.8"}]
    assert summary["fixed_versions"] == ["2.0"]


async def test_offline_cve_scan_needs_no_network_or_key(tmp_path):
    from cve_workflow import execute_cve_scan

    (tmp_path / "app.py").write_text("import pickle\npickle.loads(x)\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("jinja2==3.1.4\n", encoding="utf-8")
    from projects import ProjectSpec

    spec = ProjectSpec.model_validate(
        {
            "path": str(tmp_path),
            "command": ["python3", "app.py"],
            "test_command": ["python3", "-m", "unittest"],
            "contract": "test",
        }
    )

    async def emit(team, message):
        return None

    report = await execute_cve_scan(spec, emit, include_osv=False, include_deep_assessment=False)
    assert report.success
    assert any(f["rule_id"] == "py-pickle" for f in report.static_findings)
    assert {"ecosystem": "PyPI", "name": "jinja2", "version": "3.1.4"} in report.dependencies
    assert report.vulnerabilities == []
    assert report.deep_assessment is None


def test_nvd_summarizer_extracts_cvss_cwe_description():
    from intel_search import summarize_nvd_record, summarize_nvd_search

    item = {
        "cve": {
            "id": "CVE-2024-1234",
            "descriptions": [{"lang": "en", "value": "Test vuln in widget"}],
            "metrics": {
                "cvssMetricV31": [
                    {
                        "cvssData": {
                            "version": "3.1",
                            "baseScore": 9.8,
                            "vectorString": "AV:N",
                            "baseSeverity": "CRITICAL",
                        }
                    }
                ]
            },
            "weaknesses": [{"description": [{"value": "CWE-89"}]}],
            "published": "2024-01-01T00:00Z",
            "lastModified": "2024-01-02T00:00Z",
            "references": [{"url": "https://example.com", "source": "mitre"}],
        }
    }
    s = summarize_nvd_record(item)
    assert s["cve_id"] == "CVE-2024-1234"
    assert "widget" in s["description"]
    assert s["cvss"][0]["baseScore"] == "9.8"
    assert s["cwe"] == ["CWE-89"]
    assert summarize_nvd_search({"vulnerabilities": [item]})[0]["cve_id"] == "CVE-2024-1234"


def test_demo_materialization_validates_and_builds_spec(tmp_path):
    from demo_gen import DemoProjectFiles, materialize_demo_project

    files = DemoProjectFiles(
        app_py="from http.server import BaseHTTPRequestHandler, HTTPServer\nprint('ok')\n",
        test_contract_py="print('contract ok')\n",
        contract="Demo contract.",
        flaw_notes=["novel combo"],
        cve_inspiration=["CVE-2024-1234"],
    )
    spec = materialize_demo_project(files, dest_dir=str(tmp_path / "demo"))
    assert (tmp_path / "demo" / "app.py").exists()
    assert spec.test_command == ["python3", "test_contract.py"]
    bad = files.model_copy(update={"app_py": "x = 'sk_live_" + "a" * 24 + "'\n"})
    try:
        materialize_demo_project(bad, dest_dir=str(tmp_path / "bad"))
        raise AssertionError("should have rejected secrets")
    except ValueError:
        pass


def test_user_reports_never_contain_exploit_scripts():
    from project_agents import ContextCoverage, RedAnalysisArtifacts, RedReport
    from project_workflow import (
        CycleEvidence,
        ExecutionEvidence,
        ProjectCycleReport,
        ProjectWorkflowResult,
        SnapshotVerification,
        redact_report_for_user,
    )

    red = RedAnalysisArtifacts(
        batch_evidence=[],
        evidence_digests=[],
        report=RedReport(
            outcome="finding",
            vulnerability="v",
            affected_paths=["a.py"],
            analysis_summary="s",
            verification_script_python="EXPLOIT()",
            limitations=[],
        ),
        coverage=ContextCoverage(
            total_paths=1,
            total_bytes=1,
            covered_paths=["a.py"],
            covered_bytes=1,
            batches=1,
            complete=True,
        ),
    )
    ev = CycleEvidence(
        red=red,
        pre_verification=SnapshotVerification(
            probe=ExecutionEvidence(exit_code=0, output="x" * 600),
            regression=ExecutionEvidence(exit_code=0, output="ok"),
            fresh_target=True,
        ),
    )
    result = ProjectWorkflowResult(
        project="p",
        cycles_requested=1,
        cycle_reports=[ProjectCycleReport(cycle=1, status="retained", message="m", evidence=ev)],
    )
    safe = redact_report_for_user(result)
    dumped = __import__("json").dumps(safe)
    assert "EXPLOIT()" not in dumped
    assert safe["cycle_reports"][0]["evidence"]["red"]["report"][
        "verification_script_python"
    ].startswith("[exploit")
