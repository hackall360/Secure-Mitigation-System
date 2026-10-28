# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Resource-scoped Docker execution. Never run fixture or model code on the host."""

import io
import re
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from docker.errors import DockerException, ImageNotFound, NotFound
from docker.types import LogConfig
from requests.exceptions import ReadTimeout

import docker
from config import PurpleBoxConfig
from projects import (
    MAX_PROJECT_BYTES,
    MAX_PROJECT_FILE_BYTES,
    MAX_PROJECT_FILES,
    ProjectSnapshot,
    ProjectSpec,
)
from registry import BASE_DIR, Target


class SandboxError(RuntimeError):
    """Docker setup, execution, or cleanup failed."""


@dataclass(frozen=True)
class VerificationResult:
    exit_code: int
    output: str

    @property
    def inconclusive(self) -> bool:
        return self.exit_code not in (0, 1)


@dataclass(frozen=True)
class ProjectCheckResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


READY_SCRIPT = """
import sys, time, urllib.request, urllib.error
for attempt in range(25):
    try:
        urllib.request.urlopen('http://127.0.0.1:8080/', timeout=0.3).close()
        sys.exit(0)
    except urllib.error.HTTPError:
        sys.exit(0)
    except (OSError, urllib.error.URLError):
        time.sleep(0.2)
sys.exit(2)
"""

_SECRET_ENV_NAME = re.compile(
    r"(?:^|_)(?:API_?KEY|AUTH|CREDENTIALS?|PASS(?:WORD|WD)?|PRIVATE_?KEY|SECRET|TOKEN)(?:_|$)",
    re.IGNORECASE,
)


def docker_status(config: PurpleBoxConfig, *, client=None) -> dict:
    """Fast, read-only readiness probe for the dashboard and CLI. Never raises."""
    owned = client is None
    try:
        client = client if client is not None else docker.from_env(timeout=3)
        client.ping()
        missing = []
        for tag in (config.target_base_image, config.verifier_base_image):
            try:
                client.images.get(tag)
            except ImageNotFound:
                missing.append(tag)
        leftovers = len(client.containers.list(all=True, filters={"label": "purplebox.session"}))
        return {
            "state": "ready" if not missing else "images_missing",
            "missing_images": missing,
            "leftover_containers": leftovers,
        }
    except Exception:
        return {"state": "unavailable", "missing_images": [], "leftover_containers": 0}
    finally:
        if owned and client is not None:
            try:
                client.close()
            except Exception:
                pass


def build_base_images(config: PurpleBoxConfig, *, client=None) -> list[str]:
    """Rebuild both base images unconditionally, e.g. after a Dockerfile change."""
    client = client if client is not None else docker.from_env(timeout=600)
    built = []
    for tag, filename in (
        (config.target_base_image, "Dockerfile.target"),
        (config.verifier_base_image, "Dockerfile.verifier"),
    ):
        client.images.build(
            path=str(BASE_DIR / "docker"),
            dockerfile=filename,
            tag=tag,
            rm=True,
            forcerm=True,
            pull=True,
            labels={"purplebox.base": "true"},
            timeout=600,
        )
        built.append(tag)
    return built


def remove_stale_resources(config: PurpleBoxConfig, *, client=None) -> dict:
    """Remove only PurpleBox session resources left by a crash. Base images are kept."""
    client = client if client is not None else docker.from_env(timeout=60)
    removed = {"containers": 0, "networks": 0, "snapshots": 0}
    label = {"label": "purplebox.session"}
    for container in client.containers.list(all=True, filters=label):
        container.remove(force=True)
        removed["containers"] += 1
    for network in client.networks.list(filters=label):
        network.remove()
        removed["networks"] += 1
    for image in client.images.list(name=config.clone_repo_prefix):
        client.images.remove(image=image.id, force=True)
        removed["snapshots"] += 1
    return removed


