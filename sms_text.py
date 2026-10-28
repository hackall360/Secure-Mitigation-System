# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Shared text bounding: char-limit cuts with omission notes, UTF-8 prefixes.

_bounded lived in project_workflow; _take_utf8_prefix in project_agents.
One home, same semantics: never silently truncate — the cut always says how
much was omitted. Leaf module (stdlib only).
"""

from __future__ import annotations


def bounded(text: str, limit: int) -> str:
    """Cut text to limit chars, appending how many were omitted."""
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n[report limit reached; {omitted} characters omitted]"


def take_utf8_prefix(text: str, max_bytes: int) -> tuple[str, str]:
    """Split text on a UTF-8 character boundary without silently dropping bytes."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive.")
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, ""
    end = max_bytes
    while end > 0 and (encoded[end] & 0xC0) == 0x80:
        end -= 1
    if end == 0:
        raise ValueError("max_bytes is too small for the next UTF-8 character.")
    return encoded[:end].decode("utf-8"), encoded[end:].decode("utf-8")
