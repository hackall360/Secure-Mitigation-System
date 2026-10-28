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


def test_serve_up_kills_only_own_spawn_and_restarts_with_key(dev, tmp_path, monkeypatch):
    """LAW 7 drill contract: stale keyless server -> restart -> keyed ready."""
    import io
    import json
    import urllib.request

    state = {"ready": False, "keyed": False}
    spawned = []

    class FakeProc:
        _next_pid = 9000

        def __init__(self, *args, **kwargs):
            FakeProc._next_pid += 1
            self.pid = FakeProc._next_pid
            self.args = args
            self.env = kwargs.get("env", {})
            # The stale server was started WITHOUT the key; the restart must have it.
            state["ready"] = True
            state["keyed"] = bool(self.env.get("META_MUSE_API_KEY"))
            spawned.append(self)

        def terminate(self):
            state["ready"] = False
            state["keyed"] = False

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return None

    class FakeResponse:
        def __init__(self, payload):
            self._body = json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return self._body

    class FakeOpener:
        def open(self, url, timeout=None):
            if not state["ready"]:
                raise OSError("connection refused")
            return FakeResponse(
                {
                    "status": "ok",
                    "api_key_configured": state["keyed"],
                    "inference_ready": state["keyed"],
                }
            )

    # A stale keyless server already answers on the port; it is OURS, so an
    # own tracked handle exists for it (that is the only thing serve_up kills).
    stale = FakeProc()
    dev._TRACKED[18001] = stale
    monkeypatch.setattr(dev.subprocess, "Popen", FakeProc)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: FakeOpener())
    monkeypatch.setattr(dev.time, "sleep", lambda seconds: None)
    env_file = dev.ROOT / ".env"
    env_file.write_text("META_MUSE_API_KEY=test-key-not-a-secret\n")
    python_bin = tmp_path / ".venv/bin/python"
    python_bin.parent.mkdir(parents=True)
    python_bin.touch()
    monkeypatch.setattr(dev, "PYTHON", python_bin)

    out = io.StringIO()
    monkeypatch.setattr(dev.sys, "stdout", out)
    try:
        dev.serve_up(port=18001, restart=True)
    finally:
        dev._TRACKED.pop(18001, None)

    # Only the stale handle was terminated; its PID was never passed to a
    # broad kill, and the restart carries the key.
    assert stale.pid not in [p.pid for p in spawned[1:]]
    assert spawned[-1].env.get("META_MUSE_API_KEY") == "test-key-not-a-secret"
    assert state["keyed"] is True
    assert "api_key_configured=True" in out.getvalue()


def test_serve_up_refuses_to_steal_a_foreign_server(dev, monkeypatch):
    """LAW 7 safety: a live server we did not spawn is left alone."""
    import urllib.request

    class DeadOpener:
        def open(self, url, timeout=None):
            raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: DeadOpener())
    monkeypatch.setattr(
        dev.subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must not spawn when nothing listens and restart=False")
        ),
    )
    import pytest as _pytest

    with _pytest.raises(RuntimeError, match="missing|empty"):
        dev.serve_up(port=18002, restart=False)
