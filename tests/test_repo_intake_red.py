# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED test: repo-intake staging spec (W1-ingest-reuse).

The future ``modules/services/repo_intake.py`` will expose ``RepoIntakeSpec``
(url + commit_hash validation) and a staging-container intake function feeding
``snapshot_project``. This test imports from that not-yet-existing module, so
ModuleNotFoundError is the expected RED failure. No network, no real clone,
no exploit payloads. Docker boundary is mocked only (LAW 9C).
"""

from unittest.mock import MagicMock

import pytest

try:
    from modules.services.repo_intake import (
        RepoIntakeSpec,
        intake_repo_to_snapshot,
    )

    HAS_REPO_INTAKE = True
except ModuleNotFoundError:
    HAS_REPO_INTAKE = False
    RepoIntakeSpec = None  # type: ignore[assignment,misc]
    intake_repo_to_snapshot = None  # type: ignore[assignment]

REQUIRES_INTAKE = "RED: modules/services/repo_intake.py not implemented"

GOOD_URL = "https://github.com/example/demo"
GOOD_HASH = "a" * 40


def test_repo_intake_module_exists():
    assert HAS_REPO_INTAKE, REQUIRES_INTAKE


def test_accepts_https_github_url_and_40hex_commit():
    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    assert spec.url.startswith("https://")
    assert spec.commit_hash == GOOD_HASH


def test_rejects_non_https_schemes():
    for bad in ("git://github.com/example/demo", "ssh://git@github.com/example/demo"):
        with pytest.raises(ValueError):
            RepoIntakeSpec(url=bad, commit_hash=GOOD_HASH)


def test_rejects_blank_or_short_hashes():
    for bad_hash in ("", "abc123", "z" * 40, "a" * 39):
        with pytest.raises(ValueError):
            RepoIntakeSpec(url=GOOD_URL, commit_hash=bad_hash)


def test_intake_accepts_spec_and_runtime_command_and_returns_snapshot():
    sandbox = MagicMock()
    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    snapshot = intake_repo_to_snapshot(spec, ["python3", "/workspace/src/app.py"], sandbox=sandbox)
    assert snapshot is not None
    assert hasattr(snapshot, "files")


def test_intake_refuses_host_paths():
    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    assert not hasattr(spec, "host_path")
    sandbox = MagicMock()
    with pytest.raises((ValueError, TypeError, AttributeError)):
        intake_repo_to_snapshot(
            spec, ["python3", "/workspace/src/app.py"], sandbox=sandbox, host_path="/tmp/evil"
        )
