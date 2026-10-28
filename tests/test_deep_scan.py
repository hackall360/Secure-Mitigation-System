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
