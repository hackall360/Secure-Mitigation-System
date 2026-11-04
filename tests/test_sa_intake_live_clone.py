# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first (D2): optional commit_hash (default-branch HEAD) + clone base image.

Fake Docker clients only: no network, no builds, no subprocess.
"""

from __future__ import annotations

import io
import tarfile

import pytest
from docker.errors import ImageNotFound

from library.core.config import ConfigurationError, PurpleBoxConfig
from library.services.repo_intake import RepoIntakeSpec, intake_repo_to_snapshot

COMMIT = "d" * 40
URL = "https://github.com/example/demo.git"


# --- 1. config: clone_base_image default + validator label ---


def test_config_clone_base_image_default():
    assert PurpleBoxConfig().clone_base_image == "purplebox-clone-base:latest"


def test_config_clone_base_image_label_rejects_bad_tag():
    with pytest.raises(ConfigurationError, match="clone base image"):
        PurpleBoxConfig(clone_base_image="bad tag!!").validate()


# --- 2. Dockerfile.clone exists and is pinned ---


def test_clone_dockerfile_pinned():
    from library.core import docker_manager as manager_module
    from library.core.registry import BASE_DIR

    content = (BASE_DIR / "docker" / "Dockerfile.clone").read_text(encoding="utf-8")
    assert manager_module.PINNED_PYTHON_BASE in content
    assert "git" in content


def test_pin_check_covers_dockerfile_clone(tmp_path, monkeypatch):
    from library.core import docker_manager as manager_module

    docker_dir = tmp_path / "docker"
    docker_dir.mkdir()
    for name in ("Dockerfile.target", "Dockerfile.verifier", "Dockerfile.binary"):
        (docker_dir / name).write_text(manager_module.PINNED_PYTHON_BASE + "\n")
    (docker_dir / "Dockerfile.clone").write_text("FROM python:3.12-unpinned\n")
    monkeypatch.setattr(manager_module, "BASE_DIR", tmp_path)
    with pytest.raises(manager_module.SandboxError, match="Dockerfile.clone"):
        manager_module._assert_dockerfiles_pinned()


# --- 3. build/ensure lists include the clone pair ---


class _Images:
    def __init__(self, present=()):
        self.present = set(present)
        self.builds = []
        self.gets = []

    def get(self, tag):
        self.gets.append(tag)
        if tag in self.present:
            return object()
        raise ImageNotFound("missing")

    def build(self, **kwargs):
        self.builds.append((kwargs["tag"], kwargs["dockerfile"]))
        return (None, None)


class _Client:
    def __init__(self, present=()):
        self.images = _Images(present)

    def ping(self):
        return True


def _expected_pairs(config):
    # OMNI-INGEST Wave 2: polyglot image joins the build matrix.
    return {
        (config.target_base_image, "Dockerfile.target"),
        (config.verifier_base_image, "Dockerfile.verifier"),
        (config.binary_base_image, "Dockerfile.binary"),
        (config.clone_base_image, "Dockerfile.clone"),
        (config.polyglot_base_image, "Dockerfile.polyglot"),
    }


def test_build_base_images_includes_clone_pair():
    from library.core.docker_manager import build_base_images

    config = PurpleBoxConfig()
    client = _Client(present=())
    built = build_base_images(config, client=client)
    assert set(client.images.builds) == _expected_pairs(config)
    assert set(built) == {
        config.target_base_image,
        config.verifier_base_image,
        config.binary_base_image,
        config.clone_base_image,
        config.polyglot_base_image,
    }


def test_ensure_base_images_includes_clone_pair():
    from library.core.docker_manager import DockerSandboxManager

    config = PurpleBoxConfig()
    client = _Client(present=())
    manager = DockerSandboxManager(config, client=client)
    manager.ensure_base_images()
    assert set(client.images.builds) == _expected_pairs(config)


def test_ensure_base_images_skips_present_clone():
    from library.core.docker_manager import DockerSandboxManager

    config = PurpleBoxConfig()
    client = _Client(
        present=(
            config.target_base_image,
            config.verifier_base_image,
            config.binary_base_image,
            config.clone_base_image,
            config.polyglot_base_image,
        )
    )
    DockerSandboxManager(config, client=client).ensure_base_images()
    assert client.images.builds == []


def test_require_base_images_stays_two_image_gate():
    import inspect

    from library.core.docker_manager import DockerSandboxManager

    src = inspect.getsource(DockerSandboxManager.require_base_images)
    assert "clone" not in src.lower()


# --- 4. optional commit_hash ---


def test_spec_accepts_none_commit_hash():
    spec = RepoIntakeSpec(url=URL, commit_hash=None)
    assert spec.commit_hash is None


@pytest.mark.parametrize("bad", ["", "abc123", "z" * 40, "a" * 39, "a" * 41, 123, b"a" * 40])
def test_spec_still_rejects_bad_hashes(bad):
    with pytest.raises(ValueError, match="commit_hash"):
        RepoIntakeSpec(url=URL, commit_hash=bad)


def _tar():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name="repo/app.py")
        data = b"print(1)\n"
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _Container:
    def __init__(self, code=0):
        self.code = code
        self.removed = False

    def wait(self, timeout=None):
        return {"StatusCode": self.code}

    def get_archive(self, path):
        return [_tar()], {}

    def remove(self, force=False):
        self.removed = True


class _Containers:
    def __init__(self):
        self.container = _Container()
        self.run_calls = []

    def run(self, image, command=None, **kwargs):
        self.run_calls.append((image, command, kwargs))
        return self.container

    def create(self, *a, **k):  # pragma: no cover
        raise AssertionError("create+exec is the broken shape (F-202)")


class _Sandbox:
    def __init__(self, **cfg_overrides):
        self.client = type("C", (), {})()
        self.client.containers = _Containers()
        cfg = {"target_base_image": "sms-target:1", "clone_base_image": "sms-clone:1"}
        cfg.update(cfg_overrides)
        self.config = type("Cfg", (), cfg)()


def _run_clone(commit_hash, **kw):
    sandbox = _Sandbox(**kw.pop("cfg", {}))
    spec = RepoIntakeSpec(url=URL, commit_hash=commit_hash)
    snap = intake_repo_to_snapshot(spec, ["python3", "app.py"], sandbox=sandbox, clone=True, **kw)
    return sandbox, snap


def test_clone_none_commit_omits_fetch_checkout():
    sandbox, snap = _run_clone(None)
    ((image, command, kwargs),) = sandbox.client.containers.run_calls
    script, argv = command[2], command[4:]
    assert "fetch" not in script
    assert "checkout" not in script
    assert argv == [URL]
    assert snap.commit_hash is None
    assert snap.files["repo.commit_hash"] == b""
    # Docker 29 quirk: writable root (no read_only/tmpfs) so get_archive
    # can see the staged tree; isolation via uid/caps/no-new-privileges.
    assert kwargs.get("read_only") is not True
    assert "tmpfs" not in kwargs
    assert kwargs.get("user") == "10001"
    assert kwargs.get("cap_drop") == ["ALL"]


def test_clone_pinned_commit_keeps_fetch_checkout():
    sandbox, _snap = _run_clone(COMMIT)
    ((_image, command, _kwargs),) = sandbox.client.containers.run_calls
    script, argv = command[2], command[4:]
    assert "fetch" in script and "checkout" in script
    assert argv == [URL, COMMIT]


def test_clone_default_image_falls_back_to_clone_base():
    sandbox, _snap = _run_clone(COMMIT)
    assert sandbox.client.containers.run_calls[0][0] == "sms-clone:1"


def test_clone_explicit_image_override_wins():
    sandbox, _snap = _run_clone(COMMIT, clone_image="git-img:2")
    assert sandbox.client.containers.run_calls[0][0] == "git-img:2"


def test_clone_none_commit_error_never_echoes_url():
    class _Fail(_Container):
        def wait(self, timeout=None):
            return {"StatusCode": 128}

        def get_archive(self, path):  # pragma: no cover
            raise AssertionError("must not read archive after failed clone")

    sandbox = _Sandbox()
    sandbox.client.containers.container = _Fail()
    spec = RepoIntakeSpec(url="https://git.example.org:8443/a/b.git", commit_hash=None)
    with pytest.raises(ValueError, match="staging clone failed") as info:
        intake_repo_to_snapshot(spec, ["x"], sandbox=sandbox, clone=True)
    assert "git.example.org:8443/a/b.git" not in str(info.value)
    assert "git.example.org" in str(info.value)
