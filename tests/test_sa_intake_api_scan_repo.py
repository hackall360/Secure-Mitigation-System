# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: sms_api.scan_repo (D7 separate-project surface, slice intake-34).

FAKE intake/sandbox only: monkeypatched intake_repo_to_snapshot,
execute_project_workflow, and DockerSandboxManager. Never real Docker,
never network.
"""

from __future__ import annotations

import inspect

import pytest

import modules.services.sms_api as sms_api
from modules.core.config import ConfigurationError, PurpleBoxConfig

URL = "https://github.com/example/demo.git"
COMMIT = "c" * 40
HEAD_SHA = "ab" * 20


class _FakeContainer:
    def __init__(self, log_line: bytes = b""):
        self._log_line = log_line
        self.removed = False

    def wait(self, timeout=None):
        return {"StatusCode": 0}

    def logs(self):
        return self._log_line

    def remove(self, force=False):
        self.removed = True


class _FakeContainers:
    def __init__(self, log_line: bytes = b""):
        self.calls: list[dict] = []
        self._log_line = log_line

    def run(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return _FakeContainer(log_line=self._log_line)


class _FakeClient:
    def __init__(self, log_line: bytes = b""):
        self.containers = _FakeContainers(log_line=log_line)


class _FakeManager:
    instances: list["_FakeManager"] = []

    def __init__(self, config, **kwargs):
        self.config = config
        self.client = _FakeClient(log_line=f"{HEAD_SHA}\tHEAD\n".encode())
        _FakeManager.instances.append(self)


class _FakeSnapshot:
    def __init__(self, url, commit_hash):
        import json as _json

        self.url = url
        self.commit_hash = commit_hash
        self.runtime_command = ("true",)
        self.files = {
            "repo.url": url.encode(),
            "tree/main.py": b"print('ok')\n",
            "tree/requirements.txt": b"requests\n",
            # Wrapper manifest entries (build_service_wrapper would add
            # these): the scan path reads them for serve/smoke argv.
            "repo.runtime_command": _json.dumps(
                ["python3", "-c", "wrapper"]
            ).encode(),
            "repo.smoke_command": _json.dumps(
                ["python3", "-c", "wrapper", "--smoke"]
            ).encode(),
        }


def _keyed_config() -> PurpleBoxConfig:
    return PurpleBoxConfig(meta_api_key="unit-test-key-not-a-secret")


@pytest.fixture
def fake_stack(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr("modules.core.docker_manager.DockerSandboxManager", _FakeManager)
    _FakeManager.instances.clear()

    def fake_intake(spec, runtime_command=None, *, sandbox=None, **kwargs):
        calls["intake"] = {
            "spec": spec,
            "runtime_command": runtime_command,
            "sandbox": sandbox,
            "kwargs": kwargs,
        }
        return _FakeSnapshot(spec.url, spec.commit_hash)

    async def fake_execute(project, emit, *, config=None, **kwargs):
        calls["project"] = project
        calls["execute_config"] = config
        return {"status": "no_findings", "sentinel": True}

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr("modules.workflows.project_workflow.execute_project_workflow", fake_execute)
    return calls


def test_scan_repo_surface_exists():
    assert hasattr(sms_api, "scan_repo"), "sms_api.scan_repo missing"
    assert hasattr(sms_api, "ApiRepoScanRequest"), "ApiRepoScanRequest missing"
    sig = inspect.signature(sms_api.scan_repo)
    params = list(sig.parameters)
    assert params[0] == "repo_url"
    assert params[1] == "emit"
    for name in ("commit_hash", "contract", "config"):
        assert name in sig.parameters, name
        assert sig.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY, name


def test_scan_repo_request_forbids_extras():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        sms_api.ApiRepoScanRequest(repo_url=URL, commit_hash=COMMIT, contract="", bogus="nope")


@pytest.mark.asyncio
async def test_scan_repo_valid_reaches_intake_with_clone(fake_stack):
    result = await sms_api.scan_repo(URL, commit_hash=COMMIT, contract="", config=_keyed_config())
    assert result == {"status": "no_findings", "sentinel": True}
    intake = fake_stack["intake"]
    assert intake["kwargs"].get("clone") is True
    assert isinstance(intake["sandbox"], _FakeManager)
    assert intake["spec"].url == URL
    assert intake["spec"].commit_hash == COMMIT


@pytest.mark.asyncio
async def test_scan_repo_head_defaults_to_ls_remote(fake_stack):
    result = await sms_api.scan_repo(URL, config=_keyed_config())
    assert result == {"status": "no_findings", "sentinel": True}
    intake = fake_stack["intake"]
    assert intake["spec"].commit_hash == HEAD_SHA
    assert intake["kwargs"].get("clone") is True
    manager = _FakeManager.instances[-1]
    run_calls = manager.client.containers.calls
    assert run_calls, "HEAD resolution must run a staging container"
    flat = " ".join(
        str(part)
        for call in run_calls
        for part in (list(call["args"]) + list(call["kwargs"].get("command", [])))
    )
    assert "ls-remote" in flat


@pytest.mark.asyncio
async def test_scan_repo_bad_url_names_rule_not_url(fake_stack):
    bad = "https://user:hunter2@github.com/a/b.git"
    with pytest.raises(ValueError, match="must not embed credentials") as info:
        await sms_api.scan_repo(bad, commit_hash=COMMIT, config=_keyed_config())
    assert "hunter2" not in str(info.value)
    assert bad not in str(info.value)


@pytest.mark.asyncio
async def test_scan_repo_bad_scheme_names_rule(fake_stack):
    with pytest.raises(ValueError, match="https"):
        await sms_api.scan_repo(
            "http://github.com/a/b.git", commit_hash=COMMIT, config=_keyed_config()
        )


@pytest.mark.asyncio
async def test_scan_repo_keyless_names_key():
    with pytest.raises(ConfigurationError, match="META_MUSE_API_KEY"):
        await sms_api.scan_repo(URL, commit_hash=COMMIT, config=PurpleBoxConfig())


@pytest.mark.asyncio
async def test_scan_repo_grants_remote_inference_and_carries_contract(fake_stack):
    from modules.services.projects import ProjectSpec

    contract = "Only sanitize untrusted inputs. Preserve the public API."
    await sms_api.scan_repo(URL, commit_hash=COMMIT, contract=contract, config=_keyed_config())
    project = fake_stack["project"]
    assert isinstance(project, ProjectSpec)
    assert project.allow_remote_inference is True
    assert project.contract == contract
