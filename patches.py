# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Conservative fixture-level guards, not a proof of program equivalence."""

import configparser
import difflib

from registry import Target


class PatchRejected(ValueError):
    """The patch exceeds the scaffold's supported edit surface."""


def validate_patch(target: Target, original: str, patched: str) -> str:
    if not patched.strip() or original == patched:
        raise PatchRejected("Patch is empty or unchanged.")
    if len(patched.encode()) > 65_536 or "\x00" in patched or patched.lstrip().startswith("```"):
        raise PatchRejected("Patch is not a complete supported source file.")
    for notice in original.splitlines():
        if (
            "Required Notice:" in notice or "polyformproject.org/licenses/" in notice
        ) and notice not in patched:
            raise PatchRejected("Patch removed a required license notice.")

    before, after = original.splitlines(), patched.splitlines()
    changes = sum(
        max(i2 - i1, j2 - j1)
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=before, b=after).get_opcodes()
        if op != "equal"
    )
    if changes > 60:
        raise PatchRejected("Patch exceeds the 60-line surgical edit budget.")

    if target.key == "mysql_insecure_conf":
        old, new = configparser.ConfigParser(), configparser.ConfigParser()
        try:
            old.read_string(original)
            new.read_string(patched)
        except configparser.Error as exc:
            raise PatchRejected("Invalid configuration syntax.") from exc
        expected = {
            "bind-address": "127.0.0.1",
            "local-infile": "0",
            "secure-file-priv": "/var/lib/mysql-files",
        }
        for key, value in expected.items():
            if new.get("mysqld", key, fallback="").strip("\"'") != value:
                raise PatchRejected(f"Configuration must harden {key} to {value}.")
            old.set("mysqld", key, value)
            new.set("mysqld", key, value)
        if {s: dict(old[s]) for s in old} != {s: dict(new[s]) for s in new}:
            raise PatchRejected("Configuration patch changed unrelated settings.")
    else:
        # Restrict removals/replacements; full syntax and normal behavior are checked in Docker.
        remaining = iter(line.strip() for line in after)
        for line in before:
            stripped = line.strip()
            if (
                not stripped
                or stripped.startswith(("//", "#"))
                or stripped.startswith(target.mutable_prefixes)
            ):
                continue
            if not any(candidate == stripped for candidate in remaining):
                raise PatchRejected("Patch removed, reordered, or rewrote a protected code line.")
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{target.key}/{target.filename}",
            tofile=f"b/{target.key}/{target.filename}",
        )
    )
