# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Project snapshot types + staging budgets (core layer, C2).

Sibling of docker_manager: the tar builders type-check snapshots, so the
types live DOWN here, not in services (which owns intake machinery +
config coupling). services.projects re-exports every name (contract
preserved for all existing importers).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from modules.core.scan_profiles import SCAN_PROFILES

if TYPE_CHECKING:
    from modules.core.config import PurpleBoxConfig

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


DEFAULT_TARGET_IMAGE = "purplebox-target-base:latest"
DEFAULT_CONTEXT_BUDGET = 32_768
MIN_CONTEXT_BUDGET = 1_024
MAX_CONTEXT_BUDGET = 131_072
MAX_PROJECT_FILES = 4096
MAX_PROJECT_BYTES = 32 * 1024 * 1024
MAX_PROJECT_FILE_BYTES = 1024 * 1024
#: Compiled-binary blob cap mirrored from services.binary_intake (same wire
#: value; staging-side name so core never imports services for a number).
MAX_BINARY_BYTES = 8 * 1024 * 1024


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
