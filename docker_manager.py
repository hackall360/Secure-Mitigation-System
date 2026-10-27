# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Resource-scoped Docker execution. Never run fixture or model code on the host."""

import io
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from docker.errors import DockerException, ImageNotFound, NotFound
from docker.types import LogConfig

import docker
from config import PurpleBoxConfig
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

    def create_isolated_network(self):
        network = self.client.networks.create(
            name=f"{self.config.network_prefix}_{self.session_id[:12]}",
            driver="bridge",
            internal=True,
            enable_ipv6=False,
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

    def _runtime(self, image: str, network, role: str, command: list[str]):
        endpoints = {
            network.name: self.client.api.create_endpoint_config(
                aliases=["target-service"] if role == "target" else [],
            )
        }
        container = self.client.containers.create(
            image,
            command=command,
            network=network.name,
            networking_config=endpoints,
            read_only=True,
            tmpfs={"/tmp": "rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001"},
            **self._options(role),
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
