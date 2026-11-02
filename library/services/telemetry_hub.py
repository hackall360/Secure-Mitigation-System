# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""WebSocket telemetry hub: connect-time snapshot + batched live deltas (WebUI v3).

Subsystem C of the closed-loop WebUI v3 migration. Two pieces:

1. :func:`build_snapshot` — the total-state frame a new WebSocket connection
   receives immediately on accept, so a v3 page that loads mid-run (refresh,
   setup → console navigation) hydrates the WebGL map + HUD counters + chips
   without waiting for the next stream line. Shape::

       {"type": "snapshot", "nodes": [...], "hud": {...}, "chips": {...}, "ts": ...}

   ``hud`` keys mirror the v3 scoreboard IDs (``sc-nodes`` etc. minus the
   prefix): ``nodes``, ``msgs``, ``findings``, ``patches``, ``verified``.
   ``chips`` mirrors ``chip-server`` / ``chip-docker`` / ``chip-key`` states.
   ``nodes`` is the known fixture roster (v3 ``onGraph`` merges it).

2. :class:`TelemetryBatcher` — 100–250 ms coalescing window for rapid
   ``telemetry``-team events (vault-indexing bursts at 48x). The async Docker
   execution loop stays unblocked: callers ``await push(...)`` inline — push
   never blocks on I/O, it only schedules a short flush. Only low-signal
   telemetry ticks are batched; red/blue verdict lines bypass the batcher and
   send immediately (real time is sacred — v3 AGENTS.md rule 3).

LAW 4: snapshot carries roster/counts only, never probe source or payloads.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from library.shared.sms_observability import get_aspect
from library.shared.sms_observability import record_metric as obs_record_metric

_TELEMETRY_ASPECT = get_aspect("services.telemetry")

# Coalescing window bounds (seconds). Spec: batch at 100–250 ms.
MIN_WINDOW_S = 0.10
MAX_WINDOW_S = 0.25

# HUD keys, mirroring v3 console.html scoreboard IDs sc-nodes/sc-msgs/....
HUD_KEYS = ("nodes", "msgs", "findings", "patches", "verified")


def build_snapshot(
    *,
    targets: dict[str, Any] | None = None,
    busy: bool = False,
    docker_state: str = "unavailable",
    key_ok: bool = False,
) -> dict[str, Any]:
    """Build the connect-time state snapshot frame (pure, no I/O)."""
    roster = sorted((targets or {}).keys())
    return {
        "type": "snapshot",
        "nodes": [{"id": key, "label": key, "kind": "target", "parent": "core"} for key in roster],
        "hud": {key: 0 for key in HUD_KEYS},
        "chips": {
            "server": "ok" if not busy else "busy",
            "docker": docker_state,
            "key": "ok" if key_ok else "pending",
        },
        "busy": bool(busy),
        "ts": time.time(),
    }


class TelemetryBatcher:
    """Coalesce rapid telemetry events into bounded snapshot-delta frames.

    ``sink`` is called with one collapsed frame per window::

        {"type": "telemetry_batch", "count": N, "events": [...], "ts": ...}

    Only the last ``max_events`` lines are kept per frame so a 48x burst
    cannot grow memory or stall the browser render thread. ``push`` returns
    quickly (schedules a flush, never performs I/O inline); ``flush``
    delivers immediately. Both are safe to call from the running loop.
    """

    def __init__(
        self,
        sink: Callable[[dict[str, Any]], Awaitable[None] | None],
        window_ms: int | float = 150,
        max_events: int = 50,
    ) -> None:
        window_s = float(window_ms) / 1000.0
        self._window = min(MAX_WINDOW_S, max(MIN_WINDOW_S, window_s))
        self._max_events = max(1, int(max_events))
        self._sink = sink
        self._pending: list[dict[str, Any]] = []
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def window_s(self) -> float:
        return self._window

    async def push(self, event: dict[str, Any]) -> None:
        async with self._lock:
            self._pending.append(dict(event))
            if len(self._pending) > self._max_events:
                self._pending = self._pending[-self._max_events :]
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._delayed_flush())

    async def _delayed_flush(self) -> None:
        await asyncio.sleep(self._window)
        await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            pending, self._pending = self._pending, []
        if not pending:
            return
        # LAW 4: counts only — never event payloads, team strings are
        # the fixed "telemetry" label emitted below, not caller data.
        batch_size = len(pending)
        coalesced = max(0, batch_size - len(pending[-self._max_events :]))
        obs_record_metric(_TELEMETRY_ASPECT, "telemetry_batch.size", batch_size, unit="count")
        obs_record_metric(_TELEMETRY_ASPECT, "telemetry_batch.coalesced", coalesced, unit="count")
        frame = {
            "type": "telemetry_batch",
            "team": "telemetry",
            "count": batch_size,
            "events": pending[-self._max_events :],
            "ts": time.time(),
        }
        outcome = self._sink(frame)
        if asyncio.iscoroutine(outcome):
            await outcome
