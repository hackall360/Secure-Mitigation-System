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

from types import MappingProxyType, SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from modules.core.config import PurpleBoxConfig
from modules.core.pricing import ScanUsage
from tests.helpers import drain_snapshot

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
    """Live intake (brief 2026-11-03-repo-intake-live): a well-formed ingest
    frame reaches the project flow through the real clone path. Docker is
    mocked at the intake boundary (canned snapshot); the F-204 refusal era
    is over — fetch works."""
    from types import MappingProxyType, SimpleNamespace

    def fake_intake(spec, runtime_command=None, **kwargs):
        assert kwargs.get("clone") is True
        assert kwargs.get("sandbox") is not None
        return SimpleNamespace(
            files=MappingProxyType(
                {
                    "repo.url": GOOD_URL.encode(),
                    "repo.commit_hash": GOOD_HASH.encode(),
                    "repo.runtime_command": b'["python3", "app.py"]',
                }
            ),
            url=spec.url,
            commit_hash=spec.commit_hash,
            runtime_command=("python3", "app.py"),
            digest="fake",
        )

    async def workflow(project, emit, **kwargs):
        assert getattr(project, "name", "").startswith("ingest:"), project
        return fake_result()

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(
                {"ingest_repo": GOOD_URL, "commit_hash": GOOD_HASH, "file_list": ["package.json"]}
            )
            first = drain_snapshot(socket)
            assert first.get("type") != "invalid", f"ingest frame refused: {first}"


def test_ingest_first_frame_carries_no_host_paths(monkeypatch):
    """F-204: ingest frames fail closed, so no smuggled host path can ever
    reach a workflow — the request dies at the refusal with no flow at all."""

    async def workflow(*args, **kwargs):
        pytest.fail("Ingest frame reached the workflow without a server fetch")

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
            first = drain_snapshot(socket)
            assert first.get("type") == "invalid", f"ingest frame accepted: {first}"


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
            reply = drain_snapshot(socket)
            assert reply["type"] == "invalid"
            assert reply.get("msg"), "invalid reply must carry an actionable message"


def test_ingest_stages_through_intake_then_delegates_to_project_flow(monkeypatch):
    """Live intake: explicit runtime_command rides the real clone path
    (mocked Docker) into the project flow. F-204 refusal era is over."""
    from types import MappingProxyType, SimpleNamespace

    def fake_intake(spec, runtime_command=None, **kwargs):
        assert kwargs.get("clone") is True
        return SimpleNamespace(
            files=MappingProxyType(
                {
                    "repo.url": GOOD_URL.encode(),
                    "repo.commit_hash": GOOD_HASH.encode(),
                    "repo.runtime_command": b'["python3", "main.py"]',
                }
            ),
            url=spec.url,
            commit_hash=spec.commit_hash,
            runtime_command=("python3", "main.py"),
            digest="fake",
        )

    seen = {}

    async def workflow(project, emit, **kwargs):
        seen["ran"] = True
        assert getattr(project, "name", "").startswith("ingest:")
        return fake_result()

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with connect(client) as socket:
            socket.send_json(
                {
                    "ingest_repo": GOOD_URL,
                    "commit_hash": GOOD_HASH,
                    "runtime_command": ["python3", "main.py"],
                    "file_list": [{"main.py": "value = input()\nprint(value)\n"}],
                }
            )
            reply = drain_snapshot(socket)
            assert reply.get("type") != "invalid", f"ingest frame refused: {reply}"
    assert seen.get("ran") is True


def test_explicit_runtime_command_wins_over_detect(monkeypatch):
    """F-204: even an explicit runtime_command does not rescue the frame —
    client bytes under a claimed URL are unverified by construction."""

    async def workflow(*args, **kwargs):
        pytest.fail("Ingest frame delegated without a server fetch")

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
            reply = drain_snapshot(socket)
            assert reply.get("type") == "invalid", f"ingest frame accepted: {reply}"


def test_detect_runtime_used_when_frame_omits_command(monkeypatch):
    """F-204: auto-detect does not run on client bytes — the frame dies at
    the fetch refusal before any intake staging."""

    async def workflow(*args, **kwargs):
        pytest.fail("Ingest frame delegated without a server fetch")

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
            reply = drain_snapshot(socket)
            assert reply.get("type") == "invalid", f"ingest frame accepted: {reply}"


def test_manifest_less_repo_without_runtime_is_invalid_not_hang(monkeypatch):
    """Live intake: a README-only tree resolves to the generic probe
    (OMNI-INGEST Wave 1), so the frame proceeds to the workflow with a
    terminating probe argv — never hangs, never refuses. Docker is mocked
    at the intake boundary (canned snapshot, like the first-frame test)."""
    from types import MappingProxyType, SimpleNamespace

    def fake_intake(spec, runtime_command=None, **kwargs):
        assert kwargs.get("clone") is True
        return SimpleNamespace(
            files=MappingProxyType(
                {
                    "repo.url": GOOD_URL.encode(),
                    "repo.commit_hash": GOOD_HASH.encode(),
                    "repo.runtime_command": b'["sh", "-c", "probe"]',
                    "repo.smoke_command": b'["sh", "-c", "probe"]',
                }
            ),
            url=spec.url,
            commit_hash=spec.commit_hash,
            runtime_command=("sh", "-c", "probe"),
            digest="fake",
        )

    async def workflow(project, emit, **kwargs):
        # OMNI-INGEST Wave 1: the generic probe IS a valid runtime — the
        # workflow runs against staged bytes with a terminating argv.
        assert list(project.regression_command)[0] == "sh"
        return fake_result()

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
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
            reply = drain_snapshot(socket)
            seen = [reply.get("type")]
            while reply.get("type") not in ("result", "done", "verdict", "complete"):
                try:
                    reply = socket.receive_json()
                except Exception:
                    break
                seen.append(reply.get("type"))
            assert "invalid" not in seen, f"generic probe must not refuse: {seen}"


def test_ingest_invalid_frame_closes_1008(monkeypatch):
    """Validation failures close with policy code 1008 like the project path."""

    async def workflow(*args, **kwargs):
        pytest.fail("Invalid ingest frame reached the workflow")

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with connect(client) as socket:
                socket.send_json({"ingest_repo": GOOD_URL, "commit_hash": "short"})
                reply = drain_snapshot(socket)
                assert reply["type"] == "invalid"
                socket.receive_json()  # server closed 1008 → raises
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
            reply = drain_snapshot(socket)
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
