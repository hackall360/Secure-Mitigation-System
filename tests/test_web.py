# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from config import PurpleBoxConfig
from main import create_app


def test_disconnect_cancels_workflow_and_another_scan_is_rejected(monkeypatch):
    cleaned = threading.Event()

    async def slow_workflow(target, emit, **kwargs):
        try:
            await emit("system", "Scan started")
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    monkeypatch.setattr("main.execute_purple_workflow", slow_workflow)
    app = create_app(PurpleBoxConfig())
    with TestClient(app, base_url="http://localhost") as client:
        headers = {"origin": "http://localhost"}
        with client.websocket_connect(
            "ws://localhost/ws/combat/node_query_sink", headers=headers
        ) as first:
            assert first.receive_json()["msg"] == "Scan started"
            with client.websocket_connect(
                "ws://localhost/ws/combat/node_query_sink", headers=headers
            ) as second:
                assert second.receive_json()["type"] == "busy"
        assert cleaned.wait(timeout=2)
        assert client.get("/api/health").json()["busy"] is False


def test_ui_and_registry_work_without_key_or_docker():
    with TestClient(create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        response = client.get("/")
        assert response.status_code == 200 and "Boundary auditor" in response.text
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert len(client.get("/api/targets").json()) == 3
        assert client.get("/api/health").json()["api_key_configured"] is False
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/app.css").status_code == 200


def test_dns_rebinding_host_rejected():
    with TestClient(create_app(), base_url="http://attacker.example") as client:
        assert client.get("/").status_code == 400


@pytest.mark.parametrize("origin", ["https://attacker.example", "null", ""])
def test_cross_origin_socket_rejected(origin):
    with TestClient(create_app(), base_url="http://localhost") as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "ws://localhost/ws/combat/node_query_sink", headers={"origin": origin}
            ):
                pytest.fail("Cross-origin connection was accepted")
        assert error.value.code == 1008


def test_socket_reports_missing_key_without_docker():
    with TestClient(create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with client.websocket_connect(
            "ws://localhost/ws/combat/node_query_sink", headers={"origin": "http://localhost"}
        ) as socket:
            while True:
                event = socket.receive_json()
                if event["type"] == "result":
                    assert event["status"] == "error"
                    assert "META_MUSE_API_KEY" in event["message"]
                    assert event["cleanup_ok"]
                    break


def test_dashboard_exposes_interactive_dark_theme_controls():
    with TestClient(create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        page = client.get("/").text
        for element in (
            'id="pipeline"',
            'id="target-list"',
            'id="diff"',
            'data-filter="red"',
            'name="color-scheme" content="dark"',
            'id="toast"',
        ):
            assert element in page
        script = client.get("/static/app.js").text
        # Untrusted model output must be rendered as text, never parsed as HTML.
        assert "innerHTML" not in script and "insertAdjacentHTML" not in script
        assert "prefers-reduced-motion" in client.get("/static/app.css").text
