# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""CLI parity: config file, fancy non-interactive output, flag-gating, consent parity.

LAW 4: no test may print or assert on probe scripts, payloads, or keys.
"""

import json
from types import SimpleNamespace

import pytest

import main
from config import PurpleBoxConfig
from pricing import ScanUsage


def _result(**over):
    payload = {
        "target": "node_query_sink",
        "status": "verified",
        "message": "Probe blocked",
        "diff": "--- a/app.js\n+++ b/app.js\n@@ -1 +1 @@\n-old\n+new\n",
        "cleanup_ok": True,
        "pre_exit_code": 0,
        "post_exit_code": 1,
        "baseline_passed": True,
        "regression_passed": True,
        "cycles": [],
        "total_tokens": 11,
        "cost_usd": 0.0001,
    }
    payload.update(over)
    return SimpleNamespace(
        **payload,
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: dict(payload),
    )


def test_config_file_toml_json_precedence_and_unknown_key(tmp_path, monkeypatch):
    from sms_cli import LoadError, load_config_file, merge_config

    toml_path = tmp_path / "sms.toml"
    toml_path.write_text("[sms]\nprofile = 'economy'\nscan_profile = 'light'\nresearch = true\n")
    assert load_config_file(toml_path) == {
        "profile": "economy",
        "scan_profile": "light",
        "research": True,
    }
    json_path = tmp_path / "sms.json"
    json_path.write_text(json.dumps({"sms": {"profile": "quality", "format": "json"}}))
    assert load_config_file(json_path) == {"profile": "quality", "format": "json"}
    bad = tmp_path / "bad.toml"
    bad.write_text("[sms]\nbogus_key = 1\n")
    with pytest.raises(LoadError):
        load_config_file(bad)
    monkeypatch.setenv("PURPLEBOX_RESEARCH", "on")
    merged = merge_config({}, {"research": False}, {"research": True})
    assert merged["research"] is True
    monkeypatch.delenv("PURPLEBOX_RESEARCH")


def test_config_unknown_cli_key_rejected(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--bogus-flag-xyz"])
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2


def test_ai_demo_accepts_build_brief_and_vulns(monkeypatch, tmp_path):
    seen = {}

    async def fake_demo(output_dir, profile, **kwargs):
        seen.update(kwargs)
        seen["output_dir"] = output_dir
        seen["profile"] = profile
        return 0

    monkeypatch.setattr(main, "ai_demo_runner", fake_demo)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--ai-demo",
            "--build-brief",
            "a tiny notes app",
            "--vulns",
            "CVE-2021-44228, SQL injection",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert main.main() == 0
    assert seen["build_brief"] == "a tiny notes app"
    assert seen["vulns"] == "CVE-2021-44228, SQL injection"


def test_research_with_project_ok_and_with_ai_demo_ok(monkeypatch, tmp_path):
    seen = {}

    async def fake_cli(target, output_dir, profile, research=False, scanners="", **kwargs):
        seen["research"] = research
        seen["scanners"] = scanners
        seen.update(kwargs)
        return 0

    async def fake_demo(output_dir, profile, **kwargs):
        seen["demo_research"] = (kwargs.get("research"), kwargs.get("research_scanners"))
        return 0

    monkeypatch.setattr(main, "cli_runner", fake_cli)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    argv = [
        "main.py",
        "--project",
        str(tmp_path),
        "--command",
        '["python3", "app.py"]',
        "--test-command",
        '["python3", "-m", "unittest"]',
        "--contract",
        "Preserve API",
        "--allow-remote-inference",
        "--research",
        "--research-scanners",
        "trivy,grype",
    ]
    monkeypatch.setattr("sys.argv", argv)
    assert main.main() == 0
    assert seen["research"] is True
    assert seen["scanners"] == "trivy,grype"

    monkeypatch.setattr(main, "ai_demo_runner", fake_demo)
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--ai-demo", "--research", "--research-scanners", "osv-scanner"],
    )
    assert main.main() == 0
    assert seen["demo_research"] == (True, "osv-scanner")


def test_scanner_five_set_accepted(monkeypatch):
    seen = {}

    async def fake_cli(target, output_dir, profile, research=False, scanners="", **kwargs):
        seen["scanners"] = scanners
        return 0

    monkeypatch.setattr(main, "cli_runner", fake_cli)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--scan",
            "node_query_sink",
            "--research",
            "--research-scanners",
            "trivy,grype,osv-scanner,dependency-check,dependency-track",
        ],
    )
    assert main.main() == 0
    assert seen["scanners"] == "trivy,grype,osv-scanner,dependency-check,dependency-track"


def test_ai_demo_flag_gating_no_longer_requires_project(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--ai-demo",
            "--scan-profile",
            "light",
            "--red-agents",
            "6",
            "--intel-theme",
            "xss",
        ],
    )

    async def fake_demo(output_dir, profile, **kwargs):
        assert kwargs["scan_profile"] == "light"
        assert kwargs["red_agents"] == 6
        return 0

    monkeypatch.setattr(main, "ai_demo_runner", fake_demo)
    assert main.main() == 0


def test_intensity_warnings(monkeypatch, capsys):
    argv = [
        "main.py",
        "--scan",
        "node_query_sink",
        "--red-agents",
        "12",
        "--blue-agents",
        "12",
        "--context-budget",
        "131072",
    ]
    monkeypatch.setattr("sys.argv", argv)

    async def fake_cli(target, output_dir, profile, research=False, scanners="", **kwargs):
        return 0

    monkeypatch.setattr(main, "cli_runner", fake_cli)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    assert main.main() == 0
    err = capsys.readouterr().err
    assert "warning" in err.lower()


def test_health_table_and_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["main.py", "--health"])
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    assert main.main() == 0
    out = capsys.readouterr().out
    assert "Secure Mitigation System" in out or "inference" in out.lower()

    monkeypatch.setattr("sys.argv", ["main.py", "--health", "--format", "json"])
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    assert main.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload.get("api_key_configured") in (True, False)
    assert payload.get("version") == main.APP_VERSION

    monkeypatch.setattr("sys.argv", ["main.py", "--version"])
    with pytest.raises(SystemExit) as exited:
        main.main()
    assert exited.value.code == 0
    out = capsys.readouterr().out
    assert main.APP_VERSION in out


def test_format_json_redacted_and_no_secrets(monkeypatch, capsys):
    async def workflow(target, emit, **kwargs):
        return _result()

    monkeypatch.setattr(main, "execute_purple_workflow", workflow)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr("sys.argv", ["main.py", "--scan", "node_query_sink", "--format", "json"])
    assert main.main() == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "verified"
    lowered = out.lower()
    assert "verification_script" not in lowered
    assert "sk-ant-" not in lowered


def test_tables_render_and_no_color_paths():
    from sms_cli import fact_table, format_facts, usage_table

    usage = SimpleNamespace(
        calls=[
            SimpleNamespace(
                role="red",
                model="m",
                prompt_tokens=1,
                cached_tokens=0,
                completion_tokens=2,
                reasoning_tokens=0,
                seconds=0.5,
                cost_usd=0.0001,
            )
        ]
    )
    result = SimpleNamespace(
        target="t",
        status="verified",
        message="ok",
        diff="",
        pre_exit_code=0,
        post_exit_code=1,
        baseline_passed=True,
        regression_passed=True,
        cleanup_ok=True,
        usage=usage,
        total_tokens=3,
        cost_usd=0.0001,
    )
    table = fact_table(result, use_color=False)
    assert "Baseline" in table and "Pre-probe" in table
    assert "\x1b[" not in table
    assert "Role" in usage_table(result, use_color=False)
    colored = fact_table(result, use_color=True)
    assert "\x1b[" in colored
    facts = format_facts(result, use_color=False)
    assert facts["status"] == "verified"


def test_hosted_consent_parity_project_and_cve(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig(inference_mode="hosted"))

    async def boom(*args, **kwargs):
        raise AssertionError("workflow must not start without consent")

    monkeypatch.setattr(main, "execute_project_workflow", boom)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--project",
            str(tmp_path),
            "--command",
            '["python3", "app.py"]',
            "--test-command",
            '["python3", "-m", "unittest"]',
            "--contract",
            "Preserve API",
            "--format",
            "json",
        ],
    )
    code = main.main()
    assert code != 0


def test_tui_command_reaches_tui_main(monkeypatch, capsys):
    """--tui dispatches to the TUI entry (curses or plain degrade)."""
    import main as _main

    monkeypatch.setattr("sys.argv", ["main.py", "--tui"])
    seen = {}
    monkeypatch.setattr("tui.main", lambda argv=None: seen.setdefault("argv", argv) or 0)
    assert _main.main() == 0
    assert seen["argv"] == []
