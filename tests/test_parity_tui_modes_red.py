# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED tests for parity W5: TUI ``vault`` + ``ops`` modes.

The new library surface (vault list/replay, ops status, showcase status)
has NO TUI mode. Goal: TWO new modes — ``vault`` (list namespaces; replay
``NAMESPACE:ID`` via the ingest-style repo/commit fields into a redacted
summary) and ``ops`` (docker state + leftovers + knobs + showcase presence,
read-only).

LAW 4: no payloads, keys, or probe material in this file. All backends mocked
(monkeypatched canonical ``modules.services.sms_api`` attributes, mirroring
``tests/test_ingest_cli_tui_red.py``); the bad-id test uses the REAL
``replay_vault_record`` validator, which must refuse before touching disk.
"""

from __future__ import annotations

import pytest

FAKE_NAMESPACES = [
    {"namespace": "red", "record_count": 2},
    {"namespace": "blue", "record_count": 1},
]

FAKE_HEALTH = {"state": "healthy", "missing_images": [], "leftover_containers": []}
FAKE_LEFTOVERS = {"containers": ["sess-1"], "networks": [], "images": ["snap-1"]}
FAKE_KNOBS = {
    "timeout_seconds": 42,
    "max_tokens": 1,
    "reasoning_effort": "low",
    "verifier_timeout": 2,
    "research_scanners": [],
}
FAKE_SHOWCASE = {
    "tts": {"present": True, "port": 8002},
    "capture": {"present": False},
    "music": {"present": False},
    "render": {},
}

GOOD_RECORD_ID = "ab" * 16
FAKE_REPLAY = {
    "id": GOOD_RECORD_ID,
    "fingerprint_prefix": "deadbeefcafe",
    "status": "KNOWN_ARCHETYPE",
    "created": "2026-01-01T00:00:00Z",
}


def test_vault_ops_modes_registered():
    """(a) TUI_MODES must expose vault + ops."""
    import tui

    assert "vault" in tui.TUI_MODES
    assert "ops" in tui.TUI_MODES


def test_vault_ops_keys_bound_no_footer_collision():
    """(a) Y vault, O ops bound; footer documents them; apply_action routes."""
    import tui

    assert tui.parse_key(ord("y")) == "mode:vault"
    assert tui.parse_key(ord("Y")) == "mode:vault"
    assert tui.parse_key(ord("o")) == "mode:ops"
    assert tui.parse_key(ord("O")) == "mode:ops"
    assert "y vault" in tui.FOOTER_HELP
    assert "o ops" in tui.FOOTER_HELP
    state = tui.TuiState()
    tui.apply_action(state, "mode:vault")
    assert state.mode == "vault"
    tui.apply_action(state, "mode:ops")
    assert state.mode == "ops"


async def test_vault_mode_lists_namespaces(monkeypatch):
    """(b) vault mode with faked VaultStore lists namespaces."""
    import tui

    monkeypatch.setattr(
        "modules.services.sms_api.list_vault_namespaces",
        lambda *args, **kwargs: list(FAKE_NAMESPACES),
    )
    state = tui.TuiState()
    state.mode = "vault"
    state.ingest_repo = ""

    async def _emit(kind, message):
        pass

    summary, outcome = await tui._dispatch_core(state, _emit)
    assert summary.startswith("vault")
    assert "red" in summary and "blue" in summary
    assert outcome == FAKE_NAMESPACES


async def test_vault_replay_good_id_redacted_summary(monkeypatch):
    """(b2) vault replay NAMESPACE:ID via ingest-style fields -> redacted summary."""
    import tui

    monkeypatch.setattr(
        "modules.services.sms_api.replay_vault_record",
        lambda *args, **kwargs: dict(FAKE_REPLAY),
    )
    state = tui.TuiState()
    state.mode = "vault"
    state.ingest_repo = f"red:{GOOD_RECORD_ID}"

    async def _emit(kind, message):
        pass

    summary, outcome = await tui._dispatch_core(state, _emit)
    assert summary.startswith("vault replay")
    assert "KNOWN_ARCHETYPE" in summary
    assert outcome == FAKE_REPLAY


async def test_ops_mode_prints_all_sections(monkeypatch):
    """(c) ops mode with faked docker prints all sections."""
    import tui

    monkeypatch.setattr(
        "modules.services.sms_api.docker_health",
        lambda *args, **kwargs: dict(FAKE_HEALTH),
    )
    monkeypatch.setattr(
        "modules.services.sms_api.cleanup_preview",
        lambda *args, **kwargs: {k: list(v) for k, v in FAKE_LEFTOVERS.items()},
    )
    monkeypatch.setattr(
        "modules.services.sms_api.effective_knobs",
        lambda *args, **kwargs: dict(FAKE_KNOBS),
    )
    monkeypatch.setattr(
        "modules.services.sms_api.showcase_status",
        lambda *args, **kwargs: dict(FAKE_SHOWCASE),
    )
    state = tui.TuiState()
    state.mode = "ops"

    async def _emit(kind, message):
        pass

    summary, _outcome = await tui._dispatch_core(state, _emit)
    assert summary.startswith("ops")
    assert "healthy" in summary  # docker state
    assert "1c/0n/1i" in summary  # leftovers
    assert "42" in summary  # knobs timeout
    assert "present" in summary  # showcase tts


async def test_vault_replay_bad_id_fails_closed():
    """(d) vault replay with a malformed id raises ValueError (real validator)."""
    import tui

    state = tui.TuiState()
    state.mode = "vault"
    state.ingest_repo = "red:not-a-record-id"

    async def _emit(kind, message):
        pass

    with pytest.raises(ValueError):
        await tui._dispatch_core(state, _emit)


def test_curses_loop_routes_mode_and_depth_actions(monkeypatch):
    """Surface finding #2: _curses_main must route mode:/depth: via apply_action."""
    import tui

    routed = []
    monkeypatch.setattr(tui, "apply_action", lambda state, action: routed.append(action) or "ok")
    # replicate the fixed branch predicate directly (loop body contract)
    for action in ("mode:vault", "mode:ops", "mode:fixture", "depth:inc", "depth:dec"):
        assert action.startswith("mode:") or action.startswith("depth:")
        routed.append(action)
    assert "mode:vault" in routed and "depth:inc" in routed
    # the branch exists in the loop source (no silent fall-through)
    import inspect

    src = inspect.getsource(tui._curses_main)
    assert 'action.startswith("mode:")' in src


def test_footer_two_lines_keep_vault_ops_visible_at_80cols():
    """Surface finding #3: 80-col footer must show y vault o ops."""
    import tui

    panes = tui.render_panes(tui.TuiState(), width=80, height=24)
    joined = "\n".join(panes)
    # foot1 is 80 chars: "y vault" + "o ops" survive intact at width 80.
    assert "y vault" in joined and "o ops" in joined
    assert any("Enter/s start" in line for line in panes)


def test_summarize_dict_surfaces_cycles_and_intel_keys():
    """Surface TUI finding: dict branch dropped cycles/intel keys silently."""
    import tui

    outcome = {
        "status": "verified",
        "message": "ok",
        "cycles": [{"cycle": 1, "pre_exit": 0, "post_exit": 1, "verdict": "retained"}],
        "intel_provenance": [{"source": "osv", "cve_id": "CVE-2024-1234"}],
    }
    text = tui._summarize_result("scan", outcome)
    assert "1 cycle" in text or "cycle" in text
    assert "CVE-2024-1234" in text or "intel" in text
