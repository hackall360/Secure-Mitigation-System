# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Bounded, immutable intake for arbitrary local source repositories."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    pass

from modules.core.project_models import (
    _EXCLUDED_DIRECTORIES,
    _SECRET_CONTENT_PATTERNS,
    _SECRET_FILENAMES,
    _SECRET_SUFFIXES,
    DEFAULT_CONTEXT_BUDGET,
    DEFAULT_TARGET_IMAGE,
    MAX_CONTEXT_BUDGET,
    MAX_PROJECT_BYTES,
    MAX_PROJECT_FILE_BYTES,
    MAX_PROJECT_FILES,
    MIN_CONTEXT_BUDGET,
    ProjectFileMetadata,
    ProjectSnapshot,
    ProjectSpec,
)

__all__ = [
    "DEFAULT_TARGET_IMAGE",
    "DEFAULT_CONTEXT_BUDGET",
    "MIN_CONTEXT_BUDGET",
    "MAX_CONTEXT_BUDGET",
    "MAX_PROJECT_FILES",
    "MAX_PROJECT_BYTES",
    "MAX_PROJECT_FILE_BYTES",
    "ProjectSpec",
    "ProjectFileMetadata",
    "ProjectSnapshot",
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
