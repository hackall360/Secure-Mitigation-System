# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Ingest-mode TUI UX contract (slice/intake-35): preflight hint, dispatch,
result summary, optional-commit normalization, consent auto-grant visibility.

Scope: ``tui.py`` ingest UX only (never main.py/config.py/repo_intake.py).
In-process only: backends are monkeypatched fakes; no curses, no Docker,
run_plain paths only. LAW 4: no repo URLs, keys, or probe material here —
GOOD_URL/GOOD_HASH are inert fixtures already used by test_ingest_cli_tui_red.
"""

from __future__ import annotations

from types import SimpleNamespace

GOOD_URL = "https://github.com/example/demo"
GOOD_HASH = "a" * 40


def _result(**fields):
    base = {"target": "t", "status": "verified", "message": "ok", "success": True}
    base.update(fields)
    return SimpleNamespace(**base)


async def _null_emit(kind, message):
    return None


def _patch_ingest_path(monkeypatch, result=None, project_path="/tmp/staged"):
    """Route TUI ingest through faked _ingest_repo_to_project + project workflow."""
    import main as main_mod
    import modules.workflows.project_workflow as pwf

    seen = {}
    result = result if result is not None else _result()

    async def _fake_ingest(repo, commit, emit, **kwargs):
        seen["url"] = repo
        seen["commit"] = commit
        return SimpleNamespace(path=project_path, image="img")

    async def _fake_workflow(project, emit, **kwargs):
        seen["ran"] = True
        return result

    monkeypatch.setattr(main_mod, "_ingest_repo_to_project", _fake_ingest)
    monkeypatch.setattr(pwf, "execute_project_workflow", _fake_workflow)
    return seen


def test_ingest_preflight_empty_repo_hints_before_dispatch(monkeypatch, capsys):
    """Empty repo field: one-line stderr hint BEFORE dispatch, scan still runs."""
    import tui

    seen = _patch_ingest_path(monkeypatch)
    rc = tui.run_plain(["--mode", "ingest", "--ingest-repo", "", "--commit-hash", ""])
    assert rc == 0
    # The dispatch still ran (empty repo hits the mock boundary, not a refusal).
    assert seen.get("ran") is True
    captured = capsys.readouterr()
    assert "ingest: enter a repo URL (https://)" in captured.err


def test_ingest_preflight_empty_repo_hint_exact_line(monkeypatch, capsys):
    """Empty repo hint is exactly the consent-framing one-liner on stderr."""
    import tui

    _patch_ingest_path(monkeypatch)
    tui.run_plain(["--mode", "ingest"])
    err = capsys.readouterr().err
    line = "ingest: enter a repo URL (https://) — optional pinned commit; fetching it authorizes the scan"
    assert line in err


def test_ingest_keyless_reuses_inference_preflight(monkeypatch, capsys):
    """Repo set + hosted keyless: the inference preflight line still shows."""
    import modules.core.config as cfg
    import tui

    monkeypatch.setattr(
        cfg, "load_config", lambda: SimpleNamespace(inference_mode="hosted", meta_api_key="")
    )
    _patch_ingest_path(monkeypatch)
    rc = tui.run_plain(["--mode", "ingest", "--ingest-repo", GOOD_URL, "--commit-hash", GOOD_HASH])
    assert rc == 0
    captured = capsys.readouterr()
    assert "inference: no META_MUSE_API_KEY" in captured.err
    # The dispatch summary (with staged identity) reaches stdout, not a recompute.
    assert "github.com" in captured.out
    assert GOOD_HASH[:12] in captured.out
    assert GOOD_URL not in captured.out
    assert "allow-remote" not in captured.out


def test_summarize_ingest_surfaces_repo_identity(monkeypatch):
    """Summary names host + commit[:12] (never the full URL) and the verdict."""
    import tui

    record = _result()
    seen = _patch_ingest_path(monkeypatch, result=record)
    import asyncio

    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = GOOD_URL
    state.ingest_commit = GOOD_HASH

    summary, _outcome = asyncio.run(tui._dispatch_core(state, _null_emit))
    assert summary.startswith("ingest")
    assert "github.com" in summary
    assert GOOD_HASH[:12] in summary
    assert GOOD_URL not in summary  # LAW 4: never echo the full URL
    assert "verified" in summary
    assert seen.get("ran") is True


def test_empty_commit_normalizes_to_none(monkeypatch):
    """D2: "" commit flows as None (HEAD as-is), not "" breaking validation."""
    import tui

    seen = _patch_ingest_path(monkeypatch)
    import asyncio

    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = GOOD_URL
    state.ingest_commit = ""

    asyncio.run(tui._dispatch_core(state, _null_emit))
    assert seen.get("commit") is None


def test_success_summary_has_no_consent_nag(monkeypatch):
    """D3: explicit repo action was the grant — success shows no allow-remote text."""
    import tui

    _patch_ingest_path(monkeypatch, result=_result())
    import asyncio

    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = GOOD_URL
    state.ingest_commit = GOOD_HASH

    summary, _ = asyncio.run(tui._dispatch_core(state, _null_emit))
    assert "allow-remote" not in summary


def test_keyless_failure_still_shows_key_guidance(monkeypatch):
    """Keyless backend failure keeps the operator key guidance (F-214 pattern)."""
    import tui
    from modules.core.config import ConfigurationError

    async def _raise(*args, **kwargs):
        raise ConfigurationError("META_MUSE_API_KEY is required for scans.")

    import main as main_mod
    import modules.workflows.project_workflow as pwf

    async def _fake_ingest(repo, commit, emit, **kwargs):
        return SimpleNamespace(path="/tmp/staged", image="img")

    monkeypatch.setattr(main_mod, "_ingest_repo_to_project", _fake_ingest)
    monkeypatch.setattr(pwf, "execute_project_workflow", _raise)

    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = GOOD_URL
    state.ingest_commit = GOOD_HASH
    try:
        import asyncio

        asyncio.run(tui._dispatch_core(state, _null_emit))
    except ConfigurationError as exc:
        assert "META_MUSE_API_KEY" in str(exc)
    else:  # pragma: no cover - fail closed: the error must surface
        raise AssertionError("keyless failure must raise, not swallow")
