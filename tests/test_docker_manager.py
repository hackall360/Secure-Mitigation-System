# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import importlib.util
import io
import tarfile
from unittest.mock import MagicMock

import pytest
from docker.errors import APIError

from config import PurpleBoxConfig
from docker_manager import DockerSandboxManager, SandboxError
from projects import ProjectSpec, snapshot_project
from registry import BASE_DIR


def project_spec(tmp_path):
    (tmp_path / "src").mkdir(exist_ok=True)
    executable = tmp_path / "src" / "serve.py"
    executable.write_text("print('ready')\n", encoding="utf-8")
    executable.chmod(0o755)
    return ProjectSpec.model_validate(
        {
            "path": str(tmp_path),
            "command": ["python3", "/workspace/src/serve.py"],
            "test_command": ["python3", "-m", "unittest"],
            "contract": "The service remains available.",
        }
    )


@pytest.mark.parametrize("filename", ["../secret", "/tmp/evil", "x/y", "x\\y", ".", ".."])
def test_tar_rejects_path_escape(filename):
    with pytest.raises(ValueError):
        DockerSandboxManager._create_tar_bytes(filename, "source")


def test_tar_has_only_regular_non_root_owned_read_only_source():
    data = DockerSandboxManager._create_tar_bytes("app.js", "source")
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        (entry,) = archive.getmembers()
        assert entry.name == "app.js" and entry.isfile()
        assert entry.uid == 10001 and entry.mode == 0o444
        assert archive.extractfile(entry).read() == b"source"


def test_staging_and_verifier_limits_and_cleanup():
    client, stage, runtime = MagicMock(), MagicMock(), MagicMock()
    client.containers.create.side_effect = [stage, runtime]
    stage.put_archive.return_value = True
    runtime.wait.return_value = {"StatusCode": 1}
    runtime.logs.return_value = b"boundary blocked"
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)
    network = manager.create_isolated_network()
    network.name = "internal-net"
    result = manager.run_isolated_verifier(network, "import sys\nsys.exit(1)")
    assert result.exit_code == 1
    assert client.networks.create.call_args.kwargs["internal"] is True
    assert client.networks.create.call_args.kwargs["options"] == {
        "com.docker.network.bridge.gateway_mode_ipv4": "isolated"
    }
    create_stage, create_runtime = client.containers.create.call_args_list
    assert create_stage.kwargs["network_mode"] == "none"
    stage.start.assert_not_called()
    for call in (create_stage, create_runtime):
        assert call.kwargs["cap_drop"] == ["ALL"]
        assert call.kwargs["security_opt"] == ["no-new-privileges:true"]
        assert call.kwargs["mem_limit"] == "128m"
        assert call.kwargs["memswap_limit"] == "128m"
        assert call.kwargs["nano_cpus"] == 500_000_000
        assert call.kwargs["user"] == "10001:10001"
        assert not ({"ports", "volumes", "privileged"} & call.kwargs.keys())
    assert create_runtime.kwargs["read_only"] is True
    assert create_runtime.kwargs["use_config_proxy"] is False
    runtime.remove.assert_called_with(force=True)
    manager.close()
    network.remove.assert_called_once()
    client.images.remove.assert_called_once()


def test_failed_archive_injection_removes_staging_container():
    client = MagicMock()
    stage = client.containers.create.return_value
    stage.put_archive.side_effect = APIError("failed")
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)
    with pytest.raises(APIError):
        manager._snapshot("image", "/workspace", "app.js", "source", "target")
    stage.remove.assert_called_once_with(force=True)
    stage.start.assert_not_called()


def test_verifier_timeout_is_inconclusive_and_removed():
    client, stage, runtime = MagicMock(), MagicMock(), MagicMock()
    client.containers.create.side_effect = [stage, runtime]
    runtime.wait.side_effect = TimeoutError()
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)
    with pytest.raises(SandboxError, match="inconclusive"):
        manager.run_isolated_verifier(MagicMock(), "import sys\nsys.exit(1)")
    runtime.remove.assert_called_once_with(force=True)


def test_cleanup_attempts_network_after_container_failure():
    client, container, network = MagicMock(), MagicMock(), MagicMock()
    container.remove.side_effect = APIError("busy")
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)
    manager.containers.append(container)
    manager.networks.append(network)
    with pytest.raises(SandboxError, match="Cleanup"):
        manager.close()
    network.remove.assert_called_once()
    client.close.assert_called_once()


