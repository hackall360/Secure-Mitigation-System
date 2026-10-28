# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Project CLI and same-origin WebSocket integration contracts."""

import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from config import PurpleBoxConfig
from pricing import ScanUsage


def project_payload(tmp_path):
    return {
        "path": str(tmp_path),
        "image": "purplebox-target-base:latest",
        "command": ["python3", "app.py"],
        "test_command": ["python3", "-m", "unittest"],
        "contract": "Preserve the public API. Only sanitize untrusted input.",
        "cycles": 2,
        "context_budget": 32768,
        "allow_remote_inference": True,
    }


def fake_result():
    payload = {
        "target": "local-project",
        "status": "verified",
        "message": "Probe blocked",
        "diff": "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n",
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


def test_project_socket_passes_spec_and_profile(tmp_path, monkeypatch):
    seen = []

    async def workflow(spec, emit, **kwargs):
        seen.append((spec, kwargs["config"]))
        await emit("red", "Cycle 1: analyze")
        return fake_result()

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with client.websocket_connect(
            "ws://localhost/ws/project?profile=economy", headers={"origin": "http://localhost"}
        ) as socket:
            socket.send_json(project_payload(tmp_path))
            assert socket.receive_json()["team"] == "red"
            assert socket.receive_json()["status"] == "verified"
    assert seen[0][0].cycles == 2
    assert seen[0][1].red_team_model == seen[0][1].blue_team_model


@pytest.mark.parametrize("origin", ["https://attacker.example", "null", ""])
def test_project_socket_rejects_cross_origin(origin):
    with TestClient(main.create_app(), base_url="http://localhost") as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("ws://localhost/ws/project", headers={"origin": origin}):
                pytest.fail("Cross-origin project execution accepted")
        assert error.value.code == 1008


@pytest.mark.parametrize("change", [{"cycles": 0}, {"command": "rm -rf /"}, {"unknown": True}])
def test_invalid_project_never_starts_workflow(tmp_path, change, monkeypatch):
    async def workflow(*args, **kwargs):
        pytest.fail("Invalid project reached workflow")

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(), base_url="http://localhost") as client:
        with client.websocket_connect(
            "ws://localhost/ws/project", headers={"origin": "http://localhost"}
        ) as socket:
            socket.send_json({**project_payload(tmp_path), **change})
            assert socket.receive_json()["type"] == "invalid"
        assert client.get("/api/health").json()["busy"] is False


def test_project_disconnect_cancels_and_shared_lock_blocks_fixture(tmp_path, monkeypatch):
    cleaned = threading.Event()

    async def workflow(spec, emit, **kwargs):
        try:
            await emit("system", "Started project")
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(), base_url="http://localhost") as client:
        headers = {"origin": "http://localhost"}
        with client.websocket_connect("ws://localhost/ws/project", headers=headers) as first:
            first.send_json(project_payload(tmp_path))
            assert first.receive_json()["msg"] == "Started project"
            with client.websocket_connect(
                "ws://localhost/ws/combat/node_query_sink", headers=headers
            ) as second:
                assert second.receive_json()["type"] == "busy"
        assert cleaned.wait(2)
        assert client.get("/api/health").json()["busy"] is False


def test_local_health_ready_without_hosted_key():
    config = PurpleBoxConfig(inference_mode="local", meta_base_url="http://127.0.0.1:8081/v1")
    with TestClient(main.create_app(config), base_url="http://localhost") as client:
        health = client.get("/api/health").json()
        assert health["inference_mode"] == "local"
        assert health["inference_ready"]
        assert not health["api_key_configured"]


def test_cli_project_exports_private_report_and_patch(tmp_path, monkeypatch):
    seen = []

    async def workflow(spec, emit, **kwargs):
        seen.append(spec)
        return fake_result()

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    output = tmp_path / "reports"
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--project",
            str(tmp_path),
            "--command",
            '["python3", "app.py"]',
            "--test-command",
            '["python3", "-m", "unittest"]',
            "--contract",
            "Preserve API",
            "--cycles",
            "2",
            "--allow-remote-inference",
            "--output-dir",
            str(output),
        ],
    )
    assert main.main() == 0
    assert seen[0].cycles == 2
    report = next(output.glob("*/report.json"))
    assert json.loads(report.read_text())["status"] == "verified"
    assert report.stat().st_mode & 0o777 == 0o600
    assert report.parent.stat().st_mode & 0o777 == 0o700
    assert (report.parent / "candidate.patch").is_file()


def test_cli_requires_project_runtime_contract(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["main.py", "--project", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2
