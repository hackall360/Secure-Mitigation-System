# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Bounded, immutable intake for arbitrary local source repositories."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from modules.core.scan_profiles import SCAN_PROFILES

if TYPE_CHECKING:
    from modules.core.config import PurpleBoxConfig

DEFAULT_TARGET_IMAGE = "purplebox-target-base:latest"
DEFAULT_CONTEXT_BUDGET = 32_768
MIN_CONTEXT_BUDGET = 1_024
MAX_CONTEXT_BUDGET = 131_072
MAX_PROJECT_FILES = 4096
MAX_PROJECT_BYTES = 32 * 1024 * 1024
MAX_PROJECT_FILE_BYTES = 1024 * 1024

_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "bower_components",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "target",
        "vendor",
        "venv",
    }
)
_SECRET_FILENAMES = frozenset(
    {
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "id_dsa",
        "id_ed25519",
        "id_ecdsa",
        "id_rsa",
        "known_hosts",
        "secrets.json",
    }
)
_SECRET_SUFFIXES = (".jks", ".key", ".keystore", ".p12", ".pem", ".pfx")
_IMAGE_PATTERN = re.compile(
    r"(?:[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?/)*"
    r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[A-Za-z0-9][A-Za-z0-9._-]{0,127})?"
    r"(?:@sha256:[0-9a-f]{64})?"
)


class ProjectSpec(BaseModel):
    """Validated execution contract for one local project."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: Path
    image: str = DEFAULT_TARGET_IMAGE
    command: list[str] = Field(min_length=1, max_length=64)
    test_command: list[str] = Field(min_length=1, max_length=64)
    contract: str = Field(min_length=1, max_length=32_768)
    scan_profile: str = "custom"
    cycles: int = Field(default=1, ge=1, le=20)
    red_agents: int = Field(default=5, ge=1, le=12)
    blue_agents: int = Field(default=5, ge=1, le=12)
    context_budget: int = Field(
        default=DEFAULT_CONTEXT_BUDGET,
        ge=MIN_CONTEXT_BUDGET,
        le=MAX_CONTEXT_BUDGET,
    )
    allow_remote_inference: bool = False

    @model_validator(mode="before")
    @classmethod
    def _apply_scan_profile(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        profile_key = data.get("scan_profile", "custom")
        if profile_key == "custom":
            return data
        if not isinstance(profile_key, str) or profile_key not in SCAN_PROFILES:
            raise ValueError(f"Unknown scan profile: {profile_key!r}.")
        profile_cycles = SCAN_PROFILES[profile_key].cycles
        if "cycles" in data:
            explicit_cycles = data["cycles"]
            if type(explicit_cycles) is not int or explicit_cycles != profile_cycles:
                raise ValueError(
                    f"Scan profile {profile_key!r} requires integer {profile_cycles} cycles; "
                    "omit cycles or provide the matching value."
                )
        data["cycles"] = profile_cycles
        return data

    @field_validator("path", mode="before")
    @classmethod
    def _path_from_local_string(cls, value: object) -> Path:
        if isinstance(value, Path):
            return value
        if isinstance(value, str) and value and "\x00" not in value:
            return Path(value)
        raise ValueError("path must be a non-empty local filesystem path")

    @field_validator("path")
    @classmethod
    def _absolute_directory(cls, value: Path) -> Path:
        path = value.expanduser().absolute()
        for component in (path, *path.parents):
            if component.is_symlink():
                raise ValueError("project root and its ancestors must not be symbolic links")
        if not path.is_dir():
            raise ValueError("project path must be an existing directory")
        return path

    @field_validator("image")
    @classmethod
    def _safe_image_name(cls, value: str) -> str:
        if len(value) > 255 or _IMAGE_PATTERN.fullmatch(value) is None:
            raise ValueError("image must be a valid explicit Docker image reference")
        return value

    @field_validator("command", "test_command")
    @classmethod
    def _safe_argv(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 4096 or "\x00" in item for item in value):
            raise ValueError("command arguments must be non-empty, NUL-free strings")
        return value

    @classmethod
    def with_config_defaults(cls, config: PurpleBoxConfig, **values: object) -> ProjectSpec:
        """Build a spec whose omitted image follows the active application config."""
        values.setdefault("image", config.target_base_image)
        return cls.model_validate(values)


@dataclass(frozen=True)
class ProjectFileMetadata:
    size: int
    mode: int

    @property
    def executable(self) -> bool:
        return bool(self.mode & 0o111)


@dataclass(frozen=True)
class ProjectSnapshot:
    files: Mapping[str, bytes]
    metadata: Mapping[str, ProjectFileMetadata]
    skipped: Mapping[str, str]
    binary_files: tuple[str, ...]
    digest: str
    total_bytes: int


_SECRET_CONTENT_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[prous]_[A-Za-z0-9_]{36,}\b"),
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b"),
    re.compile(r"\bsk-ant-[0-9a-zA-Z-_]{20,}\b"),
]


def _contains_secret_material(content: bytes) -> bool:
    """Detect inline secret material in UTF-8 decodable files."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    # Quick pre-filter to avoid regex on every file.
    if not any(
        token in text for token in ("PRIVATE KEY", "AKIA", "ASIA", "gh", "xox", "sk_live", "sk-ant")
    ):
        # Still check BEGIN pattern which contains PRIVATE KEY; already covered.
        return False
    return any(pattern.search(text) for pattern in _SECRET_CONTENT_PATTERNS)


