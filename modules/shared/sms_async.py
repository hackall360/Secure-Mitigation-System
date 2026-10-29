# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Shared async + emit plumbing: the leaf every workflow imports.

`blocking` joins in-flight Docker/thread work before propagating
cancellation to cleanup. `make_log` wraps any emit callable so logging (or a
closed UI socket) can never break resource cleanup. No imports from this
repo: leaf module, zero cycle risk.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

Emit = Callable[[str, str], Awaitable[None]]


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


def make_log(emit: Emit) -> Emit:
    """Wrap emit so logging failures never break cleanup or scans."""

    async def log(team: str, message: str) -> None:
        try:
            await emit(team, message)
        except Exception:
            pass

    return log
