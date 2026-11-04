# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Slice E live-feedback progress: additive per-phase emits + rate-limited chatter.

Leaf helper: every function here is pure formatting or a small stateful
counter. No model calls, no Docker, no secrets. Workflows import this to
emit ``[phase ...]`` progress lines (same tag shape the v3 console parser
pins in tests/test_v3_live_console.py) and persona-voice chatter while
awaiting model calls, rate-limited so long runs cannot flood the feed.

LAW 4: lines carry counts, indices, and exit codes only — never probe
source, payloads, file contents, or URLs.
"""

from __future__ import annotations

# Hard ceiling: chatter is minor summaries only. Even a 48-batch run with
# digest levels emits at most this many persona lines; the rest is silent
# progress (counts only). Keeps the 120-line comms feed turning over, never
# flooding it. UI contract pinned in tests/test_slice_e_feedback_red.py.
CHATTER_MAX_PER_RUN = 8

# Emit one await-gap chatter line every N model calls at most, and never more
# than CHATTER_MAX_PER_RUN per run. Deterministic: callers pass the 1-based
# model-call index; lines fire on multiples of this interval while budget lasts.
CHATTER_EVERY_N_BATCHES = 4


def red_batch_progress(batch_index: int, batch_count: int) -> str:
    """Per-batch red progress: ``[phase red review] batch i/N``."""
    return f"[phase red review] batch {batch_index}/{batch_count}"


def blue_attempt_progress(attempt: int, attempts: int) -> str:
    """Per-attempt blue progress: ``[phase blue patch] attempt i/N``."""
    return f"[phase blue patch] attempt {attempt}/{attempts}"


def verify_start_progress(label: str) -> str:
    """Sandbox verify open bracket: ``[phase verify] start (<label>)``."""
    return f"[phase verify] start ({label})"


def verify_done_progress(label: str) -> str:
    """Sandbox verify close bracket: ``[phase verify] done (<label>)``.

    Deliberately no exit code: the workflow already emits the exit-code line
    right after, and the v3 interpreter keys findings/patches on exit
    entities — a second code-shaped token would double-count. The done line
    is a pure progress bracket.
    """
    return f"[phase verify] done ({label})"


class ChatterBudget:
    """Rate limiter for await-gap persona chatter: interval + hard cap.

    Pure counter, no I/O. ``should_chatter(call_index)`` returns True at
    most every ``every`` calls and at most ``cap`` times total. Deterministic
    for a given call sequence, so tests can pin exact behavior.
    """

    def __init__(self, *, every: int = CHATTER_EVERY_N_BATCHES, cap: int = CHATTER_MAX_PER_RUN):
        self.every = max(1, int(every))
        self.cap = max(0, int(cap))
        self.spent = 0

    def should_chatter(self, call_index: int) -> bool:
        """True when this 1-based model-call index earns a chatter line."""
        if self.spent >= self.cap:
            return False
        if call_index < 1 or call_index % self.every != 0:
            return False
        self.spent += 1
        return True

    @property
    def remaining(self) -> int:
        return max(0, self.cap - self.spent)


async def verify_traced(log, stage: str, func, *args, **kwargs):
    """Bracket one sandbox verify with start/done progress lines.

    ``func(*args, **kwargs)`` is awaited to perform the verify (usually
    ``blocking(...)``). Args are evaluated eagerly at the call site, so loop
    variables (pass ids, findings) can never leak across iterations — no
    closures. Start/done lines carry the label only — no exit codes, so the
    v3 interpreter's exit entity (which keys findings on ``boundary check
    exited N`` / ``exit N``) never double-counts. The real exit-code line
    the workflow already emits stays the single source of truth for verdicts.

    The bracket name is ``stage`` (not ``label``) so sandbox calls can keep
    their own keyword-only ``label=...`` argument without collision.
    """
    await log("system", verify_start_progress(stage))
    try:
        return await func(*args, **kwargs)
    finally:
        await log("system", verify_done_progress(stage))
