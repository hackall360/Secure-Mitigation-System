# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: F-203 (intake URL userinfo/private-host) and F-202 (live clone shape).

Fake Docker client only: no network, no Docker, no subprocess.
"""

from __future__ import annotations

import io
import tarfile

import pytest

from library.services.repo_intake import RepoIntakeSpec, intake_repo_to_snapshot

COMMIT = "c" * 40
URL = "https://github.com/example/demo.git"


@pytest.mark.parametrize(
    "url",
    [
        "https://user:hunter2@github.com/a/b.git",
        "https://user@github.com/a/b.git",
        "https://127.0.0.1/a.git",
        "https://127.0.0.1:8443/a.git",
        "https://10.0.0.5/a.git",
        "https://192.168.1.1/a.git",
        "https://169.254.169.254/latest",
        "https://0.0.0.0/a.git",
        "https://224.0.0.1/a.git",
        "https://[::1]/a.git",
        "https://[fe80::1]/a.git",
        "https://[fd00::1]/a.git",
        "https://localhost/a.git",
        "https://api.localhost/a.git",
        "https://metadata.google.internal/a",
        "https://svc.corp.internal/a.git",
        "https://printer.local/a.git",
    ],
)
def test_spec_rejects_credentials_and_private_hosts(url):
    with pytest.raises(ValueError) as info:
        RepoIntakeSpec(url=url, commit_hash=COMMIT)
    assert "hunter2" not in str(info.value)
    assert url not in str(info.value)


def test_spec_credential_message_names_rule():
    with pytest.raises(ValueError, match="must not embed credentials"):
        RepoIntakeSpec(url="https://u:p@github.com/a/b.git", commit_hash=COMMIT)


@pytest.mark.parametrize(
    "url",
    ["https://github.com/a/b.git", "https://git.example.org:8443/a/b.git", "https://8.8.8.8/a.git"],
)
def test_spec_keeps_public_hosts_and_ports(url):
    assert RepoIntakeSpec(url=url, commit_hash=COMMIT).url == url


@pytest.mark.parametrize("url", ["http://github.com/a", "https://x/a$(id)", "git://h/a"])
def test_spec_keeps_existing_rules(url):
    with pytest.raises(ValueError):
        RepoIntakeSpec(url=url, commit_hash=COMMIT)


def _tar():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in (("repo/app.py", b"print(1)\n"), ("repo/.git/config", b"x")):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _Container:
    def __init__(self, code):
        self.code = code
        self.removed = False
        self.waited = None

    def wait(self, timeout=None):
        self.waited = timeout
        return {"StatusCode": self.code}

    def get_archive(self, path):
        if self.code != 0:
            raise AssertionError("must not read archive after failed clone")
        self.archived = path
        return [_tar()], {}

    def remove(self, force=False):
        self.removed = True

    def exec_run(self, *a, **k):  # pragma: no cover - must never be used
        raise AssertionError("exec_run on a never-started container is a 409")


class _Containers:
    def __init__(self, code):
        self.container = _Container(code)
        self.run_calls = []

    def run(self, image, command=None, **kwargs):
        self.run_calls.append((image, command, kwargs))
        return self.container

    def create(self, *a, **k):  # pragma: no cover
        raise AssertionError("create+exec is the broken shape (F-202)")


class _Sandbox:
    def __init__(self, code):
        self.client = type("C", (), {})()
        self.client.containers = _Containers(code)
        self.config = type("Cfg", (), {"target_base_image": "sms-base:1"})()


def _run(code, **kw):
    sandbox = _Sandbox(code)
    spec = RepoIntakeSpec(url=URL, commit_hash=COMMIT)
    result = intake_repo_to_snapshot(
        spec, ["python3", "app.py"], sandbox=sandbox, clone=True, clone_timeout_seconds=30, **kw
    )
    return sandbox.client.containers, result


def test_clone_uses_run_with_positional_argv_and_hardening():
    containers, snap = _run(0)
    assert len(containers.run_calls) == 1
    image, command, kwargs = containers.run_calls[0]
    assert image == "sms-base:1"
    assert command[:2] == ["sh", "-c"]
    script = command[2]
    assert URL not in script and COMMIT not in script
    assert URL in command[3:] and COMMIT in command[3:]
    assert "-- " in script or '--" "$' in script or ' -- "$1"' in script
    for opt in ("protocol.allow=never", "protocol.https.allow=always", "submodule.recurse=false"):
        assert opt in script
    env = kwargs["environment"]
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["GIT_LFS_SKIP_SMUDGE"] == "1"
    assert kwargs["detach"] is True
    assert kwargs["user"] == "10001"
    assert "/work" in kwargs["tmpfs"]
    assert not kwargs.get("volumes") and not kwargs.get("mounts")
    assert kwargs.get("pids_limit") and kwargs.get("mem_limit")
    assert containers.container.waited == 30
    assert containers.container.removed
    assert snap.files["tree/repo/app.py"] == b"print(1)\n"
    assert not any(".git" in k for k in snap.files if k.startswith("tree/"))


def test_clone_image_override():
    containers, _ = _run(0, clone_image="git-img:2")
    assert containers.run_calls[0][0] == "git-img:2"


def test_clone_127_fails_closed_no_git():
    sandbox = _Sandbox(127)
    with pytest.raises(ValueError, match="staging clone unavailable: no git"):
        intake_repo_to_snapshot(
            RepoIntakeSpec(url=URL, commit_hash=COMMIT), ["x"], sandbox=sandbox, clone=True
        )
    assert sandbox.client.containers.container.removed


def test_clone_nonzero_fails_without_full_url():
    sandbox = _Sandbox(128)
    with pytest.raises(ValueError, match="staging clone failed") as info:
        intake_repo_to_snapshot(
            RepoIntakeSpec(url=URL, commit_hash=COMMIT), ["x"], sandbox=sandbox, clone=True
        )
    assert URL not in str(info.value)
    assert "github.com" in str(info.value) and COMMIT[:12] in str(info.value)
    assert sandbox.client.containers.container.removed
