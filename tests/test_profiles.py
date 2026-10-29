# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import asyncio
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from main import create_app
from modules.core.config import PurpleBoxConfig
from modules.core.profiles import ProfileError, apply_profile, available_profiles, default_profile

BASETEN = replace(
    PurpleBoxConfig(),
    meta_base_url="https://inference.baseten.co/v1",
    red_team_model="meta-models/muse-spark-open-1026",
    blue_team_model="meta-models/muse-spark-open-1026",
)


@pytest.mark.parametrize(
    "key,red,blue",
    [
        ("economy", "muse-spark-1.3", "muse-spark-1.3"),
        ("balanced", "muse-spark-1.3", "muse-wonder-1.0"),
        ("quality", "muse-wonder-1.0", "muse-wonder-1.0"),
    ],
)
def test_profiles_map_to_fixed_model_pairs(key, red, blue):
    chosen = apply_profile(PurpleBoxConfig(meta_api_key="k"), key)
    assert (chosen.red_team_model, chosen.blue_team_model) == (red, blue)
    assert chosen.meta_api_key == "k"


@pytest.mark.parametrize("key", [None, "", "custom"])
def test_custom_keeps_configured_models(key):
    config = PurpleBoxConfig()
    assert apply_profile(config, key) is config


@pytest.mark.parametrize("key", ["muse-wonder-1.0", "gpt-4", "../x", "QUALITY"])
def test_unknown_profile_rejected(key):
    with pytest.raises(ProfileError):
        apply_profile(PurpleBoxConfig(), key)


def test_meta_profiles_not_offered_for_other_endpoints():
    assert available_profiles(BASETEN) == {}
    assert default_profile(BASETEN) == "custom"
    with pytest.raises(ProfileError):
        apply_profile(BASETEN, "economy")


def test_default_profile_matches_configured_pair():
    assert default_profile(PurpleBoxConfig()) == "balanced"


def test_health_lists_profiles():
    with TestClient(create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        health = client.get("/api/health").json()
    assert [p["key"] for p in health["profiles"]] == ["economy", "balanced", "quality"]
    assert health["default_profile"] == "balanced"


def test_socket_uses_chosen_profile(monkeypatch):
    seen = {}

    async def capture(target, emit, *, config=None, **kwargs):
        seen["models"] = (config.red_team_model, config.blue_team_model)
        await asyncio.sleep(0)
        from modules.workflows.workflow import ScanResult

        return ScanResult(target=target, status="not_confirmed", message="test")

    monkeypatch.setattr("main.execute_purple_workflow", capture)
    app = create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        with client.websocket_connect(
            "ws://localhost/ws/combat/node_query_sink?profile=economy",
            headers={"origin": "http://localhost"},
        ) as socket:
            first = socket.receive_json()
            if first["type"] != "result":
                assert first["team"] == "system"  # hello preamble precedes result
                assert socket.receive_json()["type"] == "result"
    assert seen["models"] == ("muse-spark-1.3", "muse-spark-1.3")


@pytest.mark.parametrize("profile", ["gpt-4", "muse-wonder-1.0", "x" * 50])
def test_socket_refuses_unknown_profile_before_any_work(monkeypatch, profile):
    def boom(*args, **kwargs):
        raise AssertionError("workflow must not start")

    monkeypatch.setattr("main.execute_purple_workflow", boom)
    with TestClient(
        create_app(PurpleBoxConfig(meta_api_key="k")), base_url="http://localhost"
    ) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                f"ws://localhost/ws/combat/node_query_sink?profile={profile}",
                headers={"origin": "http://localhost"},
            ):
                pytest.fail("Unknown profile was accepted")
    assert error.value.code == 1008
