# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Unit tests for tui.py non-curses parts: no TTY, no curses, no Docker."""

import asyncio
import queue
import threading
import types

import tui as _tui  # noqa: F401 (keeps module importable without TTY/curses)
from tui import (
    FIXTURE_ORDER,
    HEIGHT,
    WIDTH,
    TuiState,
    apply_action,
    describe_result,
    drain_queue,
    parse_key,
    queue_emit,
    redact_event_text,
    render_panes,
    start_scan_thread,
)


def test_parse_key_digits_and_letters():
    assert parse_key("1") == "select:0"
    assert parse_key("2") == "select:1"
    assert parse_key("3") == "select:2"
    assert parse_key("s") == "start"
    assert parse_key("S") == "start"
    assert parse_key(10) == "start"
    assert parse_key(13) == "start"
    assert parse_key("x") == "stop"
    assert parse_key("X") == "stop"
    assert parse_key(27) == "stop"
    assert parse_key("f") == "filter"
    assert parse_key("q") == "quit"
    assert parse_key("z") == "unknown"


def test_parse_key_arrows_resize_enter_symbols():
    assert parse_key("KEY_UP") == "scroll:up"
    assert parse_key("KEY_DOWN") == "scroll:down"
    assert parse_key("KEY_LEFT") == "scroll:left"
    assert parse_key("KEY_RIGHT") == "scroll:right"
    assert parse_key("KEY_RESIZE") == "resize"
    assert parse_key("KEY_ENTER") == "start"
    assert parse_key("ESC") == "stop"


def test_redact_hides_keys_paths_scripts():
    assert redact_event_text("red", "meta_api_key=sk-12345 leaked") == (
        "[redacted: credentials hidden]"
    )
    assert "<path>" in redact_event_text("system", "wrote /workspace/app.js ok")
    assert "sk-" not in redact_event_text("red", "token sk-abc secret stuff")
    out = redact_event_text("red", "verification_script_python: print('pwn')")
    assert "verification_script" not in out
    assert len(out) <= 170


def test_queue_emit_redacts_and_drains():
    q: queue.Queue = queue.Queue()
    emit = queue_emit(q)
    asyncio.run(emit("red", "hello world"))
    asyncio.run(emit("system", "key=sk-secret-thing"))
    state = TuiState()
    assert drain_queue(q, state) == 2
    assert state.events[0][1].startswith("red: hello")
    assert "sk-secret" not in state.events[1][1]
    assert drain_queue(q, state) == 0


def test_renderer_layout_80x24():
    state = TuiState()
    state.events = [
        ("red", "red: analyzing sink"),
        ("blue", "blue: patch drafted"),
        ("system", "system: baseline passed"),
    ]
    lines = render_panes(state, width=80, height=24)
    assert len(lines) == 24
    assert all(len(line) == 80 for line in lines)
    assert "Secure Mitigation System" in lines[0]
    assert "1:" in lines[1] and "2:" in lines[1] and "3:" in lines[1]
    assert "RED" in lines[2] and "BLUE" in lines[2] and "SYSTEM" in lines[2]
    assert "Result" in lines[-3]
    assert "quit" in lines[-1]
    assert WIDTH == 80 and HEIGHT == 24


def test_renderer_resize_and_filter_scroll():
    state = TuiState()
    state.events = [("red", f"red: line {i}") for i in range(30)]
    small = render_panes(state, width=60, height=12)
    assert len(small) == 12
    state.filter_kind = "blue"
    assert state.visible_events("red") == []
    state.filter_kind = None
    apply_action(state, "filter")
    assert state.filter_kind == "red"
    before = list(state.scroll.values())
    apply_action(state, "scroll:down")
    assert all(v >= b for v, b in zip(state.scroll.values(), before, strict=True))


def test_apply_action_select_cycle():
    state = TuiState()
    apply_action(state, "select:2")
    assert state.fixture_key == FIXTURE_ORDER[2]
    apply_action(state, "select:9")
    assert state.fixture_key == FIXTURE_ORDER[9 % 3]


def test_describe_result_no_trace_leak():
    result = types.SimpleNamespace(
        target="node_query_sink",
        status="verified",
        message="ok",
        traces={"before": "pwn script"},
        finding="SECRET",
    )
    out = describe_result(result)
    assert "node_query_sink" in out and "verified" in out
    assert "pwn" not in out and "SECRET" not in out


