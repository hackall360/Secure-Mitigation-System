# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""run_plain flag tests for the TUI dispatch surface.

All backends are mocked by patching attributes on the canonical source
modules directly (never sys.modules replacement). Never touches Docker/Muse.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import tui


def _result(**fields):
    base = {"target": "t", "status": "ok", "message": "done", "success": True}
    base.update(fields)
    return SimpleNamespace(**base)


def _patch_all(monkeypatch):
    import main as main_mod
    import modules.workflows.binary_sweep as bsweep
    import modules.workflows.cve_workflow as cvew
    import modules.workflows.project_workflow as pwf
    import modules.workflows.sweep as sweep
    import modules.workflows.workflow as wf
    from modules.services import binary_intake, mcp_bridge

    async def _ok(*args, **kwargs):
        return _result()

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
        return {"status": "completed", "message": "demo done"}

    monkeypatch.setattr(main_mod, "run_demo_build", _demo)


def test_run_plain_mode_fixture(monkeypatch, capsys):
    _patch_all(monkeypatch)
    assert tui.run_plain(["--mode", "fixture", "--fixture", "php_command_sink"]) == 0
    out = capsys.readouterr().out
    assert "mode=fixture" in out and "fixture" in out


def test_run_plain_mode_sweep(monkeypatch, capsys):
    _patch_all(monkeypatch)
    assert tui.run_plain(["--mode", "sweep", "--fixture", "node_query_sink"]) == 0


def test_run_plain_mode_mcp_snippet_file(monkeypatch, capsys, tmp_path):
    _patch_all(monkeypatch)
    snippet = tmp_path / "poc.js"
    snippet.write_text("console.log('hi');", encoding="utf-8")
    rc = tui.run_plain(["--mode", "mcp", "--snippet", str(snippet), "--contract", "Harden inputs."])
    assert rc == 0


def test_run_plain_mode_project(monkeypatch, capsys, tmp_path):
    _patch_all(monkeypatch)
    rc = tui.run_plain(
        [
            "--mode",
            "project",
            "--project-path",
            str(tmp_path),
            "--project-command",
            "run.sh",
            "--project-test-command",
            "test.sh",
            "--project-contract",
            "Harden inputs.",
            "--project-cycles",
            "1",
        ]
    )
    assert rc == 0


def test_run_plain_mode_demo(monkeypatch, capsys):
    _patch_all(monkeypatch)
    rc = tui.run_plain(["--mode", "demo", "--demo-theme", "xss demo", "--demo-vulns", "CVE-2024-1"])
    assert rc == 0


def test_run_plain_mode_cve_offline(monkeypatch, capsys, tmp_path):
    _patch_all(monkeypatch)
    rc = tui.run_plain(
        [
            "--mode",
            "cve",
            "--project-path",
            str(tmp_path),
            "--project-offline-cve",
            "--project-fast-lane",
        ]
    )
    assert rc == 0


def test_run_plain_mode_binary_missing_file_fails_closed(monkeypatch, capsys):
    import modules.workflows.binary_sweep as bsweep

    async def _never(*args, **kwargs):
        raise AssertionError("sweep must not run for missing file")

    monkeypatch.setattr(bsweep, "execute_binary_sweep", _never)
    rc = tui.run_plain(
        ["--mode", "binary", "--contract", "x", "--binary-path", "/no/such/file.bin"]
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "mode=binary" in out


def test_run_plain_unknown_mode_exits_2(monkeypatch, capsys):
    _patch_all(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        tui.run_plain(["--mode", "bogus-mode"])
    assert exc.value.code == 2
