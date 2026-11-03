# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (parity W4 CLI remainder): CVE bounding flags + agent-count header.

LAW 9 RED-FIRST: these fail pre-fix, pass post-fix. Mock CVE workflow +
mock Muse transport (never live); real parser + real dispatch only.

(a) --cve-limit N / --cve-reach-only appear in --help.
(b) A canned 5-vuln CVE result honors --cve-limit 2 (exactly 2 [CVE] lines).
(c) --cve-reach-only prints only [TOP] topping lines, no [CVE] lines.
(d) Fixture scan header names effective agent counts
    ("agents: red=N blue=M (source: ...)").
"""

import json
from types import SimpleNamespace

import main
from modules.core.config import PurpleBoxConfig
from modules.core.pricing import ScanUsage
from modules.workflows.cve_workflow import CveScanReport


def _vuln(i, reach=True):
    v = {
        "id": f"CVE-2021-{1000 + i}",
        "cves": [f"CVE-2021-{1000 + i}"],
        "summary": f"canned vuln {i} summary",
    }
    if reach:
        v["reach_score"] = 9.0 - i * 0.5
        v["fixed_versions"] = ["9.9"]
    return v


def _canned_report(n=5):
    return CveScanReport(
        target="proj",
        status="completed",
        message="Deep scan completed.",
        static_findings=[],
        dependencies=[],
        vulnerabilities=[_vuln(i) for i in range(n)],
    )


def _project_argv(tmp_path, *extra):
    return [
        "main.py",
        "--project",
        str(tmp_path),
        "--command",
        '["python3", "app.py"]',
        "--test-command",
        '["python3", "-m", "unittest"]',
        "--contract",
        "Preserve behavior",
        "--allow-remote-inference",
        "--cve-scan",
        *extra,
    ]


def test_help_names_cve_limit_and_reach_only():
    """(a) FAIL pre-fix: --help must document the new CVE bounding flags."""
    help_text = main.build_parser().format_help()
    assert "--cve-limit" in help_text
    assert "--cve-reach-only" in help_text


def test_cve_limit_caps_printed_vulns(monkeypatch, tmp_path, capsys):
    """(b) FAIL pre-fix: 5-vuln canned result with --cve-limit 2 prints 2 [CVE] lines."""
    seen = {}

    async def fake_cve(project, emit, **kwargs):
        seen.update(kwargs)
        return _canned_report(5)

    monkeypatch.setattr(main, "execute_cve_scan", fake_cve)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr("sys.argv", _project_argv(tmp_path, "--cve-limit", "2"))
    assert main.main() == 0
    out = capsys.readouterr().out
    cve_lines = [line for line in out.splitlines() if line.startswith("[CVE")]
    assert len(cve_lines) == 2, f"expected 2 [CVE] lines, got {len(cve_lines)}:\n{out}"


def test_cve_reach_only_prints_only_topping(monkeypatch, tmp_path, capsys):
    """(c) FAIL pre-fix: --cve-reach-only prints [TOP] lines, no [CVE] lines."""
    seen = {}

    async def fake_cve(project, emit, **kwargs):
        seen.update(kwargs)
        return _canned_report(3)

    monkeypatch.setattr(main, "execute_cve_scan", fake_cve)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr("sys.argv", _project_argv(tmp_path, "--cve-reach-only"))
    assert main.main() == 0
    out = capsys.readouterr().out
    cve_lines = [line for line in out.splitlines() if line.startswith("[CVE")]
    top_lines = [line for line in out.splitlines() if line.startswith("[TOP")]
    assert not cve_lines, f"reach-only must print no [CVE] lines:\n{out}"
    assert len(top_lines) == 3, f"expected 3 [TOP] lines, got {len(top_lines)}:\n{out}"


def _fixture_result():
    payload = {
        "target": "node_query_sink",
        "status": "verified",
        "message": "Probe blocked",
        "diff": "",
        "cleanup_ok": True,
        "pre_exit_code": 0,
        "post_exit_code": 1,
        "baseline_passed": True,
        "regression_passed": True,
        "cycles": [],
        "total_tokens": 0,
        "cost_usd": 0.0,
    }
    return SimpleNamespace(
        **payload, usage=ScanUsage(), success=True, model_dump=lambda: dict(payload)
    )


def test_fixture_header_names_agent_counts(monkeypatch, capsys):
    """(d) FAIL pre-fix: fixture header must name effective agent counts."""

    async def fake_workflow(target, emit, **kwargs):
        return _fixture_result()

    monkeypatch.setattr(main, "execute_purple_workflow", fake_workflow)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--scan", "node_query_sink", "--red-agents", "7", "--blue-agents", "6"],
    )
    assert main.main() == 0
    out = capsys.readouterr().out
    assert "agents:" in out, f"header lacks agent counts:\n{out}"
    assert "red=7" in out and "blue=6" in out, f"header lacks effective counts:\n{out}"
    assert "source: flag" in out, f"header lacks count source:\n{out}"


def test_cve_scan_json_mode_prints_redacted_json_to_stdout(monkeypatch, tmp_path, capsys):
    """Surface F2 (real bug): CVE --format json printed nothing to stdout."""
    from modules.core.config import PurpleBoxConfig

    async def fake_cve(project, emit, **kwargs):
        return _canned_report(2)

    monkeypatch.setattr(main, "execute_cve_scan", fake_cve)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr("sys.argv", _project_argv(tmp_path, "--cve-limit", "5", "--format", "json"))
    assert main.main() == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "completed"
    assert len(payload["vulnerabilities"]) == 2
