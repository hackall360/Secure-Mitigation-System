# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from main import create_app
from modules.core.config import PurpleBoxConfig


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


def test_socket_redaction_failure_fails_closed(monkeypatch):
    """aa09566 hunk 2: a redaction raise must never leak the unredacted dump.

    Pre-fix the `except Exception: pass` left `safe` as the raw
    `model_dump()` — probe scripts and payloads rode the socket to the
    browser (fail-open LAW 4 violation). Post-fix the client receives
    status=error with zero exploit bytes.
    """
    from modules.core.agents import RedTeamFinding
    from modules.workflows.workflow import ScanResult

    async def evil_workflow(target, emit, **kwargs):
        result = ScanResult(
            target=target,
            status="verified",
            message="ok",
            finding=RedTeamFinding(
                vulnerability_class="vc",
                sink_location="s",
                analysis_summary="a",
                verification_script_python="EVIL-SOCKET()",
            ),
        )
        result.traces = {"before": "PAYLOAD-SOCKET" * 10}
        return result

    def boom_redact(result):
        raise RuntimeError("redactor down")

    monkeypatch.setattr("main.execute_purple_workflow", evil_workflow)
    monkeypatch.setattr("modules.workflows.workflow.redact_fixture_result_for_user", boom_redact)
    with TestClient(create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        with client.websocket_connect(
            "ws://localhost/ws/combat/node_query_sink", headers={"origin": "http://localhost"}
        ) as socket:
            while True:
                import json as _json

                event = socket.receive_json()
                if event["type"] == "result":
                    assert event["status"] == "error"
                    assert "redaction failed" in event["message"].lower()
                    assert "EVIL-SOCKET()" not in _json.dumps(event)
                    assert "PAYLOAD-SOCKET" not in _json.dumps(event)
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

    from main import create_app
    from modules.core.config import PurpleBoxConfig

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
        from modules.workflows.workflow import ScanResult

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
        from modules.workflows.workflow import ScanResult

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
                        "scan_profile": "light",
                        "cycles": 3,
                        "red_agents": 5,
                        "blue_agents": 5,
                        "context_budget": 32768,
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
    assert seen.get("scan_profile") == "light"
    assert seen.get("cycles") == 3
    assert seen.get("red_agents") == 5
    assert seen.get("blue_agents") == 5
    assert seen.get("context_budget") == 32768


def test_demo_request_accepts_hardening_fields_with_clamps(monkeypatch):
    """L3: the demo socket parses demo_size/flaw_count/seed with server clamps."""
    import json as _json

    import main as _main

    seen = {}

    async def fake_build(emit, config, **kwargs):
        seen.update(kwargs)
        await emit("green", "done")
        return {"status": "no_findings", "message": "probe", "project": "ai-demo"}

    monkeypatch.setattr(_main, "run_demo_build", fake_build)
    app = _main.create_app(PurpleBoxConfig(meta_api_key="k"))
    from fastapi.testclient import TestClient as _TC

    with _TC(app, base_url="http://localhost") as client:
        headers = {"origin": "http://localhost"}
        with client.websocket_connect("ws://localhost/ws/demo", headers=headers) as socket:
            socket.send_text(
                _json.dumps(
                    {
                        "theme": "xss",
                        "demo_size": "bogus",
                        "flaw_count": 99,
                        "seed": 7,
                    }
                )
            )
            while True:
                event = socket.receive_json()
                if event["type"] == "result":
                    break
    assert seen.get("demo_size") == "standard"
    assert seen.get("flaw_count") == 8
    assert seen.get("seed") == 7
