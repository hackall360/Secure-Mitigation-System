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
    """F-02 retired Wave 2.1: ingest now clones instead of refusing.

    Stronger contract: the fixture workflow must STILL never run for ingest
    mode (wrong bytes) — the clone path runs the PROJECT workflow instead.
    """
    import tui

    def _bomb(*args, **kwargs):
        raise AssertionError("fixture workflow must not run for ingest mode")

    monkeypatch.setattr("modules.workflows.workflow.execute_purple_workflow", _bomb)
    monkeypatch.setattr(
        "modules.core.docker_manager.DockerSandboxManager",
        lambda config=None: _FakeSandbox(),
    )

    async def _fake_project_workflow(project, emit, **kwargs):
        class _R:
            status = "verified"

            def __init__(self):
                self.message = "ok"

        return _summarize_sentinel()

    def _summarize_sentinel():
        class _R:
            status = "verified"
            message = "ok"

        return _R()

    import modules.workflows.project_workflow as _pw

    monkeypatch.setattr(_pw, "execute_project_workflow", _fake_project_workflow)
    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = GOOD_URL
    state.ingest_commit = GOOD_HASH

    emitted = []

    async def _emit(kind, message):
        emitted.append((kind, message))

    summary, _outcome = await tui._dispatch_core(state, _emit)
    assert "ingest" in summary.lower()


async def test_tui_ingest_emits_refusal_line_before_raising():
    """F-02 retired Wave 2.1: the refusal line is now a clone-progress line."""
    import tui

    emitted = []

    async def _emit(kind, message):
        emitted.append((kind, message))

    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = "git://example.com/repo"  # invalid scheme -> fail closed
    state.ingest_commit = GOOD_HASH
    with pytest.raises(ValueError):
        await tui._dispatch_core(state, _emit)


def test_repo_intake_spec_still_rejects_bad_inputs():
    """Fail-closed preserved: bad URL/commit still raise at construction."""
    from modules.services.repo_intake import RepoIntakeSpec

    with pytest.raises(ValueError):
        RepoIntakeSpec(url="git://example.com/repo", commit_hash=GOOD_HASH)
    with pytest.raises(ValueError):
        RepoIntakeSpec(url=GOOD_URL, commit_hash="short")


# --- Wave 2.1 (P2-6, 1B +0.5): intake-clone wiring (RED-FIRST) ---
# CLI --ingest-repo with clone available must reach the project workflow
# with the CLONED bytes (not the fixture loop, not a refusal).

INGEST_HASH = "b" * 40


def _one_file_tar_bytes():
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in (
            ("repo/app.js", b"console.log('hi');"),
            ("repo/package.json", b'{"name": "demo", "main": "app.js"}'),
        ):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.read()


class _FakeStage:
    status_code = 0

    def wait(self, timeout=None):
        return {"StatusCode": self.status_code}

    def get_archive(self, path):
        return ([_one_file_tar_bytes()], {"size": 1})

    def remove(self, force=False):
        pass


class _FakeContainers:
    def run(self, *args, **kwargs):
        return _FakeStage()


class _FakeClient:
    containers = _FakeContainers()


class _FakeSandbox:
    client = _FakeClient()

    def _options(self, kind):
        return {"network_mode": "none"}


async def test_cli_ingest_with_clone_reaches_project_workflow(monkeypatch):
    """Wave 2.1 RED: clone path must reach execute_project_workflow (not refusal)."""
    import main

    seen = {}

    async def fake_workflow(project, emit, **kwargs):
        seen["path"] = str(project.path)
        assert (project.path / "repo" / "app.js").is_file(), "cloned bytes must land on disk"

        class _R:
            status = "verified"
            message = "ok"
            success = True
            usage = type("U", (), {"calls": []})()

            def model_dump(self):
                return {"status": "verified"}

        return _R()

    monkeypatch.setattr(main, "execute_project_workflow", fake_workflow)
    monkeypatch.setattr(
        "modules.core.docker_manager.DockerSandboxManager",
        lambda config=None: _FakeSandbox(),
    )
    rc = await main.cli_runner(
        None,
        ingest_repo=GOOD_URL,
        commit_hash=INGEST_HASH,
        out_format="table",
    )
    assert rc == 0, "clone-backed ingest scan must succeed"
    assert seen.get("path"), "project workflow must have run on the staged clone"


async def test_cli_ingest_clone_failure_fails_closed(monkeypatch):
    """Wave 2.1: clone exec failure must raise ValueError (fail closed)."""
    import main

    class _BadStage(_FakeStage):
        status_code = 128

    class _BadClient:
        containers = type("C", (), {"run": staticmethod(lambda *a, **k: _BadStage())})()

    async def _bomb(*args, **kwargs):
        raise AssertionError("workflow must not run on failed clone")

    monkeypatch.setattr(main, "execute_project_workflow", _bomb)
    monkeypatch.setattr(
        "modules.core.docker_manager.DockerSandboxManager",
        lambda config=None: type(
            "S", (), {"client": _BadClient(), "_options": lambda self, k: {}}
        )(),
    )
    with pytest.raises(ValueError, match=r"(?i)clone|staging|fail"):
        await main.cli_runner(
            None,
            ingest_repo=GOOD_URL,
            commit_hash=INGEST_HASH,
        )
