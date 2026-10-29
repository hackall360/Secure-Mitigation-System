# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Resource-scoped Docker execution. Never run fixture or model code on the host."""

import hashlib
import io
import re
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from docker.errors import DockerException, ImageNotFound, NotFound
from docker.types import LogConfig, Ulimit
from requests.exceptions import ReadTimeout

import docker
from modules.core.checks import validate_verifier_script
from modules.core.config import PurpleBoxConfig
from modules.core.registry import BASE_DIR, Target
from modules.services.projects import (
    MAX_PROJECT_BYTES,
    MAX_PROJECT_FILE_BYTES,
    MAX_PROJECT_FILES,
    ProjectSnapshot,
    ProjectSpec,
)


class SandboxError(RuntimeError):
    """Docker setup, execution, or cleanup failed."""


# Wave 8 item 8 (llama): supply-chain pin. Digest verified offline via
# `docker inspect python:3.12-alpine3.22` (RepoDigests) on 2026-10-29; both
# Dockerfiles and both build/ensure paths below must use this exact reference.
PINNED_PYTHON_BASE = (
    "python:3.12-alpine3.22@sha256:a190708a2dec1bd18b1decb539f8e8f5407abaa9bf39cacda583f7f8c11db322"
)


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


def _assert_dockerfiles_pinned() -> None:
    """Fail closed if any Dockerfile drifts off the pinned digest base."""
    for filename in ("Dockerfile.target", "Dockerfile.verifier", "Dockerfile.binary"):
        content = (BASE_DIR / "docker" / filename).read_text(encoding="utf-8")
        if PINNED_PYTHON_BASE not in content:
            raise SandboxError(
                f"{filename} is not pinned to {PINNED_PYTHON_BASE}; refusing to build."
            )


