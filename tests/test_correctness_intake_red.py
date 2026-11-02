# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Y6 (correctness deep-validation round 5): intake/config/redaction/MCP pins.

Live-proven gaps from the round-5 survey:
1. RepoIntakeSpec adversarial matrix (http/short-hash/shell/backtick/
   empty-host/nonhex rejected; https+40hex accepted).
2. sms_cli merge precedence (flags > file > env) + unknown-key LoadError.
3. Sweep + binary redaction with real trace keys (:before withheld,
   regression/baseline kept).
4. Project redaction: verification scripts + probe outputs redacted.
5. MCP snippet bounds: oversize + bad language -> -32602 (never a scan).
6. CLI error parity: unknown --scan -> exit 2 (argparse choices).
"""

import pytest
from fastapi.testclient import TestClient

import main
from modules.core.config import PurpleBoxConfig


def test_intake_spec_adversarial_matrix():
    from modules.services.repo_intake import RepoIntakeSpec

    good = RepoIntakeSpec(url="https://github.com/example/demo", commit_hash="a" * 40)
    assert good.commit_hash == "a" * 40
    for kw in [
        {"url": "http://github.com/e/d", "commit_hash": "a" * 40},
        {"url": "https://github.com/example/demo", "commit_hash": "abc"},
        {"url": "https://github.com/example/demo; rm -rf /", "commit_hash": "a" * 40},
        {"url": "https://github.com/example/demo`id`", "commit_hash": "a" * 40},
        {"url": "https://", "commit_hash": "a" * 40},
        {"url": "https://github.com/example/demo", "commit_hash": "z" * 40},
    ]:
        with pytest.raises(ValueError):
            RepoIntakeSpec(**kw)


def test_sms_cli_merge_precedence_and_unknown_key():
    import pathlib
    import tempfile

    import sms_cli as S

    env = {"research": True, "research_scanners": "trivy", "format": "table"}
    assert S.merge_config(env, {}, {"format": "json"})["format"] == "json"
    assert S.merge_config(env, {"format": "json"}, {})["format"] == "json"
    assert S.merge_config(env, {}, {})["research"] is True
    bad = pathlib.Path(tempfile.mkdtemp()) / "sms.toml"
    bad.write_text("[sms]\nevil_key = 1\n", encoding="utf-8")
    with pytest.raises(S.LoadError):
        S.load_config_file(bad)


def test_sweep_binary_redaction_real_keys():
    from modules.workflows.binary_sweep import redact_binary_sweep_result_for_user
    from modules.workflows.sweep import SweepScanResult, redact_sweep_result_for_user

    sr = SweepScanResult(target="node_query_sink", status="verified")
    sr.traces = {
        "standard:before": "SECRET-SWEEP",
        "standard:regression": "REG-OK",
        "baseline": "B",
    }
    out = redact_sweep_result_for_user(sr)
    assert "SECRET-SWEEP" not in str(out)
    assert out["traces"]["standard:regression"] == "REG-OK"
    assert out["traces"]["baseline"] == "B"

    sb = SweepScanResult(target="binary_argv_echo", status="verified")
    sb.traces = {"p1:before": "SECRET-BIN", "p1:regression": "R"}
    out2 = redact_binary_sweep_result_for_user(sb)
    assert "SECRET-BIN" not in str(out2)
    assert out2["traces"]["p1:regression"] == "R"


def test_project_redaction_withholds_scripts_and_outputs():
    from modules.shared.sms_redact import redact_cycle_evidence, redact_project_result

    ev = {
        "red": {"report": {"verification_script_python": "SECRET-SCRIPT"}},
        "pre_verification": {"probe": {"output": "x" * 2000, "exit_code": 0}},
    }
    red = redact_cycle_evidence(ev)
    assert red["red"]["report"]["verification_script_python"] != "SECRET-SCRIPT"
    assert len(str(red["pre_verification"]["probe"]["output"])) <= 500

    class _Fake:
        def model_dump(self):
            return {
                "cycle_reports": [{"evidence": ev}],
                "cycles": [{"evidence": ev}],
                "verified_history": [],
            }

    out = redact_project_result(_Fake())
    assert "SECRET-SCRIPT" not in str(out)


def test_mcp_snippet_bounds_never_scan():
    app = main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        big = "x" * 70000
        r = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "submit_code_snippet",
                    "arguments": {"language": "javascript", "source_code": big},
                },
            },
        )
        assert r.json()["error"]["code"] == -32602
        r2 = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "submit_code_snippet",
                    "arguments": {"language": "cobol", "source_code": "x"},
                },
            },
        )
        assert r2.json()["error"]["code"] == -32602


def test_cli_unknown_scan_exits_2():
    import subprocess
    import sys

    p = subprocess.run(
        [sys.executable, "main.py", "--scan", "nope_xyz"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert p.returncode == 2
    assert "invalid choice" in (p.stderr + p.stdout).lower()
