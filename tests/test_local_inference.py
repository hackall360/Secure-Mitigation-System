# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Explicit local inference is loopback-only and never falls back to a hosted service."""

import json
from dataclasses import replace

import httpx
import pytest

from modules.core.agents import MetaMuseClient
from modules.core.config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key


@pytest.mark.parametrize("endpoint", ["http://127.0.0.1:8081/v1", "http://[::1]:8081/v1"])
def test_local_inference_requires_no_key(endpoint):
    config = PurpleBoxConfig(inference_mode="local", meta_base_url=endpoint)
    require_api_key(config)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://localhost:8081/v1",
        "http://127.0.0.2:8081/v1",
        "https://api.meta.ai/v1",
        "http://0.0.0.0:8081/v1",
        "http://user:secret@127.0.0.1:8081/v1",
        "http://127.0.0.1:8081/v1?key=secret",
    ],
)
def test_local_mode_cannot_contact_remote_or_ambiguous_hosts(endpoint):
    with pytest.raises(ConfigurationError):
        PurpleBoxConfig(inference_mode="local", meta_base_url=endpoint).validate()


def test_local_endpoint_is_not_implicitly_enabled():
    with pytest.raises(ConfigurationError):
        PurpleBoxConfig(meta_base_url="http://127.0.0.1:8081/v1").validate()
    with pytest.raises(ConfigurationError):
        replace(PurpleBoxConfig(), inference_mode="other").validate()


def test_local_environment_opt_in(monkeypatch):
    monkeypatch.setenv("PURPLEBOX_INFERENCE_MODE", "local")
    monkeypatch.setenv("META_MUSE_BASE_URL", "http://127.0.0.1:8081/v1")
    monkeypatch.delenv("META_MUSE_API_KEY", raising=False)
    config = load_config()
    assert config.inference_mode == "local"
    require_api_key(config)


async def test_local_muse_transport_has_no_auth_or_hosted_fallback():
    seen = []

    def handle(request):
        seen.append(request)
        assert str(request.url) == "http://127.0.0.1:8081/v1/chat/completions"
        assert "authorization" not in request.headers
        body = json.loads(request.content)
        assert len(body["messages"]) == 2
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "vulnerability_class": "validation",
                                    "sink_location": "app.py:1",
                                    "analysis_summary": "Test finding",
                                    "verification_script_python": "raise SystemExit(0)",
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = MetaMuseClient(
        PurpleBoxConfig(inference_mode="local", meta_base_url="http://127.0.0.1:8081/v1"),
        transport=httpx.MockTransport(handle),
    )
    try:
        await client.run_red_team_analysis("app.py", "test")
    finally:
        await client.aclose()
    assert len(seen) == 1
