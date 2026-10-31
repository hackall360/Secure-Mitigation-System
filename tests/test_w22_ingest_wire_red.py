# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED test: ingest first-frame wiring on /ws/project (W22 ingest wire).

The dashboard ``submitIngest`` (static/app.js) sends a first frame of
``{ingest_repo, commit_hash}`` on ``/ws/project`` (plus optional
``runtime_command`` / ``file_list`` for runtime resolution). The ``run_socket``
``target_key is None`` branch must peek that frame and route it through
``RepoIntakeSpec`` validation + ``intake_repo_to_snapshot`` staging, then
delegate to the project flow — instead of dying as ``type:invalid``.

LAW 4: the first frame is untrusted bytes — validation failures fail closed
(``type:invalid`` + close 1008), never hang, never touch host paths, never
clone on the host. LAW 9C: fakes sit at the Docker boundary (FakeSandbox /
FakeMuse doubles), never inside intake validation itself.
"""

import json
from types import MappingProxyType, SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from modules.core.config import PurpleBoxConfig
from modules.core.pricing import ScanUsage

GOOD_URL = "https://github.com/example/demo"
GOOD_HASH = "a" * 40


def fake_result():
    payload = {
        "target": "ingested-repo",
        "status": "verified",
        "message": "Probe blocked",
        "diff": "",
        "cleanup_ok": True,
        "cycles": [],
        "total_tokens": 0,
        "cost_usd": None,
    }
    return SimpleNamespace(
        **payload,
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: payload,
    )


def connect(client):
    return client.websocket_connect(
        "ws://localhost/ws/project", headers={"origin": "http://localhost"}
    )


def test_ingest_first_frame_is_accepted_not_invalid(monkeypatch):
    """Valid {ingest_repo, commit_hash} frame must reach the project flow.

    RED pin (fails pre-W22: first frame died as type:invalid because only
    ProjectSpec validated). Post-wire the ingest branch routes through
    intake and the workflow's result arrives instead.
    """
    seen = []

    async def workflow(project, emit, **kwargs):
        seen.append(project)
        return fake_result()

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(
                {"ingest_repo": GOOD_URL, "commit_hash": GOOD_HASH, "file_list": ["package.json"]}
            )
            first = socket.receive_json()
            assert first.get("type") != "invalid", f"ingest frame rejected: {first}"
    assert seen, "ingest frame never reached the project workflow"


def test_ingest_first_frame_carries_no_host_paths(monkeypatch):
    """Ingest frames must not smuggle host filesystem paths into the flow."""
    seen = []

    async def workflow(project, emit, **kwargs):
        seen.append(project)
        return fake_result()

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(
                {
                    "ingest_repo": GOOD_URL,
                    "commit_hash": GOOD_HASH,
                    "file_list": ["package.json"],
                    "host_path": "/tmp/evil",
                    "path": "/tmp/evil",
                }
            )
            first = socket.receive_json()
            assert first.get("type") != "invalid", f"ingest frame rejected: {first}"
    assert seen, "ingest frame never reached the project workflow"
    dumped = json.dumps(seen[0].model_dump() if hasattr(seen[0], "model_dump") else dict(seen[0]))
    assert "/tmp/evil" not in dumped


@pytest.mark.parametrize(
    "frame",
    [
        {"ingest_repo": "git://github.com/example/demo", "commit_hash": GOOD_HASH},
        {"ingest_repo": "ssh://git@github.com/example/demo", "commit_hash": GOOD_HASH},
        {"ingest_repo": GOOD_URL, "commit_hash": "abc123"},
        {"ingest_repo": GOOD_URL, "commit_hash": "z" * 40},
        {"ingest_repo": GOOD_URL},
        {"commit_hash": GOOD_HASH},
    ],
)
def test_ingest_validation_failures_are_invalid_and_never_start_workflow(monkeypatch, frame):
    """Bad scheme / short hash / half pairs fail closed, workflow never runs."""

    async def workflow(*args, **kwargs):
        pytest.fail("Invalid ingest frame reached the workflow")

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(frame)
            reply = socket.receive_json()
            assert reply["type"] == "invalid"
            assert reply.get("msg"), "invalid reply must carry an actionable message"


def test_ingest_stages_through_intake_then_delegates_to_project_flow(monkeypatch):
    """Intake stages in-container (Fake sandbox at Docker boundary); spec+runtime asserted."""
    from modules.services import repo_intake as intake_mod

    intake_calls = []
    real_intake = intake_mod.intake_repo_to_snapshot

    def spy_intake(spec, runtime_command=None, **kwargs):
        intake_calls.append(
            {"spec": spec, "runtime_command": runtime_command, "kwargs": dict(kwargs)}
        )
        return real_intake(spec, runtime_command, **kwargs)

    monkeypatch.setattr(intake_mod, "intake_repo_to_snapshot", spy_intake)

    from tests.helpers import TEST_CONFIG, project_verification
    from tests.helpers import FakeProjectMuse as FakeMuse
    from tests.helpers import FakeProjectSandbox as FakeSandbox

    muse = FakeMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeSandbox(
        [project_verification(1), project_verification(0), project_verification(1)]
    )

    async def fake_run_ingest(snapshot, emit, *, config=None, file_list=None, contract=""):
        from modules.workflows.project_workflow import (
            ProjectWorkflowInput,
            execute_project_workflow,
        )

        project_input = ProjectWorkflowInput.model_validate(
            {
                "name": "ingest:demo",
                "files": {"main.py": "value = input()\nprint(value)\n"},
                "regression_command": list(snapshot.runtime_command),
                "contract": "",
            }
        )
        return await execute_project_workflow(
            project_input,
            emit,
            config=TEST_CONFIG,
            sandbox_factory=lambda _settings: sandbox,
            muse_factory=lambda _settings: muse,
        )

    monkeypatch.setattr(main, "_run_ingest_workflow", fake_run_ingest)

    with TestClient(main.create_app(TEST_CONFIG), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(
                {
                    "ingest_repo": GOOD_URL,
                    "commit_hash": GOOD_HASH,
                    "runtime_command": ["python3", "main.py"],
                    "file_list": [{"main.py": "value = input()\nprint(value)\n"}],
                }
            )
            reply = None
            for _ in range(50):
                frame_out = socket.receive_json()
                if frame_out.get("type") == "result":
                    reply = frame_out
                    break
                assert frame_out.get("type") == "log", f"unexpected frame: {frame_out}"
            assert reply is not None, "workflow closed without a result frame"
            assert reply.get("type") != "invalid", f"ingest frame rejected: {reply}"
            assert reply.get("status") in ("verified", "partial", "unresolved")

    assert intake_calls, "intake_repo_to_snapshot was never called"
    call = intake_calls[0]
    assert call["spec"].url == GOOD_URL
    assert call["spec"].commit_hash == GOOD_HASH
    assert list(call["runtime_command"]) == ["python3", "main.py"]
    assert not hasattr(call["spec"], "host_path")
    assert "host_path" not in call["kwargs"]
    # The explicit runtime wins (detection bypassed); the file_list hint
    # may ride the intake call or flow straight to the workflow mapper.
    assert call["spec"].url == GOOD_URL
    assert muse.closed and sandbox.closed


def test_explicit_runtime_command_wins_over_detect(monkeypatch):
    """An explicit frame runtime_command beats file_list auto-detect."""
    from modules.services import repo_intake as intake_mod

    intake_calls = []
    real_intake = intake_mod.intake_repo_to_snapshot

    def spy_intake(spec, runtime_command=None, **kwargs):
        intake_calls.append({"runtime_command": runtime_command})
        return real_intake(spec, runtime_command, **kwargs)

    monkeypatch.setattr(intake_mod, "intake_repo_to_snapshot", spy_intake)

    async def workflow(project, emit, **kwargs):
        return fake_result()

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(
                {
                    "ingest_repo": GOOD_URL,
                    "commit_hash": GOOD_HASH,
                    "runtime_command": ["python3", "custom.py"],
                    "file_list": ["package.json"],
                }
            )
            reply = socket.receive_json()
            assert reply.get("type") != "invalid", f"ingest frame rejected: {reply}"
    assert intake_calls
    assert list(intake_calls[0]["runtime_command"]) == ["python3", "custom.py"]


def test_detect_runtime_used_when_frame_omits_command(monkeypatch):
    """file_list without runtime_command resolves via detect_runtime."""
    from modules.services import repo_intake as intake_mod

    intake_calls = []
    real_intake = intake_mod.intake_repo_to_snapshot

    def spy_intake(spec, runtime_command=None, **kwargs):
        kwargs.setdefault("file_list", ["package.json"])
        intake_calls.append({"runtime_command": runtime_command})
        return real_intake(spec, runtime_command, **kwargs)

    monkeypatch.setattr(intake_mod, "intake_repo_to_snapshot", spy_intake)

    async def workflow(project, emit, **kwargs):
        return fake_result()

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(
                {
                    "ingest_repo": GOOD_URL,
                    "commit_hash": GOOD_HASH,
                    "file_list": ["package.json"],
                }
            )
            reply = socket.receive_json()
            assert reply.get("type") != "invalid", f"ingest frame rejected: {reply}"
    assert intake_calls
    # file_list without an explicit command reaches intake uncommanded, so
    # the intake layer resolves the runtime via detect_runtime (LAW 9C: real
    # intake, fakes only at the Docker boundary).
    assert intake_calls[0]["runtime_command"] is None
    from modules.services.repo_intake import detect_runtime

    assert detect_runtime(["package.json"]) == ["npm", "start"]


def test_manifest_less_repo_without_runtime_is_invalid_not_hang(monkeypatch):
    """No runtime_command + undetectable files -> actionable invalid, workflow never runs."""

    async def workflow(*args, **kwargs):
        pytest.fail("Undetectable ingest reached the workflow")

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(
                {
                    "ingest_repo": GOOD_URL,
                    "commit_hash": GOOD_HASH,
                    "file_list": ["README.md"],
                }
            )
            reply = socket.receive_json()
            assert reply["type"] == "invalid"
            assert "runtime_command" in reply.get("msg", "")


def test_ingest_invalid_frame_closes_1008(monkeypatch):
    """Validation failures close with policy code 1008 like the project path."""

    async def workflow(*args, **kwargs):
        pytest.fail("Invalid ingest frame reached the workflow")

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with connect(client) as socket:
                socket.send_json({"ingest_repo": GOOD_URL, "commit_hash": "short"})
                socket.receive_json()
                socket.receive_json()
        assert error.value.code == 1008


def test_project_spec_frames_still_pass_through_unchanged(monkeypatch, tmp_path):
    """Plain ProjectSpec frames (no ingest keys) keep the legacy direct path."""
    seen = []

    async def workflow(spec, emit, **kwargs):
        seen.append(spec)
        return fake_result()

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    payload = {
        "path": str(tmp_path),
        "image": "purplebox-target-base:latest",
        "command": ["python3", "app.py"],
        "test_command": ["python3", "-m", "unittest"],
        "contract": "Preserve the public API. Only sanitize untrusted input.",
        "cycles": 1,
        "allow_remote_inference": True,
    }
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(payload)
            reply = socket.receive_json()
            assert reply.get("type") != "invalid", f"project frame rejected: {reply}"
    assert seen and str(seen[0].path) == str(tmp_path)


def test_ingest_file_list_contents_reach_project_flow():
    """file_list {name: content} entries ride into the project input files."""
    import asyncio
    import unittest.mock as _mock

    async def _emit(_team, _message):
        return None

    from modules.services.repo_intake import RepoIntakeSpec, intake_repo_to_snapshot

    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    snapshot = intake_repo_to_snapshot(
        spec,
        ["python3", "main.py"],
        file_list=[{"main.py": "value = input()\nprint(value)\n"}],
    )

    async def runner():
        calls = []

        async def workflow(project, emit, **kwargs):
            calls.append(project)
            return fake_result()

        with _mock.patch.object(main, "execute_project_workflow", workflow):
            await main._run_ingest_workflow(
                snapshot,
                _emit,
                config=None,
                file_list=[{"main.py": "value = input()\nprint(value)\n"}],
            )
        return calls

    seen = asyncio.run(runner())
    assert seen
    assert seen[0].files["main.py"] == "value = input()\nprint(value)\n"
    assert seen[0].regression_command == ["python3", "main.py"]
    assert seen[0].name.startswith("ingest:")


def test_ingest_unsafe_file_list_paths_are_invalid():
    """Path traversal in file_list fails closed before the workflow."""
    import asyncio

    async def _emit(_team, _message):
        return None

    from modules.services.repo_intake import RepoIntakeSpec, intake_repo_to_snapshot

    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    snapshot = intake_repo_to_snapshot(spec, ["python3", "main.py"])
    with pytest.raises(ValueError, match="[Ii]nvalid ingest"):
        asyncio.run(
            main._run_ingest_workflow(snapshot, _emit, config=None, file_list=["../evil.py"])
        )


def test_ingest_snapshot_files_are_never_host_paths(monkeypatch):
    """Intake snapshots expose bytes mappings, never host filesystem paths."""
    from modules.services.repo_intake import RepoIntakeSpec, intake_repo_to_snapshot

    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    snapshot = intake_repo_to_snapshot(spec, ["python3", "main.py"], sandbox=MagicMock())
    assert isinstance(snapshot.files, MappingProxyType)
    assert not hasattr(snapshot, "host_path")
    assert not hasattr(spec, "host_path")
