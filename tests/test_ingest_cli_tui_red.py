# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED tests for F-01/F-02: honest refusal for unimplemented repo-intake scan paths.

F-01: ``main.cli_runner`` receives ingest_repo/commit_hash kwargs but never
reads them; with scan=None it crashes with an unhandled pydantic
ValidationError. The fix is a defensive guard: any ingest kwargs raise
ValueError with an explicit message (never a traceback class of failure).

F-02: ``tui._dispatch_core`` ingest branch validates RepoIntakeSpec then runs
``execute_purple_workflow(fixture_key)`` and reports ``ingest proven on
fixture <key>`` — verifying the WRONG bytes while reporting the repo's
verdict (false-success). The fix is honest refusal: keep the
RepoIntakeSpec validation, emit a refusal system line, then raise
ValueError WITHOUT calling the fixture workflow.

LAW 4: no payloads, keys, or probe material in this file.
"""

from __future__ import annotations

import pytest

GOOD_URL = "https://github.com/example/demo"
GOOD_HASH = "a" * 40


async def test_cli_runner_ingest_kwargs_raise_value_error_not_validation_error():
    """F-01: ingest kwargs must raise ValueError (guard), never fall through."""
    import main

    with pytest.raises(ValueError, match=r"(?i)staging|unimplemented|not yet"):
        await main.cli_runner(
            None,
            ingest_repo=GOOD_URL,
            commit_hash=GOOD_HASH,
        )


async def test_tui_ingest_mode_refuses_without_calling_fixture_workflow(monkeypatch):
    """F-02: ingest mode must raise ValueError and never run the fixture scan."""
    import tui

    def _bomb(*args, **kwargs):
        raise AssertionError("fixture workflow must not run for ingest mode")

    monkeypatch.setattr("modules.workflows.workflow.execute_purple_workflow", _bomb)
    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = GOOD_URL
    state.ingest_commit = GOOD_HASH

    async def _emit(kind, message):
        pass

    with pytest.raises(ValueError, match=r"(?i)staging|unimplemented|not yet"):
        await tui._dispatch_core(state, _emit)


async def test_tui_ingest_emits_refusal_line_before_raising():
    """F-02: the refusal must be visible — a system line naming host + prefix."""
    import tui

    emitted = []

    async def _emit(kind, message):
        emitted.append((kind, message))

    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = GOOD_URL
    state.ingest_commit = GOOD_HASH
    with pytest.raises(ValueError):
        await tui._dispatch_core(state, _emit)
    system_lines = [msg for kind, msg in emitted if kind == "system"]
    assert system_lines, "expected a system refusal line before raising"
    joined = " ".join(system_lines)
    assert "github.com" in joined
    assert GOOD_HASH[:8] in joined or GOOD_HASH[:7] in joined


def test_repo_intake_spec_still_rejects_bad_inputs():
    """Fail-closed preserved: bad URL/commit still raise at construction."""
    from modules.services.repo_intake import RepoIntakeSpec

    with pytest.raises(ValueError):
        RepoIntakeSpec(url="git://example.com/repo", commit_hash=GOOD_HASH)
    with pytest.raises(ValueError):
        RepoIntakeSpec(url=GOOD_URL, commit_hash="short")
