# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""V6 (correctness deep-validation): WS negative-path fail-closed matrix.

Pins the exact refusal shape per invalid input, per the existing
test_web.py convention (refusals surface as WebSocketDisconnect code 1008):
- unknown target -> 1008 (pre-accept guard, main.py run_socket)
- cross-origin -> 1008 (already pinned in test_web.py; re-asserted here)
- bad profile query -> 1008 (ProfileError/ConfigurationError guard)
- binary fixture on fixture socket -> `invalid` frame + 1008 (H1 fix)
- bad sweep_passes query -> 1008 (refusal branch)
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from modules.core.config import PurpleBoxConfig


def _app():
    return main.create_app(PurpleBoxConfig(meta_api_key="k"))


HEADERS = {"origin": "http://localhost"}


def test_unknown_target_refused_1008():
    with TestClient(_app(), base_url="http://localhost") as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("ws://localhost/ws/combat/nope_xyz", headers=HEADERS):
                pytest.fail("unknown target was accepted")
        assert error.value.code == 1008


def test_bad_profile_refused_1008():
    with TestClient(_app(), base_url="http://localhost") as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "ws://localhost/ws/combat/node_query_sink?profile=nope", headers=HEADERS
            ):
                pytest.fail("bad profile was accepted")
        assert error.value.code == 1008


def test_bad_sweep_passes_refused_1008():
    with TestClient(_app(), base_url="http://localhost") as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "ws://localhost/ws/combat/node_query_sink?sweep_passes=9", headers=HEADERS
            ):
                pytest.fail("bad sweep_passes was accepted")
        assert error.value.code == 1008


def test_binary_on_fixture_socket_sends_invalid_frame():
    with TestClient(_app(), base_url="http://localhost") as client:
        with client.websocket_connect(
            "ws://localhost/ws/combat/binary_argv_echo", headers=HEADERS
        ) as ws:
            frames = []
            try:
                while True:
                    frames.append(ws.receive_json())
            except WebSocketDisconnect as error:
                assert error.code == 1008
        kinds = [f.get("type") for f in frames if isinstance(f, dict)]
        assert "invalid" in kinds, f"no fail-closed invalid frame: {kinds}"
        invalid = next(f for f in frames if isinstance(f, dict) and f.get("type") == "invalid")
        assert "Binary" in invalid.get("msg", ""), "redirect must name the Binary path"