class DockerSandboxManager:
    def __init__(self, config: PurpleBoxConfig, *, client=None):
        self.config = config
        self.client = (
            client if client is not None else docker.from_env(timeout=config.docker_timeout_seconds)
        )
        self.session_id = uuid.uuid4().hex
        self.containers = []
        self.networks = []
        self.images = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def ensure_base_images(self) -> None:
        self.client.ping()
        for tag, filename in (
            (self.config.target_base_image, "Dockerfile.target"),
            (self.config.verifier_base_image, "Dockerfile.verifier"),
        ):
            try:
                self.client.images.get(tag)
            except ImageNotFound:
                self.client.images.build(
                    path=str(BASE_DIR / "docker"),
                    dockerfile=filename,
                    tag=tag,
                    rm=True,
                    forcerm=True,
                    timeout=600,
                )

    def require_base_images(self) -> None:
        self.client.ping()
        for tag in (self.config.target_base_image, self.config.verifier_base_image):
            try:
                self.client.images.get(tag)
            except ImageNotFound as exc:
                raise SandboxError(
                    "Base images are missing. Run python main.py --init-images first."
                ) from exc

    def _options(self, role: str) -> dict:
        memory = "128m" if role == "verifier" else self.config.container_mem_limit
        return {
            "user": "10001:10001",
            "mem_limit": memory,
            "memswap_limit": memory,
            "nano_cpus": self.config.container_cpu_nano,
            "pids_limit": 32 if role == "verifier" else 64,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "init": True,
            "use_config_proxy": False,
            "environment": {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
            "labels": {"purplebox.session": self.session_id, "purplebox.role": role},
            "log_config": LogConfig(type="json-file", config={"max-size": "1m", "max-file": "1"}),
        }

    @staticmethod
    def _create_tar_bytes(filename: str, content: str) -> bytes:
        path = PurePosixPath(filename)
        if (
            path.is_absolute()
            or len(path.parts) != 1
            or filename in (".", "..")
            or "\\" in filename
        ):
            raise ValueError("Archive filenames must be simple relative basenames.")
        data = content.encode("utf-8")
        if len(data) > 65_536:
            raise ValueError("Archive source exceeds 64 KiB.")
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            entry = tarfile.TarInfo(filename)
            entry.size, entry.mode = len(data), 0o444
            entry.uid = entry.gid = 10001
            entry.mtime = 0
            archive.addfile(entry, io.BytesIO(data))
        return stream.getvalue()

    @staticmethod
    def _create_project_tar(snapshot: ProjectSnapshot) -> bytes:
        if not snapshot.files or len(snapshot.files) > MAX_PROJECT_FILES:
            raise ValueError(
                f"Project snapshot must contain between 1 and {MAX_PROJECT_FILES} files."
            )
        if snapshot.files.keys() != snapshot.metadata.keys():
            raise ValueError("Project snapshot metadata does not match its files.")
        if sum(len(content) for content in snapshot.files.values()) > MAX_PROJECT_BYTES:
            raise ValueError(f"Project snapshot exceeds {MAX_PROJECT_BYTES} bytes.")

        directories: set[PurePosixPath] = set()
        validated: list[tuple[str, bytes, int]] = []
        for filename in sorted(snapshot.files):
            path = PurePosixPath(filename)
            content = snapshot.files[filename]
            metadata = snapshot.metadata[filename]
            if (
                not filename
                or path.is_absolute()
                or filename != path.as_posix()
                or any(part in ("", ".", "..") for part in path.parts)
                or "\\" in filename
            ):
                raise ValueError("Project archive paths must be safe relative POSIX paths.")
            if not isinstance(content, bytes) or len(content) > MAX_PROJECT_FILE_BYTES:
                raise ValueError(
                    f"Project archive files must be bytes no larger than "
                    f"{MAX_PROJECT_FILE_BYTES} bytes."
                )
            if metadata.size != len(content) or metadata.mode not in (0o644, 0o755):
                raise ValueError("Project archive metadata is invalid.")
            parent = path.parent
            while parent != PurePosixPath("."):
                directories.add(parent)
                parent = parent.parent
            validated.append((filename, content, metadata.mode))

        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for directory in sorted(
                directories, key=lambda item: (len(item.parts), item.as_posix())
            ):
                entry = tarfile.TarInfo(directory.as_posix())
                entry.type = tarfile.DIRTYPE
                entry.mode = 0o555
                entry.uid = entry.gid = 10001
                entry.mtime = 0
                archive.addfile(entry)
            for filename, content, mode in validated:
                entry = tarfile.TarInfo(filename)
                entry.size, entry.mode = len(content), mode
                entry.uid = entry.gid = 10001
                entry.mtime = 0
                archive.addfile(entry, io.BytesIO(content))
        return stream.getvalue()

    def create_isolated_network(self):
        network = self.client.networks.create(
            name=f"{self.config.network_prefix}_{self.session_id[:12]}",
            driver="bridge",
            internal=True,
            enable_ipv6=False,
            options={"com.docker.network.bridge.gateway_mode_ipv4": "isolated"},
            labels={"purplebox.session": self.session_id},
        )
        self.networks.append(network)
        return network

    def _snapshot(self, base: str, directory: str, filename: str, content: str, role: str) -> str:
        # Staging containers NEVER start. Injection precedes the read-only runtime.
        # This also avoids put_archive failures on an already read-only root filesystem.
        archive = self._create_tar_bytes(filename, content)
        stage = self.client.containers.create(
            base,
            command=["true"],
            network_mode="none",
            **self._options(role),
        )
        self.containers.append(stage)
        try:
            if not stage.put_archive(directory, archive):
                raise SandboxError("Docker rejected the source archive.")
            tag = f"{self.session_id}-{uuid.uuid4().hex[:10]}"
            image_name = f"{self.config.clone_repo_prefix}:{tag}"
            # Register the tag before commit so cleanup can recover from a timeout.
            self.images.append(image_name)
            stage.commit(repository=self.config.clone_repo_prefix, tag=tag)
            return image_name
        finally:
            stage.remove(force=True)

    def _runtime(
        self,
        image: str,
        network,
        role: str,
        command: list[str],
        *,
        aliases: list[str] | None = None,
        clear_entrypoint: bool = False,
    ):
        if aliases is None:
            aliases = ["target-service"] if role == "target" else []
        endpoints = {
            network.name: self.client.api.create_endpoint_config(
                aliases=aliases,
            )
        }
        options = {
            "command": command,
            "network": network.name,
            "networking_config": endpoints,
            "read_only": True,
            "healthcheck": {"test": ["NONE"]},
            "tmpfs": {"/tmp": "rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001"},
            **self._options(role),
        }
        if clear_entrypoint:
            options["entrypoint"] = []
        container = self.client.containers.create(
            image,
            **options,
        )
        self.containers.append(container)
        container.start()
        return container

    def start_cloneable_target(
        self, network, target: Target, source: str, *, base_image: str | None = None
    ):
        snapshot = self._snapshot(
            base_image or self.config.target_base_image,
            "/workspace",
            target.filename,
            source,
            "target",
        )
        container = self._runtime(snapshot, network, "target", list(target.command))
        ready = container.exec_run(["python3", "-c", READY_SCRIPT])
        if ready.exit_code != 0:
            raise SandboxError(
                "Target did not become ready; patch may contain a syntax or startup error."
            )
        return container, snapshot

    def replace_target(self, previous, snapshot: str, network, target: Target, source: str):
        # Fresh process and immutable filesystem; no pkill or shell command interpolation.
        previous.remove(force=True)
        return self.start_cloneable_target(network, target, source, base_image=snapshot)

    def run_isolated_verifier(self, network, script: str) -> VerificationResult:
        try:
            compile(script, "verify.py", "exec")
        except (SyntaxError, ValueError) as exc:
            raise SandboxError("Verifier is not valid Python.") from exc
        snapshot = self._snapshot(
            self.config.verifier_base_image, "/verifier", "verify.py", script, "verifier"
        )
        container = None
        try:
            container = self._runtime(
                snapshot, network, "verifier", ["python3", "/verifier/runner.py"]
            )
            try:
                status = container.wait(timeout=self.config.verifier_timeout_seconds)
                output = container.logs(tail=100).decode("utf-8", errors="replace")[-16_384:]
                return VerificationResult(int(status["StatusCode"]), output.strip())
            except Exception as exc:
                raise SandboxError(
                    "Verifier failed or exceeded its time limit; result is inconclusive."
                ) from exc
        finally:
            if container is not None:
                container.remove(force=True)

    def _require_preloaded_image(self, image: str) -> None:
        try:
            loaded = self.client.images.get(image)
        except ImageNotFound as exc:
            raise SandboxError(
                f"Project image {image!r} is not preloaded; PurpleBox never pulls or builds it."
            ) from exc
        config = loaded.attrs.get("Config") or {}
        if config.get("Volumes"):
            raise SandboxError(
                f"Project image {image!r} declares volumes, which could create host-side storage."
            )
        inherited_env = config.get("Env") or []
        secret_names = []
        for item in inherited_env:
            name = item.partition("=")[0]
            if _SECRET_ENV_NAME.search(name):
                secret_names.append(name)
        if secret_names:
            raise SandboxError(
                f"Project image {image!r} embeds secret-like environment variables: "
                f"{', '.join(sorted(secret_names))}."
            )

    def _snapshot_project_image(
        self,
        base: str,
        snapshot: ProjectSnapshot,
        role: str,
        *,
        verifier_script: str | None = None,
    ) -> str:
        self._require_preloaded_image(base)
        source_archive = self._create_project_tar(snapshot)
        script_archive = (
            self._create_tar_bytes("verify.py", verifier_script)
            if verifier_script is not None
            else None
        )
        stage = self.client.containers.create(
            base,
            command=["true"],
            network_mode="none",
            entrypoint=[],
            healthcheck={"test": ["NONE"]},
            **self._options(role),
        )
        self.containers.append(stage)
        try:
            if not stage.put_archive("/workspace", source_archive):
                raise SandboxError("Docker rejected the project source archive.")
            if script_archive is not None and not stage.put_archive("/verifier", script_archive):
                raise SandboxError("Docker rejected the verifier archive.")
            tag = f"{self.session_id}-{uuid.uuid4().hex[:10]}"
            image_name = f"{self.config.clone_repo_prefix}:{tag}"
            self.images.append(image_name)
            stage.commit(repository=self.config.clone_repo_prefix, tag=tag)
            return image_name
        finally:
            stage.remove(force=True)

    def start_project(self, network, spec: ProjectSpec, snapshot: ProjectSnapshot):
        """Start one fresh target from a committed in-memory source snapshot."""
        image = self._snapshot_project_image(spec.image, snapshot, "target")
        container = self._runtime(
            image,
            network,
            "target",
            list(spec.command),
            clear_entrypoint=True,
        )
        return container, image

    @staticmethod
    def _bounded_logs(container) -> tuple[str, str]:
        stdout = container.logs(stdout=True, stderr=False, tail=200)
        stderr = container.logs(stdout=False, stderr=True, tail=200)
        return (
            stdout.decode("utf-8", errors="replace")[-16_384:].strip(),
            stderr.decode("utf-8", errors="replace")[-16_384:].strip(),
        )

    def run_project_check(
        self,
        network,
        spec: ProjectSpec,
        snapshot: ProjectSnapshot,
        *,
        command: list[str] | None = None,
        script: str | None = None,
    ) -> ProjectCheckResult:
        """Run a disposable regression command or Python verifier against a snapshot."""
        if command is not None and script is not None:
            raise ValueError("Provide either a project command or a verifier script, not both.")
        if command is None and script is None:
            command = list(spec.test_command)
        if command is not None and not command:
            raise ValueError("Project check command must not be empty.")

        if script is not None:
            try:
                compile(script, "verify.py", "exec")
            except (SyntaxError, ValueError) as exc:
                raise SandboxError("Verifier is not valid Python.") from exc
            image = self._snapshot_project_image(
                self.config.verifier_base_image,
                snapshot,
                "verifier",
                verifier_script=script,
            )
            role = "verifier"
            runtime_command = ["python3", "/verifier/runner.py"]
        else:
            image = self._snapshot_project_image(spec.image, snapshot, "test")
            role = "test"
            runtime_command = list(command or ())

        container = None
        try:
            container = self._runtime(
                image,
                network,
                role,
                runtime_command,
                aliases=[],
                clear_entrypoint=True,
            )
            try:
                status = container.wait(timeout=self.config.verifier_timeout_seconds)
            except (TimeoutError, ReadTimeout):
                stdout, stderr = self._bounded_logs(container)
                return ProjectCheckResult(None, stdout, stderr, timed_out=True)
            except Exception as exc:
                raise SandboxError("Project check failed before producing a result.") from exc
            stdout, stderr = self._bounded_logs(container)
            return ProjectCheckResult(int(status["StatusCode"]), stdout, stderr)
        finally:
            if container is not None:
                container.remove(force=True)
                if container in self.containers:
                    self.containers.remove(container)

    def stop_project(self, container) -> None:
        """Force-remove a project target, including during workflow cancellation."""
        try:
            container.remove(force=True)
        except NotFound:
            pass
        finally:
            if container in self.containers:
                self.containers.remove(container)

    def close(self) -> None:
        failures = []
        for container in reversed(self.containers):
            try:
                container.remove(force=True)
            except NotFound:
                pass
            except Exception:
                failures.append("container")
        for network in reversed(self.networks):
            try:
                network.remove()
            except NotFound:
                pass
            except Exception:
                failures.append("network")
        for image in reversed(self.images):
            try:
                self.client.images.remove(image=image)
            except (ImageNotFound, NotFound):
                pass
            except Exception:
                failures.append("snapshot")
        try:
            self.client.close()
        except DockerException:
            failures.append("client")
        if failures:
            raise SandboxError(
                f"Cleanup failed for {', '.join(failures)}. Inspect Docker resources labeled "
                f"purplebox.session={self.session_id}."
            )
