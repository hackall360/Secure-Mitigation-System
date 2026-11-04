# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Shared async + emit plumbing: the leaf every workflow imports.

`blocking` joins in-flight Docker/thread work before propagating
cancellation to cleanup. `make_log` wraps any emit callable so logging (or a
closed UI socket) can never break resource cleanup — errors are swallowed
and each emit is bounded by EMIT_TIMEOUT_S so a backpressured socket cannot
serialize the scan tail or cleanup behind it. No imports from this
repo: leaf module, zero cycle risk.
"""

from __future__ import annotations

__version__ = "0.1.0"

import asyncio
from collections.abc import Awaitable, Callable

Emit = Callable[[str, str], Awaitable[None]]

# Slice E: per-emit latency bound. A backpressured WS consumer must never
# serialize the scan tail (or cleanup) behind one slow frame. Kept well under
# the model-retry ladder (10 s+) so slow sockets degrade to dropped frames,
# never slow verdicts. LAW 10I: every I/O call gets a timeout.
EMIT_TIMEOUT_S = 0.5


async def blocking(function, *args, **kwargs):
    """Join in-flight Docker operations before propagating cancellation to cleanup."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        except Exception:
            pass
        raise


def make_log(emit: Emit, *, timeout_s: float = EMIT_TIMEOUT_S) -> Emit:
    """Wrap emit so logging failures AND slow consumers never break cleanup.

    Errors are swallowed (closed socket) and each emit is bounded by
    ``timeout_s`` (backpressured socket): on timeout the frame is dropped and
    the scan continues. LAW 4 cleanup invariant holds under both.
    """

    async def log(team: str, message: str) -> None:
        try:
            await asyncio.wait_for(emit(team, message), timeout=timeout_s)
        except Exception:
            pass

    return log