def test_start_scan_thread_uses_workflow(monkeypatch):
    import sys

    calls = {}

    async def fake_workflow(key, emit):
        calls["key"] = key
        await emit("red", "fixture ready")
        return types.SimpleNamespace(target=key, status="verified", message="all green")

    # start_scan_thread does a lazy `from modules.workflows.workflow import execute_purple_workflow`,
    # so pre-seeding sys.modules redirects it without touching the real module.
    monkeypatch.setitem(
        sys.modules,
        "modules.workflows.workflow",
        types.SimpleNamespace(execute_purple_workflow=fake_workflow),
    )
    state = TuiState(fixture_index=1)
    q: queue.Queue = queue.Queue()
    stop = threading.Event()
    thread = start_scan_thread(state, q, stop, daemon=True)
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert calls["key"] == FIXTURE_ORDER[1]
    assert stop.is_set()
    assert state.status == "done"
    assert "verified" in state.result_summary
    assert drain_queue(q, state) >= 1


def test_run_plain_success_degrade_no_curses(monkeypatch, capsys):
    """tui.run_plain: fixture workflow mocked, queue drained, redacted summary."""
    import sys
    import types as _types

    async def fake_workflow(key, emit):
        await emit("red", "analyzing sink")
        return _types.SimpleNamespace(target=key, status="verified", message="all green")

    monkeypatch.setitem(
        sys.modules,
        "modules.workflows.workflow",
        _types.SimpleNamespace(execute_purple_workflow=fake_workflow),
    )
    rc = _tui.run_plain(["--fixture", FIXTURE_ORDER[0]])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[red]" in out and "verified" in out and FIXTURE_ORDER[0] in out


def test_run_plain_failure_returns_one(monkeypatch, capsys):
    """tui.run_plain: workflow raising degrades to exit 1 with type name only."""
    import sys
    import types as _types

    async def boom(key, emit):
        raise RuntimeError("docker down")

    monkeypatch.setitem(
        sys.modules,
        "modules.workflows.workflow",
        _types.SimpleNamespace(execute_purple_workflow=boom),
    )
    assert _tui.run_plain([]) == 1
    assert "RuntimeError" in capsys.readouterr().out


def test_start_scan_thread_failure_sets_error_state(monkeypatch):
    """Worker exception: state=error, type-only summary, stop set, no raise."""
    import queue as _queue
    import sys
    import threading as _threading
    import types as _types

    async def boom(key, emit):
        raise ValueError("no docker here")

    monkeypatch.setitem(
        sys.modules,
        "modules.workflows.workflow",
        _types.SimpleNamespace(execute_purple_workflow=boom),
    )
    state = _tui.TuiState()
    q: _queue.Queue = _queue.Queue()
    stop = _threading.Event()
    thread = _tui.start_scan_thread(state, q, stop, daemon=True)
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert state.status == "error" and stop.is_set()
    assert "ValueError" in state.result_summary
    assert _tui.drain_queue(q, state) >= 1


def test_apply_action_scroll_up_and_filter_cycle_return_action():
    """apply_action: scroll:up decrements floors at 0; filter cycles all kinds."""

    state = _tui.TuiState()
    assert _tui.apply_action(state, "scroll:up") == "scroll:up"
    assert all(v == 0 for v in state.scroll.values())
    _tui.apply_action(state, "scroll:down")
    _tui.apply_action(state, "scroll:up")
    assert all(v == 0 for v in state.scroll.values())
    seen = set()
    for _ in range(4):
        seen.add(_tui.apply_action(state, "filter"))
    assert seen == {"filter"}
    assert state.filter_kind is None


def test_parse_key_enter_codes_and_unknowns():
    """parse_key: numeric enter codes start; garbage stays unknown."""

    assert _tui.parse_key(10) == "start"
    assert _tui.parse_key(13) == "start"
    assert _tui.parse_key(27) == "stop"
    assert _tui.parse_key(999999) == "unknown"
    assert _tui.parse_key("") == "unknown"
    assert _tui.parse_key("KEY_BOGUS") == "unknown"
