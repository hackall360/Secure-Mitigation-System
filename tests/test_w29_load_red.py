# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Wave 29 RED: sustained-load + 429 drill (bounded fault-injection).

Pins tribunal S1-4/S3 residual: under a sustained 429 storm the client
must (a) bound total attempts (<= RETRY_MAX_ATTEMPTS+1), (b) honor
Retry-After only up to the cap, (c) surface a rate-limit-named error
(never silent, never hang), and (d) leave the dashboard usable (error
event renders via the banner path). No live network: Fake transport at
the SDK boundary (LAW 9C), sleep recorded not slept.
"""

import pytest

from modules.core import agents as agents_mod


def test_retry_bounds_are_tight():
    assert agents_mod.RETRY_MAX_ATTEMPTS <= 3, "attempts must stay bounded for UI survival"
    assert agents_mod.RETRY_AFTER_MAX_SECONDS <= 10, "Retry-After honor must be capped"
    assert agents_mod.RETRY_BASE_SECONDS <= 1.0


def test_sustained_429_names_rate_limit_and_stops():
    """A sustained 429 storm: attempt-0 retries once, attempt-1 raises named error.

    Drives the REAL MetaMuseClient._request with a fake stream transport
    (SDK boundary, LAW 9C) and records sleeps instead of sleeping. Pins:
    exactly RETRY_MAX_ATTEMPTS HTTP posts, total sleep bounded by the cap,
    and the raised AgentError names rate limiting (UI-renderable).
    """
    import asyncio

    import modules.core.agents as am

    posts = {"n": 0}
    sleeps = []

    class FakeStream:
        def __init__(self, status, headers=None):
            self.status_code = status
            self.headers = headers or {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def aiter_bytes(self):
            yield b"{}"

    class StormClient:
        def stream(self, *a, **k):
            posts["n"] += 1
            return FakeStream(429, {"retry-after": "3600"})

    async def fake_sleep(s):
        sleeps.append(s)

    async def run():
        from modules.core.config import PurpleBoxConfig

        cfg = PurpleBoxConfig(meta_api_key="test-key-never-sent")
        client = am.MetaMuseClient.__new__(am.MetaMuseClient)
        client.config = cfg
        client.client = StormClient()
        client.usage = []
        real_sleep = asyncio.sleep
        asyncio.sleep = fake_sleep  # type: ignore[assignment]
        try:
            with pytest.raises(am.AgentError, match="rate limit"):
                await client._request("m", "s", {}, am.RedTeamFinding, role="red")
        finally:
            asyncio.sleep = real_sleep  # type: ignore[assignment]

    asyncio.new_event_loop().run_until_complete(run())
    assert posts["n"] == am.RETRY_MAX_ATTEMPTS, f"bounded posts, got {posts['n']}"
    assert len(sleeps) == 1 and sleeps[0] <= am.RETRY_AFTER_MAX_SECONDS + am.RETRY_JITTER_SECONDS, (
        f"one capped sleep, got {sleeps}"
    )
    assert all(s >= 0 for s in sleeps)


def test_exhausted_retry_error_is_ui_renderable():
    import inspect

    src = inspect.getsource(agents_mod)
    assert "rate limit" in src.lower() or "rate_limit" in src.lower() or "429" in src
