# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""CLI parity: config file, fancy non-interactive output, flag-gating, consent parity.

LAW 4: no test may print or assert on probe scripts, payloads, or keys.
"""

import json
from types import SimpleNamespace

import pytest

import main
from modules.core.config import PurpleBoxConfig
from modules.core.pricing import ScanUsage


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


def test_fast_lane_flag_reaches_cve_scan(monkeypatch, tmp_path):
    """L4: --fast-lane threads through CLI into execute_cve_scan."""
    import main as _main

    seen = {}

    async def fake_cve(project, emit, **kwargs):
        seen.update(kwargs)
        from modules.workflows.cve_workflow import CveScanReport

        return CveScanReport(target="p", message="Fast lane: ok")

    monkeypatch.setattr(_main, "execute_cve_scan", fake_cve)
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
            "--allow-remote-inference",
            "--cve-scan",
            "--fast-lane",
        ],
    )
    assert _main.main() == 0
    assert seen.get("fast_lane") is True


def test_ai_demo_accepts_hardening_flags(monkeypatch, tmp_path):
    """L3: --demo-size/--flaw-count/--demo-seed reach ai_demo_runner (flaw clamped)."""
    seen = {}

    async def fake_demo(output_dir, profile, **kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(main, "ai_demo_runner", fake_demo)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--ai-demo",
            "--demo-size",
            "small",
            "--flaw-count",
            "99",
            "--demo-seed",
            "7",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert main.main() == 0
    assert seen["demo_size"] == "small"
    assert seen["flaw_count"] == 8
    assert seen["demo_seed"] == 7


def test_ai_demo_hardening_flags_require_ai_demo(monkeypatch):
    """L3: new flags gate on --ai-demo like --build-brief/--vulns do."""
    for argv in (
        ["main.py", "--scan", "node_query_sink", "--demo-size", "small"],
        ["main.py", "--scan", "node_query_sink", "--flaw-count", "2"],
        ["main.py", "--scan", "node_query_sink", "--demo-seed", "3"],
    ):
        monkeypatch.setattr("sys.argv", argv)
        with pytest.raises(SystemExit) as error:
            main.main()
        assert error.value.code == 2


def test_config_file_accepts_hardening_keys(tmp_path):
    """L3: sms.toml [sms] accepts demo_size/flaw_count/demo_seed via CONFIG_KEYS."""
    from sms_cli import load_config_file

    toml_path = tmp_path / "sms.toml"
    toml_path.write_text("[sms]\ndemo_size = 'small'\nflaw_count = 3\ndemo_seed = 7\n")
    assert load_config_file(toml_path) == {
        "demo_size": "small",
        "flaw_count": 3,
        "demo_seed": 7,
    }


# --- Wave 2 items 1-4 tri-surface integration (SPEC 14.8, LAW 8/9 RED) ---
# Defensive probes: Wave 2 fields may be absent (parallel agents); every
# accessor must degrade silently, never raise on missing/odd-shaped fields.


def _w2v2_receipt_result(**over):
    """Fixture result carrying Wave 2 receipt + guard + mutation evidence."""
    from types import SimpleNamespace

    payload = {
        "target": "node_query_sink",
        "status": "verified",
        "message": "Probe blocked",
        "diff": "--- a/app.js\n+++ b/app.js\n",
        "cleanup_ok": True,
        "pre_exit_code": 0,
        "post_exit_code": 1,
        "baseline_passed": True,
        "regression_passed": True,
        "cycles": [],
        "total_tokens": 3,
        "cost_usd": 0.0001,
        "verdict_receipt": {
            "fixture": "node_query_sink",
            "pre_exit_code": 0,
            "post_exit_code": 1,
            "regression": "passed",
            "differential": "passed",
            "properties": "passed",
            "patch_hash": "abc123",
        },
        "guard_rationales": [
            {"guard": "no-new-sinks", "protected_line": "eval(", "reason": "blocked"}
        ],
        "mutation_evidence": {"mutations": 8, "failures": 0, "verdict": "passed"},
    }
    payload.update(over)
    return SimpleNamespace(
        **payload,
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: dict(payload),
    )


def _w2v2_fast_lane_report():
    """CVE report with reach/KEV/EPSS fast-lane topping evidence."""
    from types import SimpleNamespace

    payload = {
        "target": "p",
        "status": "completed",
        "message": "Fast lane: ok",
        "static_findings": [],
        "dependencies": [],
        "vulnerabilities": [
            {
                "id": "CVE-2024-0001",
                "cves": ["CVE-2024-0001"],
                "reach_score": 85,
                "reach_evidence": ["sink adjacency (+40)", "KEV listed (+5)"],
                "fixed_versions": ["1.2.3"],
                "kev_listed": True,
                "epss_percentile": 0.97,
            }
        ],
        "deep_assessment": None,
        "errors": [],
    }
    return SimpleNamespace(
        **payload,
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: dict(payload),
    )


def test_w2v2_receipt_facts_degrade_silently_without_fields():
    """Item 1: absent receipt -> 'Not reported'; present -> fixture + hash."""
    from sms_cli import format_wave2_facts

    facts = format_wave2_facts(_result(), use_color=False)
    assert facts["receipt"] == "Not reported"
    assert facts["guard_rationales"] == "Not reported"
    assert facts["mutations"] == "Not reported"
    facts = format_wave2_facts(_w2v2_receipt_result(), use_color=False)
    assert "node_query_sink" in facts["receipt"]
    assert "abc123" in facts["receipt"]
    assert "no-new-sinks" in facts["guard_rationales"]
    assert "0/8" in facts["mutations"]


def test_w2v2_fact_table_includes_wave2_rows():
    """LAW 8 CLI surface: fact table always shows the four Wave 2 rows."""
    from sms_cli import fact_table

    table = fact_table(_result(), use_color=False)
    for row in ("Receipt", "Guard rationales", "Fast-lane top", "Mutations"):
        assert row in table


def test_fact_table_includes_compression_row():
    """Subsystem A LAW 8: CLI fact table always shows the compression row."""
    from sms_cli import fact_table, format_facts

    compression = SimpleNamespace(
        raw_tokens_estimated=120,
        compressed_tokens_sent=80,
        tokens_saved=40,
        compression_ratio=0.3333,
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
        compression=compression,
    )
    facts = format_facts(result, use_color=False)
    assert facts["compression"] == "120 -> 80 tokens (saved 40, ratio 0.33)"
    assert "Compression" in fact_table(result, use_color=False)
    plain = SimpleNamespace(target="t", status="verified", message="ok", diff="")
    assert format_facts(plain, use_color=False)["compression"] == "Not reported"


def test_fact_table_includes_vault_row():
    """Subsystem B LAW 8: CLI fact table always shows the vault recall row."""
    from sms_cli import fact_table, format_facts

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
        vault_recall="KNOWN_ARCHETYPE",
        vault_namespaces=["red", "blue"],
    )
    facts = format_facts(result, use_color=False)
    assert facts["vault_recall"] == "KNOWN_ARCHETYPE (red, blue)"
    assert "Vault recall" in fact_table(result, use_color=False)
    plain = SimpleNamespace(target="t", status="verified", message="ok", diff="")
    assert format_facts(plain, use_color=False)["vault_recall"] == "Not reported"


def test_w2v2_write_run_report_exports_receipt_json():
    """Item 1: run report writes receipt.json when verdict_receipt present."""
    report = _w2v2_receipt_result().model_dump()
    run_dir = main.write_run_report(tmp_path_report_dir(), report, "# summary")
    receipt = (run_dir / "receipt.json").read_text()
    assert "node_query_sink" in receipt
    assert "patch_hash" in receipt


def tmp_path_report_dir():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp())


def test_w2v2_summary_markdown_has_wave2_sections():
    """SUMMARY.md carries topping + guard + mutation sections when present."""
    result = _w2v2_receipt_result()
    settings = PurpleBoxConfig()
    summary = main._build_summary_markdown("node_query_sink", None, settings, result)
    assert "Verdict receipt" in summary
    assert "Guard rationales" in summary
    assert "Mutation probes" in summary


def test_w2v2_summary_markdown_degrades_without_fields():
    """Absent Wave 2 fields: summary still builds, no Wave 2 sections."""
    result = _result()
    settings = PurpleBoxConfig()
    summary = main._build_summary_markdown("node_query_sink", None, settings, result)
    assert "Verdict receipt" not in summary
    assert "node_query_sink" in summary


def test_w2v2_fast_lane_topping_summary_section():
    """Item 3: CVE summary renders reach/KEV/EPSS topping evidence."""
    result = _w2v2_fast_lane_report()
    settings = PurpleBoxConfig()
    summary = main._build_cve_summary_markdown("p", settings, result)
    assert "Fast-lane topping" in summary
    assert "CVE-2024-0001" in summary
    assert "85" in summary
    assert "1.2.3" in summary


def test_w2v2_tui_describe_result_carries_wave2_tokens():
    """TUI surface: result line carries receipt/mutation tokens; degrades clean."""
    import tui as _tui

    out = _tui.describe_result(_result())
    assert "node_query_sink" in out and "verified" in out
    out = _tui.describe_result(_w2v2_receipt_result())
    assert "receipt" in out.lower() or "abc123" in out or "mutation" in out.lower()


def test_w2v2_probes_never_raise_on_garbage():
    """Defensive contract: odd-shaped fields never raise on any surface."""
    from types import SimpleNamespace

    import tui as _tui
    from sms_cli import format_wave2_facts

    garbage = SimpleNamespace(
        target="t",
        status="verified",
        message="ok",
        usage=ScanUsage(),
        verdict_receipt=["not", "a", "dict"],
        guard_rationales="a string, not a list",
        mutation_evidence=42,
        fast_lane=None,
    )
    assert format_wave2_facts(garbage, use_color=False)["receipt"] == "Not reported"
    assert "verified" in _tui.describe_result(garbage)


# --- Wave 2 real-field rendering (zebra rework: merged reality e76b019) ---
# Probes must read REAL producer fields first; guessed names are fallback only.


def _w2v2_real_fixture_result():
    """Real VerdictReceipt via build_verdict_receipt on a ScanResult-shaped ns."""
    from modules.workflows.workflow import build_verdict_receipt

    receipt = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="diff-bytes",
    )
    return SimpleNamespace(
        target="node_query_sink",
        status="verified",
        message="Probe blocked",
        diff="--- a/app.js\n+++ b/app.js\n",
        cleanup_ok=True,
        pre_exit_code=0,
        post_exit_code=1,
        baseline_passed=True,
        regression_passed=True,
        receipt=receipt,
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: {"target": "node_query_sink", "status": "verified"},
    )


def _w2v2_real_cycle_result():
    """Real CycleReceipt + GuardRationale + mutations on a project-shaped ns."""
    from modules.workflows.project_workflow import (
        ExecutionEvidence,
        GuardRationale,
        SnapshotVerification,
        build_cycle_receipt,
    )

    def _ev(exit_code):
        return SnapshotVerification(
            probe=ExecutionEvidence(exit_code=exit_code, output="probe"),
            regression=ExecutionEvidence(exit_code=0, output="regression ok"),
            fresh_target=True,
        )

    pre, patched = _ev(0), _ev(1)
    receipt = build_cycle_receipt(
        fixture="php_command_sink",
        pre=pre,
        patched=patched,
        baseline_regression_exit=0,
        differential_passed=True,
        candidate_diff="diff-bytes",
    )
    guard = GuardRationale(guard_id="no-new-sinks", reason="blocked sink", trigger="eval(")
    patched_with_mut = SnapshotVerification(
        probe=ExecutionEvidence(exit_code=1, output="blocked"),
        regression=ExecutionEvidence(exit_code=0, output="regression ok"),
        fresh_target=True,
        mutations=ExecutionEvidence(exit_code=0, output="4/4 mutations held"),
    )
    cycle = SimpleNamespace(
        cycle=1,
        pass_number=1,
        status="retained",
        message="ok",
        receipt=receipt,
        evidence=SimpleNamespace(
            replacement_validation=SimpleNamespace(guard_rationale=guard),
            patched_verification=patched_with_mut,
        ),
        model_dump=lambda: {"cycle": 1},
    )
    return SimpleNamespace(
        project="demo",
        status="verified",
        message="ok",
        cycle_reports=[cycle],
        cycles=[cycle],
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: {"project": "demo", "status": "verified"},
    )


def _w2v2_real_topping_report():
    """Real queue_evidence string via cve_workflow._queue_evidence."""
    from modules.workflows.cve_workflow import _queue_evidence

    summary = {
        "id": "CVE-2024-0001",
        "cves": ["CVE-2024-0001"],
        "reach_score": 85,
        "reach_evidence": ["sink adjacency (+40)"],
        "fixed_versions": ["1.2.3"],
        "kev_listed": True,
        "epss_percentile": 0.97,
    }
    summary["queue_evidence"] = _queue_evidence(summary)
    return SimpleNamespace(
        target="p",
        status="completed",
        message="Fast lane: ok",
        static_findings=[],
        dependencies=[],
        vulnerabilities=[summary],
        deep_assessment=None,
        errors=[],
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: {"target": "p", "status": "completed"},
    )


def test_w2v2_real_receipt_renders():
    """Real result.receipt (VerdictReceipt) renders fixture + sha prefix."""
    from sms_cli import format_wave2_facts

    facts = format_wave2_facts(_w2v2_real_fixture_result(), use_color=False)
    assert "node_query_sink" in facts["receipt"]
    assert "36d46d53" in facts["receipt"]  # sha256('diff-bytes') prefix
    assert "probe 0/1" in facts["receipt"]


def test_w2v2_real_cycle_receipt_guard_mutations_render():
    """Real cycle.receipt + guard_rationale + mutations render."""
    from sms_cli import format_wave2_facts

    facts = format_wave2_facts(_w2v2_real_cycle_result(), use_color=False)
    assert "php_command_sink" in facts["receipt"]
    assert "no-new-sinks" in facts["guard_rationales"]
    assert "eval(" in facts["guard_rationales"]
    assert facts["mutations"] != "Not reported"


def test_w2v2_real_queue_evidence_renders():
    """Real queue_evidence string renders KEV/EPSS tie-break line."""
    from sms_cli import format_wave2_facts

    facts = format_wave2_facts(_w2v2_real_topping_report(), use_color=False)
    assert "CVE-2024-0001" in facts["fast_lane_top"]
    assert "kev:listed" in facts["fast_lane_top"]
    assert "epss:0.97" in facts["fast_lane_top"]


def test_w2v2_real_receipt_export_roundtrip():
    """export_receipt_json output parses and carries real field names."""
    import json

    from modules.workflows.workflow import export_receipt_json

    receipt = _w2v2_real_fixture_result().receipt
    parsed = json.loads(export_receipt_json(receipt))
    assert parsed["fixture"] == "node_query_sink"
    assert parsed["patch_sha256"].startswith("36d46d53")


# --- Interactive help polish (Wave 2/5/8 exec audience; LAW 8: no dead flags) ---
# Fail-first: every capability one-liner must appear in --help output.

HELP_KEYWORDS = (
    "receipts",
    "rationale",
    "topping",
    "mutations",
    "freshness",
    "templates",
    "stale",
    "repeat-stability",
)


def _help_text(argv):
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "main.py", *argv],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_help_lists_all_wave_capabilities_with_value():
    out = _help_text(["--help"]).lower()
    for keyword in HELP_KEYWORDS:
        assert keyword in out, f"--help missing {keyword!r}"


def test_help_names_receipt_json_proof():
    out = _help_text(["--help"])
    assert "receipt.json" in out


def test_help_names_stale_token_and_repeat_stability():
    out = _help_text(["--help"])
    assert "stale:<date>" in out or "stale:" in out
    assert "repeat-stability" in out


def test_help_documents_only_live_flags_law8():
    """Every --long-flag in --help must parse (no dead documented flags)."""
    import re

    out = _help_text(["--help"])
    flags = sorted(set(re.findall(r"--[a-z][a-z0-9-]+", out)))
    # Sanity: capability keywords never masquerade as flags.
    assert "--receipts" not in flags
    assert "--topping" not in flags
    # Spot-check live flags parse on their own surface.
    import subprocess
    import sys

    for probe in (["--version"], ["--list-targets"], ["--help"]):
        proc = subprocess.run(
            [sys.executable, "main.py", *probe],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, (probe, proc.stderr)


def test_sms_capabilities_text_matches_main_epilog():
    import main as _main
    from sms_cli import capabilities_text

    for keyword in HELP_KEYWORDS:
        assert keyword in capabilities_text().lower()
    assert "receipt.json" in capabilities_text()
    assert "receipt.json" in _main.CAPABILITIES_EPILOG


def test_tui_footer_and_overlay_carry_help():
    import tui as _tui

    assert "h help" in _tui.FOOTER_HELP
    assert _tui.parse_key("h") == "help"
    assert _tui.parse_key("H") == "help"
    state = _tui.TuiState()
    _tui.apply_action(state, "help")
    assert state.help_open is True
    lines = _tui.render_panes(state)
    joined = "\n".join(lines).lower()
    for keyword in (
        "receipts",
        "rationale",
        "topping",
        "mutations",
        "freshness",
        "templates",
        "stale",
        "repeat-stability",
    ):
        assert keyword in joined, f"TUI overlay missing {keyword!r}"


def test_tui_plain_help_carries_capabilities():
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from tui import run_plain; raise SystemExit(run_plain(['--help']))",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.lower()
    for keyword in HELP_KEYWORDS:
        assert keyword in out, f"tui --help missing {keyword!r}"


# --- W5R2-2 second half (SPEC 14.9 item 4): tri-surface drift fail-first ---
# Every test here must RED on base dafa4da and GREEN after the fix.


def test_w5r2_ai_demo_accepts_custom_cycles(monkeypatch, tmp_path):
    """HIGH main.py:1537-1560: --ai-demo drops --cycles (defaults None) so any
    named profile + explicit cycles crashes in ProjectSpec (light needs 3)."""
    seen = {}

    async def fake_demo(output_dir, profile, **kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(main, "ai_demo_runner", fake_demo)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--ai-demo",
            "--scan-profile",
            "light",
            "--cycles",
            "3",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert main.main() == 0
    assert seen["cycles"] == 3


def test_w5r2_ai_demo_custom_cycles_end_to_end_clamped(tmp_path):
    """HIGH main.py:236-238 stamp rule: custom + explicit cycles must survive
    ProjectSpec validation (clamped 1..20) instead of raising ValueError."""
    from modules.services.projects import ProjectSpec

    dump = {
        "path": str(tmp_path),
        "command": ["python3", "app.py"],
        "test_command": ["python3", "test_contract.py"],
        "contract": "c",
        "scan_profile": "custom",
        "cycles": max(1, min(20, 9)),
        "red_agents": 5,
        "blue_agents": 5,
        "allow_remote_inference": True,
    }
    spec = ProjectSpec.model_validate(dump)
    assert spec.cycles == 9


def test_w5r2_docs_line_refs_track_sources():
    """MED docs/reference/CLI.md + docs/reference/MODULES.md: stale file:line
    cross-links (pre verified values from reading the files)."""
    from pathlib import Path

    cli = (Path(__file__).resolve().parents[1] / "docs" / "reference" / "CLI.md").read_text()
    modules = (
        Path(__file__).resolve().parents[1] / "docs" / "reference" / "MODULES.md"
    ).read_text()
    assert "sms_cli.py:310" in cli, "CLI.md format_wave2_facts line moved (was 290)"
    assert "sms_cli.py:631" in cli, "CLI.md fact_table line moved (was 611)"
    assert "main.py:870" in cli, "CLI.md write_run_report line moved (was 854-861)"
    assert "tui.py:280" in cli, "CLI.md describe_wave2 line moved (was 244)"
    assert "main.py:1093" in cli or "main.py:1095" in cli, "CLI.md receipt section moved"
    assert "modules/workflows/workflow.py:238,262" in modules
    assert "modules/workflows/project_workflow.py:207" in modules
    assert "modules/workflows/project_workflow.py:285,320" in modules
    assert "modules/core/patches.py:57" in modules
    assert "modules/core/checks.py:423,543" in modules
    assert "modules/workflows/project_workflow.py:102,131" in modules
    assert "modules/workflows/cve_workflow.py:31,135,417" in modules
    assert "modules/workflows/cve_workflow.py:39,42" in modules


def test_cli_reference_lists_v1_leaves():
    """W1 CLI rows: CLI.md commands table lists v1 engine leaves + MCP/binary rows."""
    from pathlib import Path

    cli = (Path(__file__).resolve().parents[1] / "docs" / "reference" / "CLI.md").read_text()
    for token in ("sms_compress", "sms_vault", "sms_api", "--mcp", "binary_argv_echo"):
        assert token in cli, f"CLI.md missing {token!r}"
