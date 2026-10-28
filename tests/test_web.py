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
            msg = first.receive_json()
            if msg.get("msg") != "Scan started":
                assert msg["team"] == "system"  # hello preamble precedes workflow
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


def test_demo_route_registered_and_rejects_origin_mismatch():
    from fastapi.testclient import TestClient

    from config import PurpleBoxConfig
    from main import create_app

    app = create_app(PurpleBoxConfig(meta_api_key="unit-test-key"))
    routes = [getattr(r, "path", "") for r in app.routes]
    assert "/ws/demo" in routes
    client = TestClient(app)
    try:
        with client.websocket_connect("/ws/demo", headers={"origin": "http://evil.example"}):
            raise AssertionError("origin mismatch should close")
    except Exception:
        pass


def test_ws_research_query_enables_sidecar_config(monkeypatch):
    """H4: ?research=on allowlists scanners into the per-scan config."""

    import main as _main

    seen = {}

    async def fake_workflow(target, emit, **kwargs):
        seen.update(
            kwargs.get("config").__dict__ if hasattr(kwargs.get("config"), "__dict__") else {}
        )
        await emit("system", "done")
        from workflow import ScanResult

        return ScanResult(target="t", status="error", message="probe")

    monkeypatch.setattr(_main, "execute_purple_workflow", fake_workflow)
    app = _main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        headers = {"origin": "http://localhost"}
        with client.websocket_connect(
            "ws://localhost/ws/combat/node_query_sink?research=on&research_scanners=trivy,evil",
            headers=headers,
        ) as socket:
            while True:
                event = socket.receive_json()
                if event["type"] == "result":
                    break
    assert seen.get("research_enabled") is True
    assert seen.get("research_scanners") == ("trivy",)


def test_ws_research_absent_stays_off(monkeypatch):
    """H4: no query params means the sidecar stays off (opt-in)."""
    import main as _main

    seen = {}

    async def fake_workflow(target, emit, **kwargs):
        config = kwargs.get("config")
        seen["enabled"] = config.research_enabled
        seen["scanners"] = config.research_scanners
        await emit("system", "done")
        from workflow import ScanResult

        return ScanResult(target="t", status="error", message="probe")

    monkeypatch.setattr(_main, "execute_purple_workflow", fake_workflow)
    app = _main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        headers = {"origin": "http://localhost"}
        with client.websocket_connect(
            "ws://localhost/ws/combat/node_query_sink", headers=headers
        ) as socket:
            while True:
                event = socket.receive_json()
                if event["type"] == "result":
                    break
    assert seen == {"enabled": False, "scanners": ()}


def test_demo_request_accepts_brief_and_vulns_fields(monkeypatch):
    """I1: the demo socket parses build_brief + vulns alongside the theme."""
    import json as _json

    import main as _main

    seen = {}

    async def fake_build(emit, config, **kwargs):
        seen.update(kwargs)
        await emit("green", "done")
        return {"status": "no_findings", "message": "probe", "project": "ai-demo"}

    monkeypatch.setattr(_main, "run_demo_build", fake_build)
    app = _main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        headers = {"origin": "http://localhost"}
        with client.websocket_connect("ws://localhost/ws/demo", headers=headers) as socket:
            socket.send_text(
                _json.dumps(
                    {
                        "theme": "xss",
                        "build_brief": "a tiny notes app",
                        "vulns": "CVE-2024-3094, sqli",
                    }
                )
            )
            while True:
                event = socket.receive_json()
                if event["type"] == "result":
                    break
    assert seen.get("theme") == "xss"
    assert seen.get("build_brief") == "a tiny notes app"
    assert seen.get("vulns") == "CVE-2024-3094, sqli"
