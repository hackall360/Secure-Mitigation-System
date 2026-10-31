# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Host-side summarizer for in-sandbox binary static profiles (Subsystem D).

binary_static_profile() runs file/strings/readelf INSIDE the air-gapped
container; this module only interprets the returned TEXT on the host.
It never executes binaries, never touches the sandbox, and never raises:
unparseable profiles yield an empty-signals summary so the red passes
still run (fail-open summary, fail-closed verdict — Docker still decides).
"""

from __future__ import annotations

import re

_INTERESTING_SYSCALLS = (
    "system",
    "execve",
    "popen",
    "strcpy",
    "strcat",
    "sprintf",
    "gets",
    "memcpy",
    "mmap",
    "socket",
    "connect",
    "ptrace",
    "chmod",
)

_INTERESTING_KEYWORDS = (
    "password",
    "secret",
    "passwd",
    "/bin/sh",
    "/bin/bash",
    "LD_PRELOAD",
    "backdoor",
    "shell",
)


def summarize_profile(profile_text: str) -> dict:
    """Reduce raw profile text to a JSON-serializable telemetry summary."""
    if not profile_text or not isinstance(profile_text, str):
        return {"format": "unknown", "signals": [], "notes": "empty profile"}
    lowered = profile_text.lower()
    if "elf" in lowered:
        binary_format = "elf"
    elif "macho" in lowered or "mach-o" in lowered:
        binary_format = "macho"
    elif "pe32" in lowered or "mz" in lowered:
        binary_format = "pe"
    else:
        binary_format = "unknown"
    signals: list[str] = []
    for syscall in _INTERESTING_SYSCALLS:
        if re.search(r"\b" + re.escape(syscall) + r"\b", lowered):
            signals.append(f"imports:{syscall}")
    for keyword in _INTERESTING_KEYWORDS:
        if keyword.lower() in lowered:
            signals.append(f"string:{keyword}")
    notes = "static profile parsed on host from sandbox output"
    if not signals:
        notes = "no known-dangerous imports or strings observed; treat as unclassified"
    return {"format": binary_format, "signals": sorted(set(signals)), "notes": notes}
