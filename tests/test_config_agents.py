# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import json
from dataclasses import replace

import httpx
import pytest

from agents import AgentError, MetaMuseClient, RedTeamFinding
from config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key

FINDING = {
    "vulnerability_class": "input validation",
    "sink_location": "app.js:15",
    "analysis_summary": "An unexpected type reaches an expression.",
    "verification_script_python": "import sys\nsys.exit(0)\n",
}


def test_key_only_required_for_inference(monkeypatch):
    monkeypatch.delenv("META_MUSE_API_KEY", raising=False)
    settings = load_config()
    assert settings.meta_base_url == "https://api.meta.ai/v1"
    with pytest.raises(ConfigurationError, match="META_MUSE_API_KEY"):
        require_api_key(settings)
    assert "secret-value" not in repr(PurpleBoxConfig(meta_api_key="secret-value"))


@pytest.mark.parametrize(
    "url",
    [
        "[https://api.meta.ai/v1](https://api.meta.ai/v1)",
        "http://api.meta.ai/v1",
        "https://api.openai.com/v1",
        "https://api.meta.ai.evil.example/v1",
        "https://key:secret@api.meta.ai/v1",
        "https://api.meta.ai/v1?key=secret",
        "https://api.meta.ai:8080/v1",
    ],
)
def test_endpoint_lock(url):
    with pytest.raises(ConfigurationError):
        replace(PurpleBoxConfig(), meta_base_url=url).validate()


@pytest.mark.parametrize("model", ["gpt-4", "claude-sonnet", "muse-code", "muse-spark;evil"])
def test_model_lock(model):
    with pytest.raises(ConfigurationError):
        replace(PurpleBoxConfig(), blue_team_model=model).validate()


async def test_muse_request_uses_exact_configured_endpoint_and_strict_schema():
    requests = []

    def handle(request):
        requests.append(request)
        assert str(request.url) == "https://api.meta.ai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer unit-test-key"
        body = json.loads(request.content)
        assert body["model"] == "muse-spark-1.3"
        assert json.loads(body["messages"][1]["content"])["source"] == "test source"
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(FINDING)}}]
            },
        )

    client = MetaMuseClient(
        PurpleBoxConfig(meta_api_key="unit-test-key"), transport=httpx.MockTransport(handle)
    )
    try:
        result = await client.run_red_team_analysis("app.js", "test source")
        assert isinstance(result, RedTeamFinding)
        assert len(requests) == 1
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        "{}",
        json.dumps({**FINDING, "extra": True}),
        json.dumps({**FINDING, "sink_location": 123}),
    ],
)
async def test_schema_failure_is_not_a_finding(content):
    client = MetaMuseClient(
        PurpleBoxConfig(meta_api_key="unit-test-key"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": content}}]}
            ),
        ),
    )
    try:
        with pytest.raises(AgentError, match="invalid JSON"):
            await client.run_red_team_analysis("app.js", "source")
    finally:
        await client.aclose()


@pytest.mark.parametrize("status", [302, 401, 429, 500])
async def test_api_failure_has_no_fallback_and_does_not_expose_body(status):
    called = []

    def handle(request):
        called.append(request)
        return httpx.Response(
            status, text="private provider detail", headers={"location": "https://example.com"}
        )

    client = MetaMuseClient(
        PurpleBoxConfig(meta_api_key="unit-test-key"), transport=httpx.MockTransport(handle)
    )
    try:
        with pytest.raises(AgentError) as error:
            await client.run_red_team_analysis("app.js", "source")
        assert "private provider detail" not in str(error.value)
        assert len(called) == 1
    finally:
        await client.aclose()
