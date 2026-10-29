# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import json

import httpx
import pytest

from modules.core.agents import AgentError, MetaMuseClient
from modules.core.config import PurpleBoxConfig
from modules.core.pricing import CallUsage, ScanUsage, estimate_cost, usage_from_response

FINDING = {
    "vulnerability_class": "type confusion",
    "sink_location": "app.js",
    "analysis_summary": "summary",
    "verification_script_python": "import sys\nsys.exit(0)\n",
}


def test_estimate_uses_cached_input_and_reasoning_is_output():
    # 1M uncached input + 1M output on Spark: 1.25 + 4.25
    assert estimate_cost("muse-spark-1.3", 1_000_000, 0, 1_000_000) == 5.5
    # Cached tokens are billed at the cached rate, never twice.
    assert estimate_cost("muse-wonder-1.0", 1_000_000, 1_000_000, 0) == 0.2
    # Cached cannot exceed prompt.
    assert estimate_cost("muse-wonder-1.0", 10, 999, 0) == estimate_cost(
        "muse-wonder-1.0", 10, 10, 0
    )
    assert estimate_cost("meta-models/muse-spark-open-1026", 100, 0, 100) is None


def test_real_response_shape_from_meta_api():
    # Shape captured from a real api.meta.ai muse-spark-1.3 response on 2026-10-28.
    body = {
        "usage": {
            "completion_tokens": 5064,
            "prompt_tokens": 772,
            "total_tokens": 5836,
            "completion_tokens_details": {"reasoning_tokens": 3983},
            "prompt_tokens_details": {"cached_tokens": 753},
        }
    }
    call = usage_from_response("red", "muse-spark-1.3", body, 12.345)
    assert (call.prompt_tokens, call.cached_tokens) == (772, 753)
    assert (call.completion_tokens, call.reasoning_tokens) == (5064, 3983)
    assert call.seconds == 12.35
    assert call.cost_usd == round((753 * 0.15 + 19 * 1.25 + 5064 * 4.25) / 1e6, 6)


@pytest.mark.parametrize("body", [{}, {"usage": None}, {"usage": {"prompt_tokens": -5}}, []])
def test_missing_or_bad_usage_counts_as_zero(body):
    call = usage_from_response("red", "muse-spark-1.3", body, 1)
    assert call.prompt_tokens == call.completion_tokens == 0
    assert call.cost_usd == 0


def test_total_cost_unknown_if_any_call_unpriced():
    priced = CallUsage(role="red", model="m", cost_usd=0.01)
    unpriced = CallUsage(role="blue", model="x", cost_usd=None)
    assert ScanUsage(calls=[priced, priced]).cost_usd == 0.02
    assert ScanUsage(calls=[priced, unpriced]).cost_usd is None
    assert ScanUsage().cost_usd is None


async def test_client_records_usage_even_when_response_json_is_rejected():
    replies = iter(
        [
            {
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(FINDING)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
            {
                "choices": [{"finish_reason": "stop", "message": {"content": "not json"}}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 70},
            },
        ]
    )
    client = MetaMuseClient(
        PurpleBoxConfig(meta_api_key="k"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=next(replies))),
    )
    await client.run_red_team_analysis("app.js", "src")
    with pytest.raises(AgentError):
        await client.run_red_team_analysis("app.js", "src")
    await client.aclose()
    assert [(c.role, c.prompt_tokens) for c in client.usage] == [("red", 100), ("red", 200)]
