# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Conservative fixture-level guards, not a proof of program equivalence."""

import configparser
import difflib

from modules.core.registry import Target


class PatchRejected(ValueError):
    """The patch exceeds the scaffold's supported edit surface.

    Each rejection carries a machine-readable ``guard_id`` (which guard
    fired) plus a short ``trigger`` (which protected line/setting tripped
    it) so reviewers can audit why a patch was refused. Neither field ever
    carries probe bytes (LAW 4): triggers name original-source lines or
    config keys only.
    """

    def __init__(
        self, message: str, *, guard_id: str = "patch_rejected", trigger: str = ""
    ) -> None:
        super().__init__(message)
        self.guard_id = guard_id
        self.trigger = trigger[:500]


def guard_rationale(exc: PatchRejected) -> dict[str, str]:
    """Export a rejected fixture patch as structured review evidence.

    Returns ``guard_id`` (which guard fired), ``reason`` (the human message),
    and ``trigger`` (the protected line/setting). Contains no probe bytes.
    """
    return {
        "guard_id": exc.guard_id,
        "reason": str(exc),
        "trigger": exc.trigger,
    }


def validate_patch(target: Target, original: str, patched: str) -> str:
    if not patched.strip() or original == patched:
        raise PatchRejected(
            "Patch is empty or unchanged.",
            guard_id="empty_or_unchanged",
        )
    if len(patched.encode()) > 65_536 or "\x00" in patched or patched.lstrip().startswith("```"):
        raise PatchRejected(
            "Patch is not a complete supported source file.",
            guard_id="malformed_patch",
        )
    for notice in original.splitlines():
        if (
            "Required Notice:" in notice or "polyformproject.org/licenses/" in notice
        ) and notice not in patched:
            raise PatchRejected(
                "Patch removed a required license notice.",
                guard_id="license_notice_removed",
                trigger=notice.strip(),
            )

    before, after = original.splitlines(), patched.splitlines()
    changes = sum(
        max(i2 - i1, j2 - j1)
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=before, b=after).get_opcodes()
        if op != "equal"
    )
    if changes > 60:
        raise PatchRejected(
            "Patch exceeds the 60-line surgical edit budget.",
            guard_id="edit_budget_exceeded",
            trigger=f"{changes} changed lines over 60-line budget",
        )

    if target.key == "mysql_insecure_conf":
        old, new = configparser.ConfigParser(), configparser.ConfigParser()
        try:
            old.read_string(original)
            new.read_string(patched)
        except configparser.Error as exc:
            raise PatchRejected(
                "Invalid configuration syntax.",
                guard_id="config_syntax_invalid",
            ) from exc
        expected = {
            "bind-address": "127.0.0.1",
            "local-infile": "0",
            "secure-file-priv": "/var/lib/mysql-files",
        }
        for key, value in expected.items():
            if new.get("mysqld", key, fallback="").strip("\"'") != value:
                raise PatchRejected(
                    f"Configuration must harden {key} to {value}.",
                    guard_id="config_not_hardened",
                    trigger=f"{key} must be {value}",
                )
            old.set("mysqld", key, value)
            new.set("mysqld", key, value)
        if {s: dict(old[s]) for s in old} != {s: dict(new[s]) for s in new}:
            raise PatchRejected(
                "Configuration patch changed unrelated settings.",
                guard_id="config_unrelated_changed",
            )
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
                raise PatchRejected(
                    "Patch removed, reordered, or rewrote a protected code line.",
                    guard_id="protected_line_removed",
                    trigger=stripped,
                )
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{target.key}/{target.filename}",
            tofile=f"b/{target.key}/{target.filename}",
        )
    )
