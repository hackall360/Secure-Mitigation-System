# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first pins: ingest path-shape tolerance at the snapshot guard.

Gate-2 failure (2026-11-04, insecure-web): ingest stages snapshot keys as
``tree/app/app.py`` (+ ``repo.*`` service keys); red legitimately reports the
repo-relative ``app/app.py``; the guard's exact-set comparison raised
"Red report referenced paths outside the safe snapshot" and killed a
$0.0031/1:55 run before blue. AnyCam dodged this only because its red echoed
the staged ``tree/``-prefixed paths verbatim.

LAW 9 red-first: all pins fail before the normalization lands (mocked
workflow input only, no Docker, no secrets).
"""

import pytest  # noqa: F401

from modules.core.agents import AgentError as ProjectWorkflowError  # noqa: F401
from modules.services.project_agents import resolve_snapshot_paths


def _guard_paths(affected: list[str], snapshot_keys: set[str]) -> list[str]:
    """Mirror of the guard under test: normalize staged prefixes, suffix-match bare names.

    Returns the unknown (truly outside) paths. Empty = all resolved.
    """
    from modules.services.project_agents import resolve_snapshot_paths

    resolved, unknown = resolve_snapshot_paths(affected, snapshot_keys)
    assert len(resolved) == len(affected) - len(unknown)
    return unknown


def test_bare_repo_path_resolves_against_tree_prefixed_snapshot():
    """RED: bare ``app/app.py`` must resolve when the snapshot holds ``tree/app/app.py``."""
    snapshot = {"tree/app/app.py", "tree/app/templates/index.html", "repo.runtime_command"}
    assert _guard_paths(["app/app.py"], snapshot) == []


def test_staged_tree_path_still_resolves_verbatim():
    """RED: ``tree/app/app.py`` (AnyCam shape) must keep resolving verbatim."""
    snapshot = {"tree/app/app.py", "repo.runtime_command"}
    assert _guard_paths(["tree/app/app.py"], snapshot) == []


def test_truly_outside_path_still_fails_closed():
    """RED: ``/etc/passwd`` must remain unknown (guard purpose preserved)."""
    snapshot = {"tree/app/app.py", "repo.runtime_command"}
    assert _guard_paths(["/etc/passwd"], snapshot) == ["/etc/passwd"]


def test_ambiguous_suffix_match_fails_closed():
    """RED: bare ``app.py`` matching two staged files must NOT guess (0 or 2+ = error)."""
    snapshot = {"tree/a/app.py", "tree/b/app.py"}
    assert _guard_paths(["app.py"], snapshot) == ["app.py"]


def test_service_keys_never_patchable():
    """RED: ``repo.*`` keys resolve verbatim (exact match) but must never be
    SELECTED: build_blue_dossier's protected_paths excludes them. The resolver
    reports truthfully; the patch guard enforces. Here: a bare ``repo.x``
    with NO exact key stays unknown."""
    snapshot = {"tree/app/app.py", "repo.runtime_command", "repo.smoke_command"}
    resolved, unknown = resolve_snapshot_paths(["repo.runtime_command"], snapshot)
    assert resolved == ["repo.runtime_command"]  # exact match reports truthfully
    assert _guard_paths(["repo.other_command"], snapshot) == ["repo.other_command"]
