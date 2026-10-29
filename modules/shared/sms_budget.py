# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Shared payload budgeting: JSON size checks against explicit context budgets.

deep_scan, demo_gen, and project_workflow each re-implemented "dump, measure,
raise when over budget". One home with three entry points. Leaf (stdlib only).
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_FLOOR_BYTES = 16_384


def payload_size_bytes(payload: Any) -> int:
    """Measure a payload's JSON-encoded byte size."""
    return len(json.dumps(payload).encode("utf-8"))


def check_payload_budget(payload: Any, max_payload_bytes: int, context: str) -> int:
    """Return size; raise ValueError naming context when over budget."""
    size = payload_size_bytes(payload)
    if size > max_payload_bytes:
        raise ValueError(f"{context} payload exceeds the context budget.")
    return size


def resolve_payload_budget(
    default: int,
    context_budget: int,
    *,
    floor: int = DEFAULT_FLOOR_BYTES,
    factor: int = 4,
) -> int:
    """Project payload budget: bounded by snapshot-derived context allowance."""
    return min(default, max(floor, context_budget * factor))