def _is_secret_file(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered == ".env"
        or lowered.startswith(".env.")
        or lowered in _SECRET_FILENAMES
        or lowered.endswith(_SECRET_SUFFIXES)
    )


def _validate_relative_path(path: str) -> PurePosixPath:
    relative = PurePosixPath(path)
    if (
        not path
        or relative.is_absolute()
        or path != relative.as_posix()
        or any(part in ("", ".", "..") for part in relative.parts)
        or "\\" in path
    ):
        raise ValueError(f"unsafe project snapshot path: {path!r}")
    return relative


def _snapshot_digest(
    files: Mapping[str, bytes], metadata: Mapping[str, ProjectFileMetadata]
) -> str:
    digest = hashlib.sha256()
    digest.update(b"purplebox-project-snapshot-v1\0")
    for path in sorted(files):
        encoded_path = path.encode("utf-8")
        content = files[path]
        mode = metadata[path].mode
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(mode.to_bytes(2, "big"))
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _make_snapshot(
    files: Mapping[str, bytes],
    metadata: Mapping[str, ProjectFileMetadata],
    skipped: Mapping[str, str] | None = None,
) -> ProjectSnapshot:
    frozen_files = MappingProxyType(dict(files))
    frozen_metadata = MappingProxyType(dict(metadata))
    frozen_skipped = MappingProxyType(dict(skipped or {}))
    binary_files = tuple(
        path
        for path, content in sorted(frozen_files.items())
        if b"\x00" in content[:8192] or _cannot_decode_utf8(content)
    )
    return ProjectSnapshot(
        files=frozen_files,
        metadata=frozen_metadata,
        skipped=frozen_skipped,
        binary_files=binary_files,
        digest=_snapshot_digest(frozen_files, frozen_metadata),
        total_bytes=sum(len(content) for content in frozen_files.values()),
    )


