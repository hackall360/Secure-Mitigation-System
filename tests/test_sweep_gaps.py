# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first sweep gap tests (Subsystem C, V1 guidance matrix Y3).

RED per LAW 9: the 3-pass engine exists (sweep.py + binary_sweep.py +
--sweep-passes); these tests pin the remaining gaps before they are filled:
per-pass compression + vault recall propagation, dashboard pass indicator
data, and CLI/TUI sweep surfacing of the new telemetry.
"""


def _sweep_result(**overrides):
    from modules.workflows.sweep import SweepScanResult

    base = {
        "target": "node_query_sink",
        "status": "verified",
        "message": "ok",
        "baseline_passed": True,
        "cleanup_ok": True,
    }
    base.update(overrides)
    return SweepScanResult(**base)


def test_sweep_result_carries_compression_and_vault():
    result = _sweep_result()
    dumped = result.model_dump()
    assert "compression" in dumped
    assert dumped["compression"]["raw_tokens_estimated"] >= 0


def test_cli_facts_render_sweep_telemetry():
    from sms_cli import format_facts

    result = _sweep_result()
    facts = format_facts(result, use_color=False)
    assert "compression" in facts
    assert "vault_recall" in facts


def test_threat_actor_prompt_demands_novelty():
    from modules.core.prompts import RED_THREAT_ACTOR_SYSTEM_PROMPT

    lowered = RED_THREAT_ACTOR_SYSTEM_PROMPT.lower()
    for marker in (
        "do not",
        "repeat",
        "novel",
        "logic abuse",
        "researcher",
    ):
        assert marker in lowered, marker


def test_deep_prompt_covers_mutation_classes():
    from modules.core.prompts import RED_DEEP_SWEEP_SYSTEM_PROMPT

    lowered = RED_DEEP_SWEEP_SYSTEM_PROMPT.lower()
    for marker in ("encoding", "coercion", "truncation"):
        assert marker in lowered, marker


def test_dashboard_pass_badge_and_telemetry_ids_exist():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text()
    js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
    assert "sweep-passes" in html
    assert "fact-compression" in html
    assert "fact-vault" in html
    assert "sweep_summary" in js
    assert "fact-vault" in js


def test_tui_sweep_mode_reports_depth():
    import tui

    state = tui.TuiState(mode="sweep", sweep_depth=3)
    assert tui._state_sweep_passes(state) == 3
    state2 = tui.TuiState(mode="sweep", sweep_depth=1)
    assert tui._state_sweep_passes(state2) == 1
