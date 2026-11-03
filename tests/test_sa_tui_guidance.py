# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""F-214: TUI failure lines surface safe operator guidance, never internals."""

from __future__ import annotations

from types import SimpleNamespace

import tui
from modules.core.config import ConfigurationError

_MSG = "META_MUSE_API_KEY is required for scans. Secure Mitigation System uses Meta Muse only."


def _raise_with(monkeypatch, exc):
    import modules.workflows.workflow as wf

    async def _boom(*a, **k):
        raise exc

    monkeypatch.setattr(wf, "execute_purple_workflow", _boom)


def test_plain_config_error_shows_guidance(monkeypatch, capsys):
    _raise_with(monkeypatch, ConfigurationError(_MSG))
    assert tui.run_plain(["--fixture", "php_command_sink"]) == 1
    out = capsys.readouterr().out
    assert "scan failed (ConfigurationError): META_MUSE_API_KEY is required" in out


def test_plain_mode_dispatch_config_error_shows_guidance(monkeypatch, capsys):
    _raise_with(monkeypatch, ConfigurationError(_MSG))
    assert tui.run_plain(["--mode", "fixture", "--fixture", "php_command_sink"]) == 1
    assert "META_MUSE_API_KEY" in capsys.readouterr().out


def test_token_like_guidance_falls_back_to_type_only():
    exc = ConfigurationError("bad key abcdefghijKLMNOPQRST1234567890")
    assert tui._operator_guidance(exc) == "scan failed (ConfigurationError)"
    assert tui._operator_guidance(ConfigurationError("see https://x")) == (
        "scan failed (ConfigurationError)"
    )


def test_other_exceptions_stay_type_only():
    assert tui._operator_guidance(RuntimeError("secret /home/x")) == "scan failed (RuntimeError)"


def test_guidance_truncated():
    out = tui._operator_guidance(ConfigurationError("word " * 200))
    assert len(out) <= len("scan failed (ConfigurationError): ") + 300


def test_preflight_no_key_hint(monkeypatch):
    import modules.core.config as cfg

    monkeypatch.setattr(
        cfg, "load_config", lambda: SimpleNamespace(inference_mode="hosted", meta_api_key="")
    )
    assert "no META_MUSE_API_KEY" in tui._inference_preflight()
    monkeypatch.setattr(
        cfg, "load_config", lambda: SimpleNamespace(inference_mode="hosted", meta_api_key="k")
    )
    assert tui._inference_preflight() == ""

    def _bad():
        raise ConfigurationError("x")

    monkeypatch.setattr(cfg, "load_config", _bad)
    assert tui._inference_preflight() == "inference: configuration error (ConfigurationError)"


def test_preflight_printed_to_stderr_in_plain(monkeypatch, capsys):
    import modules.core.config as cfg
    import modules.workflows.workflow as wf

    monkeypatch.setattr(
        cfg, "load_config", lambda: SimpleNamespace(inference_mode="hosted", meta_api_key="")
    )

    async def _ok(*a, **k):
        return SimpleNamespace(target="t", status="ok", message="m", success=True)

    monkeypatch.setattr(wf, "execute_purple_workflow", _ok)
    tui.run_plain(["--fixture", "php_command_sink"])
    assert "inference: no META_MUSE_API_KEY" in capsys.readouterr().err


def test_legacy_fixture_key_error_exits_nonzero(monkeypatch, tmp_path, capsys):
    """TUI legacy path: error-status ScanResult (backend returns, not raises)
    must exit nonzero. Live-proven: key-free plain run printed
    `-> error: META_MUSE_API_KEY ...` but exited 0."""
    import tui as tui_mod

    monkeypatch.chdir(tmp_path)

    class FakeResult:
        status = "error"
        message = "META_MUSE_API_KEY is required for scans."
        target = "node_query_sink"
        success = False

    async def fake_run(*args, **kwargs):
        return FakeResult()

    import modules.workflows.workflow as _wf

    monkeypatch.setattr(_wf, "execute_purple_workflow", fake_run)
    rc = tui_mod._run_plain_legacy(
        type("A", (), {"fixture": "node_query_sink", "sweep_passes": None, "binary_target": ""})()
    )
    out = capsys.readouterr().out
    assert rc == 1, f"key-error result must exit 1, got {rc}: {out[:200]}"
    assert "META_MUSE_API_KEY" in out
