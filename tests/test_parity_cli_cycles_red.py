# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED-FIRST (parity W3): CLI --show-cycles per-cycle evidence surface.

Pre-change these tests FAIL (--show-cycles unknown to argparse); post-change green.
LAW 4: no test may print or assert on probe scripts, payloads, or keys.
"""

from types import SimpleNamespace

import main
from modules.core.pricing import ScanUsage


def _cycle(cycle: int) -> dict:
    return {
        "cycle": cycle,
        "pass_number": 1,
        "status": "retained",
        "message": "cycle retained",
        "receipt": {
            "fixture": "node_query_sink",
            "cycle": cycle,
            "pre_probe_exit": 0,
            "post_probe_exit": 1,
            "property_passed": True,
            "patch_sha256": "b" * 64,
        },
        "evidence": {
            "patched_verification": {
                "probe": {"exit_code": 1},
                "regression": {"exit_code": 0},
                "mutations": {"exit_code": 0},
                "properties": {"exit_code": 0},
                "repeat_regression": {"exit_code": 0},
            },
        },
    }


def _canned_2cycle_result():
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
        "cycle_reports": [_cycle(1), _cycle(2)],
        "total_tokens": 3,
        "cost_usd": 0.0001,
    }
    return SimpleNamespace(
        **payload,
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: dict(payload),
    )


def _run_scan(monkeypatch, capsys, *extra):
    async def workflow(target, emit, **kwargs):
        return _canned_2cycle_result()

    from modules.core.config import PurpleBoxConfig

    monkeypatch.setattr(main, "execute_purple_workflow", workflow)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr("sys.argv", ["main.py", "--scan", "node_query_sink", *extra])
    return main.main()


def test_show_cycles_in_help():
    """(a) --show-cycles appears in --help."""
    assert "--show-cycles" in main.build_parser().format_help()


def test_fixture_scan_with_flag_prints_cycle_rows(monkeypatch, capsys):
    """(b) fixture scan with flag prints one row per cycle."""
    assert _run_scan(monkeypatch, capsys, "--show-cycles") == 0
    out = capsys.readouterr().out
    assert "Per-cycle evidence" in out
    assert "retained" in out
    assert "Cycle" in out


def test_without_flag_no_cycles_section(monkeypatch, capsys):
    """(c) without flag: no cycles section, no behavior change."""
    assert _run_scan(monkeypatch, capsys) == 0
    out = capsys.readouterr().out
    assert "Per-cycle evidence" not in out


def test_json_mode_with_flag_carries_cycles_key(monkeypatch, capsys):
    """json mode with flag: report gains a 2-row 'cycles' key."""
    import json

    assert _run_scan(monkeypatch, capsys, "--show-cycles", "--format", "json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["cycles"]) == 2
    assert payload["cycles"][0]["pre_exit"] == 0
    assert payload["cycles"][1]["post_exit"] == 1


def test_json_mode_without_flag_no_cycles_key(monkeypatch, capsys):
    """json mode without flag: no enriched cycles (raw redact value untouched)."""
    import json

    assert _run_scan(monkeypatch, capsys, "--format", "json") == 0
    # redact emits the raw model "cycles" field ([] here); --show-cycles
    # overwrites it with summarize_cycle_evidence rows.
    assert json.loads(capsys.readouterr().out)["cycles"] == []
