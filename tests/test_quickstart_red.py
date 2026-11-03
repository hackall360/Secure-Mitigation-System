# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (HH1): one-command quickstart contract. Now GREEN.

`dev.py quickstart` takes a fresh clone to a live verdict in one
command: bootstrap .venv via uv (stdlib venv fallback only when uv is
absent), pre-flight Docker with an explicit fail message, provision .env
from example.env without overwriting, build base images idempotently, and
run the chain fixture end to end printing verdict + receipt. Keyless
default stays offline-verified; --keyed runs one live chain scan and
fails closed when no key is configured (LAW 7).
"""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def dev(tmp_path, monkeypatch):
    import subprocess

    path = Path(__file__).resolve().parents[1] / "scripts/dev/dev.py"
    spec = importlib.util.spec_from_file_location("purplebox_dev_qs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "PYTHON", tmp_path / ".venv/bin/python")
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/uv")
    # run() is mocked, so nothing materializes .venv: fake the venv creation
    # side effect (uv venv / stdlib venv both produce the interpreter) while
    # recording every call for the contract assertions.
    calls = []

    def fake_run(*args):
        calls.append(args)
        joined = " ".join(map(str, args))
        if "venv" in joined:
            interpreter = tmp_path / ".venv/bin/python"
            interpreter.parent.mkdir(parents=True, exist_ok=True)
            interpreter.touch()

    monkeypatch.setattr(module, "run", Mock(side_effect=fake_run))
    # The mocked suite has no Docker daemon: pretend the pre-flight ping passes
    # so the venv/idempotency contract is what these tests exercise. The
    # dedicated no-docker test below overrides this with a failing probe.
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0] if a else "docker", 0),
    )
    (tmp_path / "example.env").write_text("META_MUSE_API_KEY=\n")
    return module


def test_quickstart_entry_exists(dev):
    """The quickstart entry point must exist (failed: AttributeError pre-HH2)."""
    assert callable(dev.quickstart), "dev.quickstart entry is missing"


def test_quickstart_bootstraps_venv_via_uv(dev, tmp_path):
    """Fresh clone: venv created via uv, deps synced hashed, .env templated."""
    dev.quickstart(keyed=False)
    venue_calls = [c.args for c in dev.run.call_args_list]
    assert any(c[:3] == ("uv", "venv", "--python") for c in venue_calls), (
        "venv must be bootstrapped via uv"
    )
    assert any(c[:2] == ("uv", "pip") and "--require-hashes" in c for c in venue_calls), (
        "deps must sync hashed via uv pip"
    )
    env = tmp_path / ".env"
    assert env.is_file(), ".env template must be provisioned"
    assert env.stat().st_mode & 0o777 == 0o600


def test_quickstart_idempotent_second_run_skips_venv(dev, tmp_path):
    """Second run: existing .venv + .env must survive untouched (idempotency)."""
    venv_python = tmp_path / ".venv/bin/python"
    venv_python.parent.mkdir(parents=True)
    venv_python.touch()
    env = tmp_path / ".env"
    env.write_text("# Developer configuration must survive\n")
    before = env.read_bytes()
    dev.quickstart(keyed=False)
    assert env.read_bytes() == before, "existing .env must never be overwritten"
    assert not any("venv" in c.args for c in dev.run.call_args_list), (
        "existing .venv must not be re-created"
    )


def test_quickstart_fails_closed_without_docker(dev, monkeypatch):
    """Docker unreachable: explicit fail naming docker, before any scan."""
    import subprocess

    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0] if args else "docker")

    monkeypatch.setattr(dev.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="[Dd]ocker"):
        dev.quickstart(keyed=False)


def test_quickstart_falls_back_to_stdlib_venv_without_uv(dev, monkeypatch, tmp_path):
    """No uv: stdlib venv fallback with a clear message, never a hard fail."""
    import io
    import subprocess as _sp

    def no_uv(name):
        if name == "uv":
            return None
        return "/usr/bin/" + name

    monkeypatch.setattr(dev.shutil, "which", no_uv)
    monkeypatch.setattr(
        dev.subprocess,
        "run",
        lambda *a, **k: _sp.CompletedProcess(a[0] if a else "docker", 0),
    )
    out = io.StringIO()
    monkeypatch.setattr(dev.sys, "stdout", out)
    dev.quickstart(keyed=False)
    assert "uv" in out.getvalue().lower(), "fallback must name uv as missing"


def test_quickstart_keyed_fails_closed_without_key(dev, tmp_path):
    """--keyed with empty key: fail closed naming the key, never scan keyless."""
    (tmp_path / ".env").write_text("META_MUSE_API_KEY=\n")
    with pytest.raises(RuntimeError, match="[Kk]ey"):
        dev.quickstart(keyed=True)


def test_quickstart_keyed_propagates_key_to_scan_env(dev, tmp_path, monkeypatch):
    """--keyed with a key: the scan subprocess env must carry META_MUSE_API_KEY."""
    import subprocess as _sp

    (tmp_path / ".env").write_text("META_MUSE_API_KEY=test-key-not-a-secret\n")
    seen: dict = {}

    def fake_python(*args):
        pass  # skip images/offline stages; the scan path is what this pins

    monkeypatch.setattr(dev, "python", fake_python)

    def recording_run(*a, **k):
        # Docker pre-flight ping passes; the keyed scan records env then fails.
        if "from_env" in str(a[0] if a else "") or "ping" in str(a[0] if a else ""):
            return _sp.CompletedProcess(a[0] if a else "docker", 0)
        seen.update(k.get("env", {}))
        raise _sp.CalledProcessError(7, a[0] if a else "scan")

    monkeypatch.setattr(dev.subprocess, "run", recording_run)
    with pytest.raises(_sp.CalledProcessError):
        dev.quickstart(keyed=True)
    assert seen.get("META_MUSE_API_KEY") == "test-key-not-a-secret", (
        "keyed scan must run with the key exported (LAW 7: main.py never loads .env)"
    )
