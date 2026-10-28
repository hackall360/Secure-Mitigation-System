# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Development tooling must remain scoped to the repository and protect local config."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def dev(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / ".jcode/tools/dev.py"
    spec = importlib.util.spec_from_file_location("purplebox_dev", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "PYTHON", tmp_path / ".venv/bin/python")
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(module, "run", Mock())
    (tmp_path / "example.env").write_text("META_MUSE_API_KEY=\n")
    return module


def test_setup_creates_local_environment_and_private_template(dev):
    dev.setup()
    assert dev.run.call_args_list[0].args == ("uv", "venv", "--python", "3.12", dev.ROOT / ".venv")
    sync = dev.run.call_args_list[1].args
    assert sync == (
        "uv",
        "pip",
        "sync",
        "--python",
        dev.PYTHON,
        "--require-hashes",
        "requirements-dev.lock",
    )
    assert (dev.ROOT / ".env").read_text() == "META_MUSE_API_KEY=\n"
    assert (dev.ROOT / ".env").stat().st_mode & 0o777 == 0o600


def test_setup_preserves_existing_environment_and_configuration(dev):
    dev.PYTHON.parent.mkdir(parents=True)
    dev.PYTHON.touch()
    env = dev.ROOT / ".env"
    env.write_text("# Developer configuration must survive\n")
    before = env.read_bytes()
    dev.setup()
    assert env.read_bytes() == before
    assert not any("venv" in call.args for call in dev.run.call_args_list)


def test_setup_missing_uv_does_not_modify_environment(dev, monkeypatch):
    monkeypatch.setattr(dev.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Install uv first"):
        dev.setup()
    dev.run.assert_not_called()
    assert not (dev.ROOT / ".env").exists()


def test_python_command_requires_repository_environment(dev):
    with pytest.raises(RuntimeError, match="setup"):
        dev.python("main.py", "--list-targets")
    dev.run.assert_not_called()


def test_python_command_uses_repository_interpreter(dev):
    dev.PYTHON.parent.mkdir(parents=True)
    dev.PYTHON.touch()
    dev.python("main.py", "--list-targets")
    dev.run.assert_called_once_with(dev.PYTHON, "main.py", "--list-targets")


def test_gitignore_protects_secrets_and_allows_environment_templates():
    import subprocess

    root = Path(__file__).resolve().parents[1]
    paths = [".env", ".env.local", ".env.production", "example.env", ".env.example"]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        input="\n".join(paths) + "\n",
        text=True,
        capture_output=True,
        cwd=root,
        check=False,
    )
    assert result.returncode == 0
    assert set(result.stdout.splitlines()) == {".env", ".env.local", ".env.production"}
    assert (root / "example.env").is_file()
