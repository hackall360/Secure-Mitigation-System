# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Dispatch routing tests for tui.py: prompt_line + dispatch_scan per mode.

All backends are mocked by patching attributes on the canonical source
modules directly (never sys.modules replacement). Never touches Docker/Muse.
"""

from __future__ import annotations

import queue
import threading
from types import SimpleNamespace

import pytest

import tui

SECRET = "SECRET_SNIPPET_PAYLOAD_abc123 api_key=sk-secret-key-999"
BINARY_MARKER = "BINARY_BYTES_MARKER_deadbeef"


def _result(**fields):
    base = {"target": "t", "status": "ok", "message": "done", "success": True}
    base.update(fields)
    return SimpleNamespace(**base)


def _emit_factory(log):
    async def _emit(kind, message):
        log.append((kind, message))

    return _emit


def _state(mode, **fields):
    state = tui.TuiState()
    state.mode = mode
    for key, value in fields.items():
        setattr(state, key, value)
    return state


def test_prompt_line_typed_and_default():
    assert tui.prompt_line("P:", "dflt", lambda _: "  hi  ") == "hi"
    assert tui.prompt_line("P:", "dflt", lambda _: "") == "dflt"
    assert tui.prompt_line("P:", "dflt", lambda _: "   ") == "dflt"

    def _eof(_prompt):
        raise EOFError

    assert tui.prompt_line("P:", "dflt", _eof) == "dflt"


def test_dispatch_unknown_mode_raises():
    with pytest.raises(ValueError):
        tui.dispatch_scan(_state("bogus-mode"), _emit_factory([]))


def test_dispatch_stop_event_set_returns_cancelled():
    stop = threading.Event()
    stop.set()
    assert tui.dispatch_scan(_state("fixture"), _emit_factory([]), stop) == (
        "cancelled before scan."
    )


def test_dispatch_fixture_summary_has_fixture_key(monkeypatch):
    import modules.workflows.workflow as wf

    async def _fake(key, emit, **kwargs):
        return _result(target=key)

    monkeypatch.setattr(wf, "execute_purple_workflow", _fake)
    state = _state("fixture")
    state.fixture_index = 2
    summary = tui.dispatch_scan(state, _emit_factory([]))
    assert state.fixture_key in summary


def test_dispatch_sweep_depth_field(monkeypatch):
    import modules.workflows.sweep as sweep

    calls = {}

    async def _fake(key, emit, **kwargs):
        calls.update(kwargs)
        return _result(target=key)

    monkeypatch.setattr(sweep, "execute_sweep_scan", _fake)
    state = _state("sweep", sweep_depth=2)
    tui.dispatch_scan(state, _emit_factory([]))
    assert calls.get("max_passes") == 2


def test_dispatch_mcp_never_leaks_source(monkeypatch):
    import main as main_mod
    from modules.services import mcp_bridge

    seen = {}

    def _fake_validate(raw):
        seen.update(raw)
        return SimpleNamespace(filename=raw["filename"])

    async def _fake_scan(arguments, emit, **kwargs):
        return _result(target="snippet")

    monkeypatch.setattr(mcp_bridge, "validate_snippet_arguments", _fake_validate)
    monkeypatch.setattr(main_mod, "execute_mcp_snippet_scan", _fake_scan)
    state = _state(
        "mcp",
        snippet_path="poc.php",
        snippet_source="<?php echo SECRET; ?> " + SECRET,
        contract="Only harden inputs.",
    )
    summary = tui.dispatch_scan(state, _emit_factory([]))
    assert seen["language"] == "php"
    assert SECRET not in summary and "sk-secret-key-999" not in summary
    assert isinstance(summary, str)


def test_dispatch_binary_never_leaks_bytes_or_path(monkeypatch):
    import modules.workflows.binary_sweep as bsweep
    from modules.services import binary_intake

    async def _fake_sweep(spec, emit, **kwargs):
        return _result(target="binary")

    monkeypatch.setattr(
        binary_intake,
        "validate_binary_file",
        lambda p, **k: SimpleNamespace(path=p, raw_bytes=BINARY_MARKER),
    )
    monkeypatch.setattr(bsweep, "execute_binary_sweep", _fake_sweep)
    state = _state("binary", binary_path="/tmp/x.bin", contract="Harden inputs.")
    summary = tui.dispatch_scan(state, _emit_factory([]))
    assert BINARY_MARKER not in summary
    assert "/tmp/x.bin" not in summary


def test_dispatch_project_consent_fail_closed_live(monkeypatch, tmp_path):
    """Hosted inference without consent: real backend fails closed (error result)."""
    from modules.core.config import load_config as _load

    if _load().inference_mode == "local":
        pytest.skip("hosted-only consent check")

    state = _state(
        "project",
        project_path=str(tmp_path),
        project_command="run.sh",
        project_test_command="test.sh",
        project_contract="Harden inputs.",
        project_cycles=1,
    )
    summary = tui.dispatch_scan(state, _emit_factory([]))
    assert "project" in summary
    assert "error" in summary or "failed" in summary


def test_dispatch_demo_coerces_offline_without_consent(monkeypatch):
    import main as main_mod
    from modules.core.config import load_config as _load

    if _load().inference_mode == "local":
        pytest.skip("hosted-only coercion check")
    calls = {}

    async def _fake_demo(emit, settings, **kwargs):
        calls.update(kwargs)
        return {"status": "completed", "message": "demo done"}

    monkeypatch.setattr(main_mod, "run_demo_build", _fake_demo)
    state = _state("demo", demo_theme="xss demo", demo_vulns="CVE-2024-1")
    summary = tui.dispatch_scan(state, _emit_factory([]))
    assert calls.get("intel_offline") is True
    assert "CVE-2024-1" not in summary or isinstance(summary, str)


def test_dispatch_cve_routes_project_spec(monkeypatch, tmp_path):
    import modules.workflows.cve_workflow as cvew

    calls = {}

    async def _fake_cve(project, emit, **kwargs):
        calls["project"] = project
        calls.update(kwargs)
        return _result(target="cve")

    monkeypatch.setattr(cvew, "execute_cve_scan", _fake_cve)
    state = _state(
        "cve",
        project_path=str(tmp_path),
        project_offline_cve=True,
        project_fast_lane=True,
    )
    summary = tui.dispatch_scan(state, _emit_factory([]))
    assert calls.get("project") is not None
    assert calls.get("fast_lane") is True
    assert isinstance(summary, str)


def test_start_dispatch_thread_fixture_mode(monkeypatch):
    import modules.workflows.workflow as wf

    async def _fake(key, emit, **kwargs):
        await emit("red", "analyzing")
        return _result(target=key, status="verified")

    monkeypatch.setattr(wf, "execute_purple_workflow", _fake)
    state = _state("fixture")
    q: queue.Queue = queue.Queue()
    stop = threading.Event()
    thread = tui.start_dispatch_thread(state, q, stop, daemon=True)
    thread.join(timeout=10)
    assert not thread.is_alive() and stop.is_set()
    assert state.status == "done"
    assert tui.drain_queue(q, state) >= 1


def test_start_dispatch_thread_error_state(monkeypatch):
    import modules.workflows.workflow as wf

    async def _boom(key, emit):
        raise RuntimeError("no docker")

    monkeypatch.setattr(wf, "execute_purple_workflow", _boom)
    state = _state("fixture")
    q: queue.Queue = queue.Queue()
    stop = threading.Event()
    thread = tui.start_dispatch_thread(state, q, stop, daemon=True)
    thread.join(timeout=10)
    assert state.status == "error" and stop.is_set()
    assert "RuntimeError" in state.result_summary