def _cannot_decode_utf8(content: bytes) -> bool:
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _read_regular_file(path: Path, expected: os.stat_result, max_file_bytes: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        actual = os.fstat(descriptor)
        if not stat.S_ISREG(actual.st_mode):
            raise ValueError(f"project entry is not a regular file: {path}")
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise ValueError(f"project file changed during snapshot: {path}")
        if actual.st_size > max_file_bytes:
            raise ValueError(f"project file exceeds {max_file_bytes} bytes: {path}")
        with os.fdopen(os.dup(descriptor), "rb") as source:
            content = source.read(max_file_bytes + 1)
        if len(content) > max_file_bytes:
            raise ValueError(f"project file exceeds {max_file_bytes} bytes: {path}")
        after = os.fstat(descriptor)
        if (after.st_size, after.st_mtime_ns) != (actual.st_size, actual.st_mtime_ns):
            raise ValueError(f"project file changed during snapshot: {path}")
        return content
    finally:
        os.close(descriptor)


def snapshot_project(
    spec: ProjectSpec,
    *,
    max_files: int = MAX_PROJECT_FILES,
    max_total_bytes: int = MAX_PROJECT_BYTES,
    max_file_bytes: int = MAX_PROJECT_FILE_BYTES,
) -> ProjectSnapshot:
    """Copy a local tree into a deterministic bounded in-memory manifest."""
    if max_files < 1 or max_total_bytes < 1 or max_file_bytes < 1:
        raise ValueError("snapshot limits must be positive")

    files: dict[str, bytes] = {}
    metadata: dict[str, ProjectFileMetadata] = {}
    skipped: dict[str, str] = {}
    root = spec.path

    def visit(directory: Path, relative_directory: PurePosixPath) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise ValueError(f"cannot read project directory: {directory}") from exc
        for entry in entries:
            relative = relative_directory / entry.name
            relative_text = relative.as_posix()
            try:
                if entry.is_symlink():
                    raise ValueError(f"symbolic links are not allowed: {relative_text}")
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ValueError(f"cannot inspect project entry: {relative_text}") from exc

            if stat.S_ISDIR(entry_stat.st_mode):
                if entry.name.lower() in _EXCLUDED_DIRECTORIES:
                    skipped[relative_text] = (
                        "version-control, dependency, build, or cache directory"
                    )
                else:
                    visit(Path(entry.path), relative)
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                raise ValueError(f"special files are not allowed: {relative_text}")
            if _is_secret_file(entry.name):
                skipped[relative_text] = "secret or credential filename"
                continue

            _validate_relative_path(relative_text)
            if len(files) >= max_files:
                raise ValueError(f"project contains more than {max_files} included files")
            content = _read_regular_file(Path(entry.path), entry_stat, max_file_bytes)
            if _contains_secret_material(content):
                skipped[relative_text] = "secret or credential content pattern"
                continue
            if sum(len(item) for item in files.values()) + len(content) > max_total_bytes:
                raise ValueError(f"project snapshot exceeds {max_total_bytes} bytes")
            mode = 0o755 if entry_stat.st_mode & 0o111 else 0o644
            files[relative_text] = content
            metadata[relative_text] = ProjectFileMetadata(size=len(content), mode=mode)

    visit(root, PurePosixPath())
    if not files:
        raise ValueError("project has no included regular source files")
    return _make_snapshot(files, metadata, skipped)


def replace_snapshot_files(
    snapshot: ProjectSnapshot,
    replacements: Mapping[str, bytes | str],
    *,
    max_total_bytes: int = MAX_PROJECT_BYTES,
    max_file_bytes: int = MAX_PROJECT_FILE_BYTES,
) -> ProjectSnapshot:
    """Return a new bounded snapshot after replacing existing manifest paths only."""
    if not replacements:
        return snapshot
    files = dict(snapshot.files)
    metadata = dict(snapshot.metadata)
    for path, replacement in replacements.items():
        _validate_relative_path(path)
        if path not in files:
            raise ValueError(f"replacement path is not in the original snapshot: {path}")
        if not isinstance(replacement, (bytes, str)):
            raise TypeError("replacement content must be bytes or UTF-8 text")
        content = replacement.encode("utf-8") if isinstance(replacement, str) else replacement
        if len(content) > max_file_bytes:
            raise ValueError(f"replacement exceeds {max_file_bytes} bytes: {path}")
        files[path] = content
        metadata[path] = ProjectFileMetadata(size=len(content), mode=metadata[path].mode)
    if sum(len(content) for content in files.values()) > max_total_bytes:
        raise ValueError(f"project snapshot exceeds {max_total_bytes} bytes")
    return _make_snapshot(files, metadata, snapshot.skipped)
