# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): binary static signals miss the modern RE surface.

summarize_profile hunts 13 imports + 8 keywords. Missing classes a
reverse engineer checks first:

- FORMAT RIGOR: no section-header parsing (readelf -S), no import-table
  listing (readelf --dyn-syms / objdump -T), no entropy note for packed
  binaries. Red gets raw profile text but the SUMMARY (what grounds the
  compressed context) carries only format+signals.
- MEMORY-UNSAFE: no scanf/strncpy-misuse/getenv/setuid/curl_/ssl_ signals;
  no format-string (%n/%s in strings) signal; no stack-protector/NX/PIE
  mitigation note from readelf -l (GNU_STACK/GNU_RELRO).
- C2/EXFIL: no dns/getaddrinfo/curl/wget/http/user-agent/base64 signals.
- CRYPTO: no crypt/md5/sha/des/aes signals (weak-hash triage for the new
  coverage pass).

Parity contract: the signal lists cover at least: scanf, getenv, setuid,
curl, ssl_, dns/getaddrinfo, http, base64, crypt, md5, format-string %n,
plus readelf-derived mitigation notes (NX/RELRO/stack canary when the
profile text contains them). Signals stay LOW-RISK strings (names only,
never payloads).
"""

from __future__ import annotations


def test_signal_lists_cover_modern_surface():
    from modules.services import binary_telemetry as bt

    syscalls = {s.lower() for s in bt._INTERESTING_SYSCALLS}
    keywords = {k.lower() for k in bt._INTERESTING_KEYWORDS}
    universe = syscalls | keywords
    for must in (
        "scanf",
        "getenv",
        "setuid",
        "curl",
        "getaddrinfo",
        "base64",
        "crypt",
        "md5",
    ):
        assert must in universe, f"signal list must cover {must}"
    assert "%n" in keywords or "format" in " ".join(keywords), "need a format-string signal"


def test_profile_summary_notes_mitigations():
    from modules.services.binary_telemetry import summarize_profile

    profile = (
        "ELF 64-bit LSB executable, x86-64\n"
        "GNU_STACK RWE / GNU_RELRO full\n"
        "Stack: __stack_chk_fail\n"
        "UND curl_easy_init\n"
        "password= hunter2\n"
    )
    summary = summarize_profile(profile)
    assert summary["format"] == "elf"
    assert any("curl" in s for s in summary["signals"]), summary
    text = " ".join(summary["signals"]) + summary.get("notes", "")
    assert "NX" in text or "RELRO" in text or "canary" in text, (
        "summary must note binary mitigations when the profile contains them"
    )
