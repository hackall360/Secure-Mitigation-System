# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED tests: TUI ingest-mode live proof + CLI --stats depth (tribunal 2d-6/7).

Pins (RED on base, GREEN after the fix):
1. ``tui.py run_plain`` exposes a ``--stats`` flag printing a CompressionStats
   summary + vault_stats() (global novel/historical + tokens_saved_estimate).
2. CLI ``--stats`` stdout contains raw/sent/saved keys.
3. The TUI ingest dispatch path runs in-process (FakeMuse/FakeSandbox-style:
   patch the workflow + intake attributes directly, never Docker) asserting
   the ingest branch renders repo URL/commit/token rows without crashing.
4. ``sms_cli.format_facts`` on a sweep result includes ``savings_pct`` +
   ``novel_vs_historical`` keys (telemetry auto-flow, tribunal 2d-7).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import tui

VALID_REPO = "https://example.com/org/demo.git"
VALID_COMMIT = "a" * 40


def _result(**fields):
    base = {"target": "t", "status": "ok", "message": "done", "success": True}
    base.update(fields)
    return SimpleNamespace(**base)


def test_tui_plain_exposes_stats_flag(capsys):
    """Pin 1: run_plain accepts --stats (parses, exits 0, no Docker)."""
    rc = tui.run_plain(["--stats"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "stats" in out.lower()


def test_cli_stats_stdout_has_raw_sent_saved_keys(capsys):
    """Pin 2: --stats stdout contains raw/sent/saved keys."""
    rc = tui.run_plain(["--stats"])
    assert rc == 0
    out = capsys.readouterr().out
    lowered = out.lower()
    assert "raw" in lowered
    assert "sent" in lowered
    assert "saved" in lowered


def test_tui_ingest_dispatch_renders_rows_live(monkeypatch):
    """Pin 3 (RETIRED by F-02 fix 2026-11-02): the old contract asserted the
    ingest branch runs the fixture workflow and renders its rows — that was
    the false-success defect itself (fixture bytes reported as the repo's
    verdict). Repo-intake staging has no clone yet, so ingest now refuses
    fail-closed. Contract moved to tests/test_ingest_cli_tui_red.py
    (refusal + never-calls-workflow pins). This stub keeps the pin count
    stable and documents the supersession."""
    pytest.skip("superseded by F-02 honest-refusal contract (test_ingest_cli_tui_red.py)")


def test_format_facts_carries_telemetry_keys():
    """Pin 4: format_facts on a sweep result includes savings_pct +
    novel_vs_historical keys (telemetry auto-flow)."""
    from sms_cli import format_facts

    result = _result(
        compression=SimpleNamespace(
            raw_tokens_estimated=200,
            compressed_tokens_sent=120,
            tokens_saved=80,
            compression_ratio=0.4,
        ),
        vault_recall="KNOWN_ARCHETYPE",
        vault_namespaces=["red"],
    )
    facts = format_facts(result, use_color=False)
    assert "savings_pct" in facts, f"missing savings_pct in {sorted(facts)}"
    assert "novel_vs_historical" in facts, f"missing novel_vs_historical in {sorted(facts)}"
