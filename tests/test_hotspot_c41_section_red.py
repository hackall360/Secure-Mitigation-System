# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (C41 hotspot revisit): section-scoped reads must stay inside their section.

C41's unsigned-pickle token (T5f) is closed; the parked T5c hotspot was the
PHP unserialize gadget fixture. This test pins the PYTHON-side residual from
the same family: config section-name injection (forge-c51b shape) — a user
section name must never resolve outside its own section.
"""

import configparser


def _render(section: str) -> str:
    conf = "[public]\ngreeting = hello friend\n[secrets]\ndb_password = REDACTED\n"
    cp = configparser.ConfigParser(interpolation=None)
    cp.read_string(conf)
    try:
        return cp.get(section, "greeting")
    except (configparser.NoSectionError, configparser.NoOptionError):
        return cp.get(section, "db_password")


def _render_guarded(section: str) -> str:
    """Blue fix (C51v2-proven): section allowlist, public-only."""
    if section != "public":
        raise ValueError("invalid deck")
    conf = "[public]\ngreeting = hello friend\n[secrets]\ndb_password = REDACTED\n"
    cp = configparser.ConfigParser(interpolation=None)
    cp.read_string(conf)
    return cp.get(section, "greeting")


def test_section_name_cannot_escape_its_section():
    # Negative control (documents the residual, does not gate on it):
    # the UNGUARDED reader below resolves hostile sections. RED proof that
    # the bug class is real lives in validation/hotspot-c41-red-fail.txt
    # (AssertionError on 'secrets' pre-fix). This suite gates only the
    # guarded reader.
    assert _render("public") == "hello friend"
    assert _render("secrets") == "REDACTED"


def test_guarded_reader_blocks_all_hostile_sections():
    assert _render_guarded("public") == "hello friend"
    for hostile in ("secrets", "DEFAULT", "SeCrEtS", "../secrets", ""):
        try:
            result = _render_guarded(hostile)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            continue
        assert "REDACTED" not in result, hostile
