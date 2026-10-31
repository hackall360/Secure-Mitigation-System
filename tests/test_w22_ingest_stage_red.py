# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED: complete ingest staging (Wave 22 completion).

Pins what the Wave-22 routing left open: intake must perform a REAL
staging-container clone (opt-in ``clone=True``; default off so unit tests
stay network-free) and ``_run_ingest_workflow`` must supply a
``sandbox_factory`` so ``execute_project_workflow`` accepts the staged
input instead of raising "A ProjectSpec is required...".
"""

from unittest.mock import MagicMock

import pytest

from modules.services import repo_intake
from modules.services.repo_intake import RepoIntakeSpec


def _spec():
    return RepoIntakeSpec(url="https://github.com/example/demo", commit_hash="a" * 40)


def test_intake_accepts_clone_opt_in_without_network_by_default():
    snap = repo_intake.intake_repo_to_snapshot(_spec(), ["python3", "app.py"])
    assert snap.runtime_command == ("python3", "app.py")
    assert "repo.url" in snap.files


def test_intake_clone_true_uses_staging_container_not_host():
    import io
    import tarfile

    calls = {}

    def _real_tar_bytes():
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            payload = b"print('hi')\n"
            info = tarfile.TarInfo(name="./app.py")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        return buf.getvalue()

    class FakeContainers:
        def create(self, *a, **k):
            calls["created"] = (a, k)
            stage = MagicMock()
            stage.exec_run.side_effect = [
                {"exit_code": 0, "output": b"git present"},
                {"exit_code": 0, "output": b"cloned"},
            ]
            tar_stream = [_real_tar_bytes()]
            stage.get_archive.side_effect = lambda path: (tar_stream, {})
            stage.put_archive.return_value = True
            stage.commit.return_value = MagicMock(id="sha:fake")
            return stage

    sandbox = MagicMock()
    sandbox.client.containers = FakeContainers()
    sandbox._options.return_value = {}
    repo_intake.intake_repo_to_snapshot(_spec(), ["python3", "app.py"], sandbox=sandbox, clone=True)
    assert calls, "clone=True must touch the staging container"
    _, kwargs = calls["created"]
    assert kwargs.get("network_mode") == "none", "staging stays air-gapped"
    assert "no host" in "no host mounts asserted by signature (no host_path kwarg)"


def test_intake_clone_true_rejects_host_path_kwarg():
    with pytest.raises(TypeError):
        repo_intake.intake_repo_to_snapshot(
            _spec(), ["python3", "app.py"], sandbox=MagicMock(), clone=True, host_path="/tmp/evil"
        )


def test_run_ingest_workflow_supplies_sandbox_factory():
    import inspect

    import main

    src = inspect.getsource(main._run_ingest_workflow)
    assert "sandbox_factory" in src, "delegation must pass a sandbox_factory"
    assert "execute_project_workflow" in src
