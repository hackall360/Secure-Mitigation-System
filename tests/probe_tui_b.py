"""FAIL-FIRST probe B: TUI multi-mode dispatch end state (Writer-B contract).

Desired end state (does NOT exist yet — this probe must be RED):
  * ``tui.prompt_line(prompt, default="", input_func)`` — pure helper that
    returns the typed line (stripped) or ``default`` on empty input / EOF.
  * ``tui.dispatch_scan(state, emit, stop_event=None)`` — sync function
    returning a LAW-4-safe summary string. Routes ``state.mode`` to:
      fixture -> modules.workflows.workflow.execute_purple_workflow
      sweep   -> modules.workflows.sweep.execute_sweep_scan (max_passes)
      mcp     -> validate_snippet_arguments + main.execute_mcp_snippet_scan
      binary  -> validate_binary_file + execute_binary_sweep
      project -> modules.workflows.project_workflow.execute_project_workflow
      demo    -> main.run_demo_build
      cve     -> modules.workflows.cve_workflow.execute_cve_scan
    Backends are lazy-imported at call time so monkeypatching the canonical
    source modules works. ``state`` carries mode-specific fields set as
    plain attributes (mode, sweep_passes, contract, snippet_path,
    snippet_language, binary_target, project_*, demo_theme, demo_vulns).
  * ``tui.run_plain`` accepts --mode/--contract/--snippet/--snippet-language/
    --project-*/--demo-theme/--demo-vulns and exits 2 on unknown --mode.
  * Summaries never contain raw snippet source, binary bytes, or keys (LAW 4).

All backends are mocked (monkeypatch). Never touches Docker or Muse.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

import tui

SECRET_SNIPPET = "SECRET_SNIPPET_PAYLOAD_abc123 api_key=sk-secret-key-999"
BINARY_MARKER = "BINARY_BYTES_MARKER_deadbeef"


def _fake_result(target="t", status="ok", message="done", success=True):
    return SimpleNamespace(target=target, status=status, message=message, success=success)


def _ok_result(*args, **kwargs):
    async def _run(*a, **k):
        return _fake_result()

    return _run(*args, **kwargs)


def _state_with(mode, **fields):
    state = tui.TuiState()
    state.mode = mode
    for key, value in fields.items():
        setattr(state, key, value)
    return state


def _recording_emit_factory(log):
    async def _emit(kind, message):
        log.append((kind, message))

    return _emit


# --- prompt_line -----------------------------------------------------------


def test_prompt_line_returns_typed_line_stripped():
    assert hasattr(tui, "prompt_line"), "tui.prompt_line helper is missing"
    out = tui.prompt_line("Pick: ", "dflt", lambda _: "  hello  ")
    assert out == "hello"


def test_prompt_line_empty_input_returns_default():
    assert hasattr(tui, "prompt_line"), "tui.prompt_line helper is missing"
    assert tui.prompt_line("Pick: ", "dflt", lambda _: "") == "dflt"
    assert tui.prompt_line("Pick: ", "dflt", lambda _: "   ") == "dflt"


def test_prompt_line_eof_returns_default():
    assert hasattr(tui, "prompt_line"), "tui.prompt_line helper is missing"

    def _eof(_prompt):
        raise EOFError

    assert tui.prompt_line("Pick: ", "dflt", _eof) == "dflt"


# --- dispatch_scan routing --------------------------------------------------


def test_dispatch_scan_exists():
    assert hasattr(tui, "dispatch_scan"), "tui.dispatch_scan is missing"
    assert callable(tui.dispatch_scan)


def test_dispatch_fixture_routes_to_purple_workflow(monkeypatch):
    import modules.workflows.workflow as wf

    calls = {}

    async def _fake(fixture_key, emit, **kwargs):
        calls["fixture"] = fixture_key
        return _fake_result(target=fixture_key)

    monkeypatch.setattr(wf, "execute_purple_workflow", _fake)
    log = []
    state = _state_with("fixture")
    state.fixture_index = 1
    summary = tui.dispatch_scan(state, _recording_emit_factory(log))
    assert calls.get("fixture") == state.fixture_key
    assert isinstance(summary, str) and state.fixture_key in summary


def test_dispatch_sweep_passes_max_passes(monkeypatch):
    import modules.workflows.sweep as sweep

    calls = {}

    async def _fake(fixture_key, emit, **kwargs):
        calls.update(kwargs)
        calls["fixture"] = fixture_key
        return _fake_result()

    monkeypatch.setattr(sweep, "execute_sweep_scan", _fake)
    log = []
    state = _state_with("sweep", sweep_passes=3)
    summary = tui.dispatch_scan(state, _recording_emit_factory(log))
    assert calls.get("fixture") == state.fixture_key
    assert calls.get("max_passes") == 3, f"max_passes not routed: {calls}"
    assert isinstance(summary, str)


def test_dispatch_mcp_validates_snippet_then_scans(monkeypatch):
    import main as main_mod
    from modules.services import mcp_bridge

    calls = {}

    def _fake_validate(raw):
        calls["validated"] = dict(raw)
        return SimpleNamespace(filename=raw["filename"])

    async def _fake_scan(arguments, emit, **kwargs):
        calls["scanned"] = True
        return _fake_result(target="snippet")

    monkeypatch.setattr(mcp_bridge, "validate_snippet_arguments", _fake_validate)
    monkeypatch.setattr(main_mod, "execute_mcp_snippet_scan", _fake_scan)
    log = []
    state = _state_with(
        "mcp",
        snippet_path="poc.js",
        snippet_language="javascript",
        snippet_source=SECRET_SNIPPET,
        contract="Only harden inputs.",
    )
    summary = tui.dispatch_scan(state, _recording_emit_factory(log))
    assert calls.get("validated"), "snippet was not validated before scan"
    assert calls.get("scanned"), "MCP snippet scan backend was not called"
    assert SECRET_SNIPPET not in summary
    assert "sk-secret-key-999" not in summary


def test_dispatch_binary_validates_then_sweeps(monkeypatch):
    import modules.workflows.binary_sweep as bsweep
    from modules.services import binary_intake

    calls = {}

    def _fake_validate(path, **kwargs):
        calls["path"] = path
        return SimpleNamespace(path=path, raw_bytes=BINARY_MARKER)

    async def _fake_sweep(spec, emit, **kwargs):
        calls["swept"] = True
        return _fake_result(target="binary")

    monkeypatch.setattr(binary_intake, "validate_binary_file", _fake_validate)
    monkeypatch.setattr(bsweep, "execute_binary_sweep", _fake_sweep)
    log = []
    state = _state_with("binary", binary_target="/tmp/x.bin", contract="Harden inputs.")
    summary = tui.dispatch_scan(state, _recording_emit_factory(log))
    assert calls.get("path") == "/tmp/x.bin"
    assert calls.get("swept"), "binary sweep backend was not called"
    assert BINARY_MARKER not in summary
    assert "/tmp/x.bin" not in summary, "raw path leaked into summary"


def test_dispatch_project_routes_to_project_workflow(monkeypatch):
    import modules.workflows.project_workflow as pwf

    calls = {}

    async def _fake(project, emit, **kwargs):
        calls["project"] = project
        return _fake_result(target="project")

    monkeypatch.setattr(pwf, "execute_project_workflow", _fake)
    log = []
    state = _state_with(
        "project",
        project_image="img:1",
        project_command="run.sh",
        project_test_command="test.sh",
        project_contract="Harden inputs.",
        project_cycles=2,
        project_context_budget=32768,
        project_allow_remote_inference=False,
        project_offline_cve=True,
        project_fast_lane=False,
        project_deep_assessment=False,
    )
    summary = tui.dispatch_scan(state, _recording_emit_factory(log))
    assert calls.get("project") is not None, "project backend was not called"
    assert isinstance(summary, str)


def test_dispatch_demo_routes_to_demo_build(monkeypatch):
    import main as main_mod

    calls = {}

    async def _fake_demo(emit, settings, **kwargs):
        calls.update(kwargs)
        return 0

    monkeypatch.setattr(main_mod, "run_demo_build", _fake_demo)
    log = []
    state = _state_with("demo", demo_theme="xss demo", demo_vulns="CVE-2024-1")
    summary = tui.dispatch_scan(state, _recording_emit_factory(log))
    assert calls.get("theme") == "xss demo", f"demo theme not routed: {calls}"
    assert calls.get("vulns") == "CVE-2024-1", f"demo vulns not routed: {calls}"
    assert isinstance(summary, str)


def test_dispatch_cve_routes_to_cve_scan(monkeypatch):
    import modules.workflows.cve_workflow as cvew

    calls = {}

    async def _fake_cve(project, emit, **kwargs):
        calls["cve"] = True
        calls.update(kwargs)
        return _fake_result(target="cve")

    monkeypatch.setattr(cvew, "execute_cve_scan", _fake_cve)
    log = []
    state = _state_with(
        "cve",
        project_image="img:1",
        project_offline_cve=False,
        project_fast_lane=True,
        project_deep_assessment=False,
    )
    summary = tui.dispatch_scan(state, _recording_emit_factory(log))
    assert calls.get("cve"), "CVE scan backend was not called"
    assert isinstance(summary, str)


def test_dispatch_accepts_stop_event(monkeypatch):
    import modules.workflows.workflow as wf

    async def _fake(fixture_key, emit, **kwargs):
        return _fake_result()

    monkeypatch.setattr(wf, "execute_purple_workflow", _fake)
    log = []
    state = _state_with("fixture")
    summary = tui.dispatch_scan(state, _recording_emit_factory(log), threading.Event())
    assert isinstance(summary, str)


# --- run_plain flags ----------------------------------------------------------


def _patch_all_backends(monkeypatch):
    import main as main_mod
    import modules.workflows.binary_sweep as bsweep
    import modules.workflows.cve_workflow as cvew
    import modules.workflows.project_workflow as pwf
    import modules.workflows.sweep as sweep
    import modules.workflows.workflow as wf
    from modules.services import binary_intake, mcp_bridge

    async def _ok(*a, **k):
        return _fake_result()

    monkeypatch.setattr(wf, "execute_purple_workflow", _ok)
    monkeypatch.setattr(sweep, "execute_sweep_scan", _ok)
    monkeypatch.setattr(bsweep, "execute_binary_sweep", _ok)
    monkeypatch.setattr(pwf, "execute_project_workflow", _ok)
    monkeypatch.setattr(cvew, "execute_cve_scan", _ok)
    monkeypatch.setattr(
        mcp_bridge, "validate_snippet_arguments", lambda raw: SimpleNamespace(**raw)
    )
    monkeypatch.setattr(main_mod, "execute_mcp_snippet_scan", _ok)
    monkeypatch.setattr(
        binary_intake, "validate_binary_file", lambda p, **k: SimpleNamespace(path=p)
    )

    async def _demo(emit, settings, **kwargs):
        return 0

    monkeypatch.setattr(main_mod, "run_demo_build", _demo)


def test_run_plain_accepts_mode_and_contract_flags(monkeypatch, capsys):
    _patch_all_backends(monkeypatch)
    rc = tui.run_plain(
        ["--mode", "fixture", "--contract", "Harden inputs only.", "--fixture", "node_query_sink"]
    )
    assert rc == 0


def test_run_plain_accepts_snippet_flags(monkeypatch, capsys):
    _patch_all_backends(monkeypatch)
    rc = tui.run_plain(
        [
            "--mode",
            "mcp",
            "--snippet",
            "poc.js",
            "--snippet-language",
            "javascript",
            "--contract",
            "Harden inputs.",
        ]
    )
    assert rc == 0


def test_run_plain_accepts_project_flags(monkeypatch, capsys):
    _patch_all_backends(monkeypatch)
    rc = tui.run_plain(
        [
            "--mode",
            "project",
            "--project-image",
            "img:1",
            "--project-command",
            "run.sh",
            "--project-test-command",
            "test.sh",
            "--project-contract",
            "Harden inputs.",
            "--project-cycles",
            "2",
            "--project-context-budget",
            "32768",
            "--project-allow-remote-inference",
            "--project-offline-cve",
            "--project-fast-lane",
            "--project-deep-assessment",
        ]
    )
    assert rc == 0


def test_run_plain_accepts_demo_flags(monkeypatch, capsys):
    _patch_all_backends(monkeypatch)
    rc = tui.run_plain(["--mode", "demo", "--demo-theme", "xss demo", "--demo-vulns", "CVE-2024-1"])
    assert rc == 0


def test_run_plain_rejects_unknown_mode_with_exit_2(monkeypatch, capsys):
    _patch_all_backends(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        tui.run_plain(["--mode", "bogus-mode"])
    assert exc.value.code == 2
