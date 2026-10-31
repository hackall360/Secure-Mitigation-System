# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first 429-throttle UI contract (tribunal S3-7, wave w13).

A sustained provider throttle must keep the UI alive with explicit errors:
the Muse transport stays bounded (capped Retry-After, capped attempts), a
throttled sweep reports error/rejected with rate-limit wording (never
verified, never silent), and WS log/result frames render that error text
via the writeLine path.

Docs note: retry discipline already existed in modules/core/agents.py
(TRANSIENT_STATUS_CODES / RETRY_AFTER_MAX_SECONDS / RETRY_MAX_ATTEMPTS);
the gap this wave pins is the user-facing wording after an exhausted
retry, plus the UI contract that the error text actually renders.
"""

import pytest

from tests.helpers import TEST_CONFIG


async def test_sustained_429_raises_bounded_agent_error(monkeypatch):
    """Sustained 429s (Retry-After past the cap) fail after bounded attempts."""
    import asyncio

    import httpx

    from modules.core.agents import (
        RETRY_AFTER_MAX_SECONDS,
        RETRY_JITTER_SECONDS,
        RETRY_MAX_ATTEMPTS,
        AgentError,
        MetaMuseClient,
    )

    attempts = 0
    slept: list[float] = []

    def always_throttled(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, headers={"retry-after": "3600"}, json={"error": "slow down"})

    async def record_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)
    client = MetaMuseClient(TEST_CONFIG, transport=httpx.MockTransport(always_throttled))
    try:
        with pytest.raises(AgentError):
            await client.run_red_team_analysis("app.js", "source")
    finally:
        await client.aclose()
    assert attempts == RETRY_MAX_ATTEMPTS
    assert len(slept) == RETRY_MAX_ATTEMPTS - 1
    assert sum(slept) <= (RETRY_AFTER_MAX_SECONDS + RETRY_JITTER_SECONDS) * len(slept)
    assert sum(slept) < 3600.0


def test_retry_after_honored_only_up_to_cap():
    """Retry-After 3600 moves the delay up to, but never past, the cap."""
    from modules.core.agents import (
        RETRY_AFTER_MAX_SECONDS,
        RETRY_JITTER_SECONDS,
        _parse_retry_after,
        _retry_delay_seconds,
    )

    assert _parse_retry_after("3600") == 3600.0
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("not-a-number") is None
    capped = _retry_delay_seconds(0, 3600.0)
    assert RETRY_AFTER_MAX_SECONDS <= capped <= RETRY_AFTER_MAX_SECONDS + RETRY_JITTER_SECONDS
    small = _retry_delay_seconds(0, 1.0)
    assert 1.0 <= small <= 1.0 + RETRY_JITTER_SECONDS


async def test_sweep_with_throttled_muse_reports_rate_limit_error(monkeypatch):
    """A throttled sweep ends error/rejected, names the rate limit, stays loud."""
    import asyncio

    import httpx

    from modules.core.agents import MetaMuseClient
    from modules.workflows.sweep import execute_sweep_scan
    from tests.helpers import FakeFixtureSandbox

    def always_throttled(request):
        return httpx.Response(429, headers={"retry-after": "3600"}, json={"error": "slow down"})

    async def no_sleep(delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    events: list[tuple[str, str]] = []

    async def emit(team, message):
        events.append((team, message))

    transport = httpx.MockTransport(always_throttled)
    sandbox = FakeFixtureSandbox([0])
    result = await execute_sweep_scan(
        "node_query_sink",
        emit,
        config=TEST_CONFIG,
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: MetaMuseClient(settings, transport=transport),
    )
    assert result.status in ("error", "rejected")
    assert result.status != "verified"
    assert result.verified is False
    assert "rate limit" in result.message.lower().replace("-", " ")
    assert events, "throttled sweep must stay loud: no silent UI"
    assert "rate limit" in " | ".join(m for _, m in events).lower().replace("-", " ")


def test_ui_renders_throttle_events_with_explicit_error():
    """Text-level UI contract: log frames reach writeLine; errors get labels."""
    from pathlib import Path

    app_js = Path(__file__).resolve().parents[1] / "static" / "app.js"
    source = app_js.read_text(encoding="utf-8")
    # WS log frames reach the timeline through writeLine ...
    assert "writeLine(payload.team, payload.msg)" in source
    # ... every team (unknown included) lands in the system timeline, never dropped ...
    assert "append(logs.system" in source
    # ... the verdict card shows the message text explicitly ...
    assert "el('result-message').textContent = payload.message" in source
    # ... with an explicit could-not-complete label for error status ...
    assert "error: 'Scan could not complete'" in source
    # ... and refusal/busy states keep their specific next step.
    assert "Scan refused: another scan holds the server lock" in source
