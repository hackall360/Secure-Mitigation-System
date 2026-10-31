# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED test: runtime auto-detect for ingested repos (W8-runtime-autodetect).

The future ``detect_runtime`` in ``modules/services/repo_intake.py`` maps repo
contents to a runtime argv (package.json -> node/npm, requirements.txt or
pyproject.toml -> python3, composer.json -> php, Makefile -> make targets) and
fails closed with ``ValueError`` on unknown repos. ``intake_repo_to_snapshot``
gains opt-in auto-detect (``runtime_command=None`` + ``file_list=...``);
explicit commands still win. Pure function: no execution, no network (LAW 4).

RED state: ``detect_runtime`` does not exist yet and intake requires an
explicit command, so the detect tests fail here first.
"""

import os
import socket
import subprocess
from types import MappingProxyType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules.services import repo_intake
from modules.services.repo_intake import RepoIntakeSpec, intake_repo_to_snapshot

HAS_DETECT = hasattr(repo_intake, "detect_runtime")
REQUIRES_DETECT = "RED: detect_runtime not implemented in modules/services/repo_intake.py"

GOOD_URL = "https://github.com/example/demo"
GOOD_HASH = "b" * 40


def detect(source):
    assert HAS_DETECT, REQUIRES_DETECT
    return repo_intake.detect_runtime(source)


def test_detect_node_package_json():
    assert detect(["package.json", "src/index.js"]) == ["npm", "start"]


def test_detect_node_package_json_main_field():
    package = '{"name": "demo", "main": "dist/server.js"}'
    assert detect([{"package.json": package}]) == ["node", "dist/server.js"]


def test_detect_python_requirements():
    assert detect(["requirements.txt", "main.py"]) == ["python3", "main.py"]


def test_detect_python_pyproject():
    assert detect(["pyproject.toml", "src/app.py"]) == ["python3", "src/app.py"]


def test_detect_php_composer():
    assert detect(["composer.json", "public/index.php"]) == ["php", "public/index.php"]


def test_detect_makefile_run_target():
    makefile = "run:\n\tpython3 app.py\n\ntest:\n\tpytest\n"
    assert detect([{"Makefile": makefile}]) == ["make", "run"]


def test_detect_makefile_names_only_defaults_to_make():
    assert detect(["Makefile"]) == ["make"]


def test_unknown_repo_raises_actionable_valueerror():
    with pytest.raises(ValueError, match="runtime_command"):
        detect(["README.md", "docs/guide.txt"])


def test_empty_repo_raises_valueerror():
    with pytest.raises(ValueError):
        detect([])


def test_explicit_runtime_command_wins_over_autodetect():
    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    snapshot = intake_repo_to_snapshot(
        spec,
        ["python3", "custom.py"],
        sandbox=MagicMock(),
        file_list=["package.json"],
    )
    assert tuple(snapshot.runtime_command) == ("python3", "custom.py")


def test_intake_autodetects_when_runtime_omitted():
    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    snapshot = intake_repo_to_snapshot(spec, file_list=["package.json"], sandbox=MagicMock())
    assert tuple(snapshot.runtime_command) == ("npm", "start")


def test_intake_without_runtime_or_file_list_fails_closed():
    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    with pytest.raises(ValueError, match="runtime_command"):
        intake_repo_to_snapshot(spec, sandbox=MagicMock())


def test_intake_with_undetectable_files_fails_closed():
    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    with pytest.raises(ValueError, match="runtime_command"):
        intake_repo_to_snapshot(spec, file_list=["README.md"], sandbox=MagicMock())


def test_detect_accepts_snapshot_with_files_mapping():
    snapshot = SimpleNamespace(files=MappingProxyType({"package.json": b'{"name": "demo"}'}))
    assert detect(snapshot) == ["npm", "start"]


def test_detect_performs_no_execution_or_network(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("detect_runtime must not execute or call out")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    monkeypatch.setattr(os, "system", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", _forbidden)
    evil_files = [
        "requirements.txt; rm -rf /",
        {"Makefile": "$(shell rm -rf /)\nrun:\n\techo pwned"},
        {"package.json": '{"scripts": {"start": "__import__(\\"os\\").system(\\"id\\")"}}'},
    ]
    assert detect(["requirements.txt"]) == ["python3", "main.py"]
    assert detect([evil_files[1]]) == ["make", "run"]
    assert detect([evil_files[2]]) == ["npm", "start"]
    with pytest.raises(ValueError):
        detect([evil_files[0]])