def build_base_images(config: PurpleBoxConfig, *, client=None) -> list[str]:
    """Rebuild base images unconditionally, e.g. after a Dockerfile change."""
    _assert_dockerfiles_pinned()
    client = client if client is not None else docker.from_env(timeout=600)
    built = []
    for tag, filename in (
        (config.target_base_image, "Dockerfile.target"),
        (config.verifier_base_image, "Dockerfile.verifier"),
        (config.binary_base_image, "Dockerfile.binary"),
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
    """Remove only Secure Mitigation System session resources left by a crash. Base images are kept."""
    client = client if client is not None else docker.from_env(timeout=60)
    removed = {"containers": 0, "networks": 0, "snapshots": 0}
    label = {"label": "purplebox.session"}
    for container in client.containers.list(all=True, filters=label):
        try:
            container.remove(force=True)
        except NotFound:
            # Reaped between list and remove; already gone, keep sweeping.
            continue
        removed["containers"] += 1
    for network in client.networks.list(filters=label):
        try:
            network.remove()
        except NotFound:
            continue
        removed["networks"] += 1
    for image in client.images.list(name=config.clone_repo_prefix):
        try:
            client.images.remove(image=image.id, force=True)
        except (ImageNotFound, NotFound):
            continue
        removed["snapshots"] += 1
    return removed


class DockerSandboxManager:
    def __init__(self, config: PurpleBoxConfig, *, client=None):
        self.config = config
        self.client = (
            client if client is not None else docker.from_env(timeout=config.docker_timeout_seconds)
        )
        self.session_id = uuid.uuid4().hex
        self.containers: list = []
        self.networks: list = []
        self.images: list[str] = []
        self._snapshot_cache: dict[tuple[str, ...], str] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def ensure_base_images(self) -> None:
        _assert_dockerfiles_pinned()
        self.client.ping()
        for tag, filename in (
            (self.config.target_base_image, "Dockerfile.target"),
            (self.config.verifier_base_image, "Dockerfile.verifier"),
            (self.config.binary_base_image, "Dockerfile.binary"),
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
            "ulimits": [
                Ulimit(name="nofile", soft=256, hard=256),
                Ulimit(name="core", soft=0, hard=0),
            ],
            "ipc_mode": "none",
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
        cache_key = (
            base,
            directory,
            filename,
            hashlib.sha256(content.encode("utf-8")).hexdigest(),
            role,
        )
        if cache_key in self._snapshot_cache:
            return self._snapshot_cache[cache_key]
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
            self._snapshot_cache[cache_key] = image_name
            return image_name
        finally:
            try:
                stage.remove(force=True)
            except NotFound:
                pass
            finally:
                if stage in self.containers:
                    self.containers.remove(stage)

    def _runtime(
        self,
        image: str,
        network,
        role: str,
        command: list[str],
        *,
        aliases: list[str] | None = None,
        clear_entrypoint: bool = False,
        working_dir: str | None = None,
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
        if working_dir is not None:
            options["working_dir"] = working_dir
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
        try:
            previous.remove(force=True)
        except NotFound:
            # Already reaped (cancel/disconnect path removed it); still untrack below.
            pass
        finally:
            if previous in self.containers:
                self.containers.remove(previous)
        return self.start_cloneable_target(network, target, source, base_image=snapshot)

    def run_isolated_verifier(self, network, script: str) -> VerificationResult:
        try:
            validate_verifier_script(script)
        except ValueError as exc:
            raise SandboxError(str(exc)) from exc
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
                try:
                    container.remove(force=True)
                except NotFound:
                    pass
                finally:
                    if container in self.containers:
                        self.containers.remove(container)

    @staticmethod
    def _create_binary_tar(files: list[tuple[str, bytes, int]]) -> bytes:
        """Tar archive for binary staging: strict basenames, capped total."""
        from modules.services.binary_intake import BINARY_MAX_BYTES

        total = sum(len(content) for _, content, _ in files)
        if total > BINARY_MAX_BYTES + 65_536:
            raise ValueError("Binary staging archive exceeds the intake budget.")
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for filename, content, mode in files:
                path = PurePosixPath(filename)
                if (
                    path.is_absolute()
                    or len(path.parts) != 1
                    or filename in (".", "..")
                    or "\\" in filename
                ):
                    raise ValueError("Binary archive names must be simple basenames.")
                entry = tarfile.TarInfo(filename)
                entry.size, entry.mode = len(content), mode
                entry.uid = entry.gid = 10001
                entry.mtime = 0
                archive.addfile(entry, io.BytesIO(content))
        return stream.getvalue()

    def require_binary_image(self) -> None:
        """Fail closed when the binary-analysis base image is missing."""
        self.client.ping()
        try:
            self.client.images.get(self.config.binary_base_image)
        except ImageNotFound as exc:
            raise SandboxError(
                "Binary-analysis base image is missing. Run python main.py --init-images first."
            ) from exc

    def start_binary_harness(self, network, blob: bytes, *, mitigation: str = ""):
        """Stage a binary + trusted harness, start the harness HTTP server.

        The binary is injected into a stopped never-executed staging
        container (network_mode none), committed, then run read-only with
        the harness as PID 1. The binary executes ONLY as a subprocess of
        the trusted harness inside the air-gapped network. Returns
        (container, snapshot); cleanup tracks both.
        """
        harness_source = (BASE_DIR / "docker" / "binary_harness.py").read_text(encoding="utf-8")
        archive = self._create_binary_tar(
            [
                ("target.bin", blob, 0o555),
                ("harness.py", harness_source.encode("utf-8"), 0o444),
                ("mitigation.txt", mitigation.encode("utf-8"), 0o444),
            ]
        )
        stage = self.client.containers.create(
            self.config.binary_base_image,
            command=["true"],
            network_mode="none",
            **self._options("target"),
        )
        self.containers.append(stage)
        try:
            if not stage.put_archive("/workspace", archive):
                raise SandboxError("Docker rejected the binary staging archive.")
            tag = f"{self.session_id}-{uuid.uuid4().hex[:10]}"
            image_name = f"{self.config.clone_repo_prefix}:{tag}"
            self.images.append(image_name)
            stage.commit(repository=self.config.clone_repo_prefix, tag=tag)
        finally:
            try:
                stage.remove(force=True)
            except NotFound:
                pass
            finally:
                if stage in self.containers:
                    self.containers.remove(stage)
        container = self._runtime(
            image_name,
            network,
            "target",
            ["python3", "/workspace/harness.py"],
            aliases=["target-service"],
        )
        ready = container.exec_run(["python3", "-c", READY_SCRIPT])
        if ready.exit_code != 0:
            raise SandboxError(
                "Binary harness did not become ready; the binary may be unexecutable."
            )
        return container, image_name

    def replace_binary_harness(self, previous, snapshot: str, network, *, mitigation: str = ""):
        """Restart the harness on the same snapshot with new mitigation rules."""
        try:
            previous.remove(force=True)
        except NotFound:
            pass
        finally:
            if previous in self.containers:
                self.containers.remove(previous)
        return self.start_binary_harness_from_snapshot(snapshot, network, mitigation=mitigation)

    def start_binary_harness_from_snapshot(self, snapshot: str, network, *, mitigation: str = ""):
        """Restart the harness image with replaced mitigation rules (same binary)."""
        stage = self.client.containers.create(
            snapshot,
            command=["true"],
            network_mode="none",
            **self._options("target"),
        )
        self.containers.append(stage)
        try:
            archive = self._create_binary_tar(
                [("mitigation.txt", mitigation.encode("utf-8"), 0o444)]
            )
            if not stage.put_archive("/workspace", archive):
                raise SandboxError("Docker rejected the mitigation archive.")
            tag = f"{self.session_id}-{uuid.uuid4().hex[:10]}"
            image_name = f"{self.config.clone_repo_prefix}:{tag}"
            self.images.append(image_name)
            stage.commit(repository=self.config.clone_repo_prefix, tag=tag)
        finally:
            try:
                stage.remove(force=True)
            except NotFound:
                pass
            finally:
                if stage in self.containers:
                    self.containers.remove(stage)
        container = self._runtime(
            image_name,
            network,
            "target",
            ["python3", "/workspace/harness.py"],
            aliases=["target-service"],
        )
        ready = container.exec_run(["python3", "-c", READY_SCRIPT])
        if ready.exit_code != 0:
            raise SandboxError("Mitigated binary harness did not become ready.")
        return container, image_name

    def binary_static_profile(self, network, blob: bytes) -> str:
        """Static reversing profile (file/strings/readelf) inside the sandbox.

        Runs in one shot in the binary base image with no network; output is
        bounded text for red-team grounding. The binary never executes here
        (analysis tools only read it).
        """
        script = (
            "import subprocess\n"
            "for cmd in (['file', '/workspace/target.bin'],"
            " ['sh', '-c', 'strings /workspace/target.bin | head -100'],"
            " ['sh', '-c', 'readelf -h -l /workspace/target.bin 2>&1 | head -60']):\n"
            "    try:\n"
            "        out = subprocess.run(cmd, stdout=subprocess.PIPE,"
            " stderr=subprocess.STDOUT, timeout=20)\n"
            "        print('$ ' + ' '.join(cmd[:2]))\n"
            "        print(out.stdout.decode('utf-8', errors='replace')[:4000])\n"
            "    except Exception as exc:\n"
            "        print('profile tool failed: ' + type(exc).__name__)\n"
        )
        archive = self._create_binary_tar(
            [
                ("target.bin", blob, 0o555),
                ("profile.py", script.encode("utf-8"), 0o444),
            ]
        )
        stage = self.client.containers.create(
            self.config.binary_base_image,
            command=["true"],
            network_mode="none",
            **self._options("verifier"),
        )
        self.containers.append(stage)
        try:
            if not stage.put_archive("/workspace", archive):
                raise SandboxError("Docker rejected the binary profile archive.")
            tag = f"{self.session_id}-{uuid.uuid4().hex[:10]}"
            image_name = f"{self.config.clone_repo_prefix}:{tag}"
            self.images.append(image_name)
            stage.commit(repository=self.config.clone_repo_prefix, tag=tag)
        finally:
            try:
                stage.remove(force=True)
            except NotFound:
                pass
            finally:
                if stage in self.containers:
                    self.containers.remove(stage)
        container = None
        try:
            container = self._runtime(
                image_name, network, "verifier", ["python3", "/workspace/profile.py"]
            )
            try:
                status = container.wait(timeout=self.config.verifier_timeout_seconds)
                output = container.logs(tail=100).decode("utf-8", errors="replace")[-16_384:]
                if int(status["StatusCode"]) != 0:
                    raise SandboxError("Static profile run failed; result is inconclusive.")
                return output.strip()
            except Exception as exc:
                raise SandboxError(
                    "Static profile failed or timed out; result is inconclusive."
                ) from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except NotFound:
                    pass
                finally:
                    if container in self.containers:
                        self.containers.remove(container)

    def _require_preloaded_image(self, image: str) -> None:
        try:
            loaded = self.client.images.get(image)
        except ImageNotFound as exc:
            raise SandboxError(
                f"Project image {image!r} is not preloaded; Secure Mitigation System never pulls or builds it."
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
        cache_key = (
            base,
            snapshot.digest,
            role,
            hashlib.sha256((verifier_script or "").encode("utf-8")).hexdigest(),
        )
        if cache_key in self._snapshot_cache:
            return self._snapshot_cache[cache_key]
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
            self._snapshot_cache[cache_key] = image_name
            return image_name
        finally:
            try:
                stage.remove(force=True)
            except NotFound:
                pass
            finally:
                if stage in self.containers:
                    self.containers.remove(stage)

    def start_project(self, network, spec: ProjectSpec, snapshot: ProjectSnapshot):
        """Start one fresh target from a committed in-memory source snapshot."""
        image = self._snapshot_project_image(spec.image, snapshot, "target")
        container = self._runtime(
            image,
            network,
            "target",
            list(spec.command),
            clear_entrypoint=True,
            working_dir="/workspace",
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
                validate_verifier_script(script)
            except ValueError as exc:
                raise SandboxError(str(exc)) from exc
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
            runtime_command = [
                "python3",
                "-I",
                "-B",
                "-u",
                "-c",
                "import runpy, sys; sys.path.append('/workspace'); "
                "runpy.run_path('/verifier/runner.py', run_name='__main__')",
            ]
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
                working_dir="/workspace",
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
                try:
                    container.remove(force=True)
                except NotFound:
                    pass
                finally:
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
        finally:
            # Tracking is per-session: clear it even on failure so a later
            # close (or the fail-closed stale sweep) never re-removes or leaks.
            self.containers.clear()
            self.networks.clear()
            images, self.images = self.images, []
            self._snapshot_cache = {
                key: tag for key, tag in self._snapshot_cache.items() if tag not in images
            }
        if failures:
            raise SandboxError(
                f"Cleanup failed for {', '.join(failures)}. Inspect Docker resources labeled "
                f"purplebox.session={self.session_id}."
            )