@pytest.mark.parametrize(
    "failure,expected",
    [(RuntimeError("crash"), 2), (SystemExit(1), 1), (SystemExit(0), 0), (SystemExit(None), 2)],
)
def test_runner_distinguishes_exception_from_explicit_block(monkeypatch, failure, expected):
    spec = importlib.util.spec_from_file_location(
        "verifier_runner", BASE_DIR / "docker" / "runner.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(runner.runpy, "run_path", fail)
    assert runner.main() == expected


def test_docker_status_reports_ready_missing_and_unavailable():
    from docker.errors import DockerException, ImageNotFound

    from docker_manager import docker_status

    client = MagicMock()
    client.containers.list.return_value = []
    assert docker_status(PurpleBoxConfig(), client=client)["state"] == "ready"
    client.images.get.side_effect = [None, ImageNotFound("gone")]
    report = docker_status(PurpleBoxConfig(), client=client)
    assert report["state"] == "images_missing"
    assert report["missing_images"] == ["purplebox-verifier-base:latest"]
    client.ping.side_effect = DockerException("down")
    assert docker_status(PurpleBoxConfig(), client=client)["state"] == "unavailable"


def test_stale_cleanup_is_label_scoped_and_keeps_base_images():
    from docker_manager import remove_stale_resources

    client = MagicMock()
    container, network, snapshot = MagicMock(), MagicMock(), MagicMock(id="sha256:x")
    client.containers.list.return_value = [container]
    client.networks.list.return_value = [network]
    client.images.list.return_value = [snapshot]
    removed = remove_stale_resources(PurpleBoxConfig(), client=client)
    assert removed == {"containers": 1, "networks": 1, "snapshots": 1}
    client.containers.list.assert_called_once_with(all=True, filters={"label": "purplebox.session"})
    client.networks.list.assert_called_once_with(filters={"label": "purplebox.session"})
    client.images.list.assert_called_once_with(name="purplebox-clone-cache")
    client.images.remove.assert_called_once_with(image="sha256:x", force=True)


def test_project_tar_preserves_nested_paths_and_executable_bits(tmp_path):
    snapshot = snapshot_project(project_spec(tmp_path))
    data = DockerSandboxManager._create_project_tar(snapshot)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        members = {member.name: member for member in archive.getmembers()}
        assert members["src"].isdir() and members["src"].mode == 0o555
        assert members["src/serve.py"].isfile()
        assert members["src/serve.py"].mode == 0o755
        assert members["src/serve.py"].uid == 10001
        assert archive.extractfile(members["src/serve.py"]).read() == b"print('ready')\n"


def test_start_project_uses_preloaded_image_fresh_snapshot_and_hardening(tmp_path):
    client, stage, runtime = MagicMock(), MagicMock(), MagicMock()
    client.images.get.return_value.attrs = {"Config": {"Env": ["PATH=/usr/bin"], "Volumes": None}}
    client.containers.create.side_effect = [stage, runtime]
    stage.put_archive.return_value = True
    network = MagicMock(name="network")
    network.name = "isolated-net"
    spec = project_spec(tmp_path)
    snapshot = snapshot_project(spec)
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)

    container, image = manager.start_project(network, spec, snapshot)

    assert container is runtime
    assert image.startswith("purplebox-clone-cache:")
    client.images.get.assert_called_once_with(spec.image)
    create_stage, create_runtime = client.containers.create.call_args_list
    assert create_stage.kwargs["network_mode"] == "none"
    assert create_stage.kwargs["entrypoint"] == []
    assert create_stage.kwargs["healthcheck"] == {"test": ["NONE"]}
    assert create_runtime.kwargs["command"] == list(spec.command)
    assert create_runtime.kwargs["working_dir"] == "/workspace"
    assert create_runtime.kwargs["read_only"] is True
    assert create_runtime.kwargs["entrypoint"] == []
    assert create_runtime.kwargs["healthcheck"] == {"test": ["NONE"]}
    assert not ({"ports", "volumes", "privileged", "devices"} & create_runtime.kwargs.keys())
    runtime.start.assert_called_once()


def test_project_probe_has_separate_bounded_output_and_timeout(tmp_path):
    client, stage, runtime = MagicMock(), MagicMock(), MagicMock()
    client.images.get.return_value.attrs = {"Config": {"Env": ["PATH=/usr/bin"], "Volumes": None}}
    client.containers.create.side_effect = [stage, runtime]
    stage.put_archive.return_value = True
    runtime.wait.side_effect = TimeoutError()
    runtime.logs.side_effect = lambda **kwargs: b"out" if kwargs["stdout"] else b"err"
    spec = project_spec(tmp_path)
    snapshot = snapshot_project(spec)
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)

    result = manager.run_project_check(
        MagicMock(name="network"), spec, snapshot, script="raise SystemExit(0)"
    )

    assert result.timed_out is True and result.exit_code is None
    assert result.stdout == "out" and result.stderr == "err"
    runtime.remove.assert_called_once_with(force=True)
    create_stage, create_runtime = client.containers.create.call_args_list
    assert create_stage.args[0] == "purplebox-verifier-base:latest"
    assert create_runtime.kwargs["command"][:5] == ["python3", "-I", "-B", "-u", "-c"]
    assert "sys.path.append('/workspace')" in create_runtime.kwargs["command"][5]
    assert create_runtime.kwargs["working_dir"] == "/workspace"
    assert create_runtime.kwargs["read_only"] is True
    assert create_runtime.kwargs["networking_config"]


@pytest.mark.parametrize(
    "image_config,match",
    [
        ({"Volumes": {"/data": {}}}, "declares volumes"),
        ({"Env": ["PATH=/usr/bin", "API_TOKEN=embedded"]}, "secret-like"),
    ],
)
def test_project_image_rejects_host_volumes_and_embedded_secrets(image_config, match):
    client = MagicMock()
    client.images.get.return_value.attrs = {"Config": image_config}
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)
    with pytest.raises(SandboxError, match=match):
        manager._require_preloaded_image("local/project:latest")
    client.containers.create.assert_not_called()
