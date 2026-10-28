# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Environment configuration. Loading the UI never requires an inference key."""

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

ALLOWED_RESEARCH_SCANNERS = (
    "trivy",
    "grype",
    "osv-scanner",
    "dependency-check",
    "dependency-track",
)

# Docker image tags are name[:tag] with registry-safe characters; anything
# else is rejected before a scan starts so a typo fails fast, not mid-run.
_IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:-]{0,255}$")
# Clone-cache repo and isolated-network prefixes: Docker-safe names only.
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,64}$")
# Docker --memory style: bare bytes or b/k/m/g suffix.
_MEM_LIMIT_RE = re.compile(r"^[0-9]+[bkmgBKMG]?$")


class ConfigurationError(ValueError):
    """An invalid setting prevents a real scan from starting."""


@dataclass(frozen=True)
class PurpleBoxConfig:
    meta_api_key: str = field(default="", repr=False)
    meta_base_url: str = "https://api.meta.ai/v1"
    inference_mode: str = "hosted"
    red_team_model: str = "muse-spark-1.3"
    blue_team_model: str = "muse-wonder-1.0"
    target_base_image: str = "purplebox-target-base:latest"
    verifier_base_image: str = "purplebox-verifier-base:latest"
    clone_repo_prefix: str = "purplebox-clone-cache"
    container_mem_limit: str = "256m"
    container_cpu_nano: int = 500_000_000
    network_prefix: str = "purplebox_isolated_net"
    api_timeout_seconds: float = 180.0
    max_output_tokens: int = 32_768
    reasoning_effort: str = ""
    research_enabled: bool = False
    research_scanners: tuple[str, ...] = ()
    verifier_timeout_seconds: int = 20
    docker_timeout_seconds: int = 30
    # Legacy single-blob cap: superseded by per-call context_budget plumbing
    # (snapshot + Muse payload limits). Kept so older configs still validate.
    max_source_bytes: int = 65_536

    def validate(self) -> None:
        if self.inference_mode not in ("hosted", "local"):
            raise ConfigurationError("PURPLEBOX_INFERENCE_MODE must be hosted or local.")
        url = urlsplit(self.meta_base_url)
        hostname = url.hostname or ""
        allowed = hostname == "api.meta.ai" or any(
            hostname.endswith(suffix) for suffix in (".baseten.co", ".api.baseten.co", ".modal.run")
        )
        local = self.inference_mode == "local"
        if local and (
            url.scheme not in ("http", "https")
            or hostname not in ("127.0.0.1", "::1")
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ConfigurationError(
                "Local Muse inference requires an explicit 127.0.0.1 or [::1] HTTP(S) endpoint."
            )
        if not local and (
            url.scheme != "https"
            or not allowed
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.port not in (None, 443)
        ):
            raise ConfigurationError(
                "META_MUSE_BASE_URL must be an HTTPS Meta API, Baseten, or Modal endpoint "
                "without credentials, query parameters, or a custom port."
            )
        for model in (self.red_team_model, self.blue_team_model):
            # Meta Model API IDs (muse-spark-1.3, muse-wonder-1.0) or the open-weight
            # Muse Spark Open release served by a hosted provider (meta-models/...).
            if not re.fullmatch(
                r"muse-(?:spark|wonder)(?:-[a-z0-9]+(?:\.[0-9]+)*)*"
                r"|meta-models/muse-spark-open(?:-[a-z0-9]+)*",
                model,
            ):
                raise ConfigurationError(
                    "Only Muse Spark/Wonder or meta-models/muse-spark-open IDs are supported. "
                    "Muse Code is a coding agent, not a model ID."
                )
        if not 1_024 <= self.max_output_tokens <= 131_072:
            raise ConfigurationError("META_MUSE_MAX_TOKENS must be between 1024 and 131072.")
        if self.reasoning_effort not in ("", "minimal", "low", "medium", "high", "xhigh", "max"):
            raise ConfigurationError(
                "META_MUSE_REASONING_EFFORT must be minimal, low, medium, high, xhigh, max, or unset."
            )
        if not 1 <= self.api_timeout_seconds <= 300:
            raise ConfigurationError("META_MUSE_TIMEOUT_SECONDS must be between 1 and 300.")
        if not 1 <= self.verifier_timeout_seconds <= 120:
            raise ConfigurationError(
                "PURPLEBOX_VERIFIER_TIMEOUT_SECONDS must be between 1 and 120."
            )
        if not 1 <= self.docker_timeout_seconds <= 600:
            raise ConfigurationError("PURPLEBOX_DOCKER_TIMEOUT_SECONDS must be between 1 and 600.")
        if not 1 <= self.container_cpu_nano <= 64_000_000_000:
            raise ConfigurationError(
                "Container CPU quota must be between 1 and 64000000000 nano CPUs."
            )
        if not _MEM_LIMIT_RE.fullmatch(self.container_mem_limit):
            raise ConfigurationError(
                "Container memory limit must be bare bytes or carry a b/k/m/g suffix."
            )
        for label, image in (
            ("target base image", self.target_base_image),
            ("verifier base image", self.verifier_base_image),
        ):
            if not image or not _IMAGE_RE.fullmatch(image):
                raise ConfigurationError(f"Docker {label} tag is invalid: {image!r}.")
        for label, name in (
            ("clone-cache repo prefix", self.clone_repo_prefix),
            ("isolated network prefix", self.network_prefix),
        ):
            if not _SAFE_NAME_RE.fullmatch(name):
                raise ConfigurationError(f"Docker {label} is invalid: {name!r}.")
        for scanner in self.research_scanners:
            if scanner not in ALLOWED_RESEARCH_SCANNERS:
                raise ConfigurationError(f"Unknown research scanner: {scanner!r}.")
        if len(set(self.research_scanners)) != len(self.research_scanners):
            raise ConfigurationError("Research scanners must not repeat.")
        if self.research_scanners != tuple(sorted(self.research_scanners)):
            raise ConfigurationError("Research scanners must be sorted and unique.")
        if not 1_024 <= self.max_source_bytes <= 1_048_576:
            raise ConfigurationError("max_source_bytes must be between 1024 and 1048576.")


def load_config() -> PurpleBoxConfig:
    try:
        config = PurpleBoxConfig(
            meta_api_key=os.getenv("META_MUSE_API_KEY", "").strip(),
            meta_base_url=os.getenv("META_MUSE_BASE_URL", "https://api.meta.ai/v1")
            .strip()
            .rstrip("/"),
            inference_mode=os.getenv("PURPLEBOX_INFERENCE_MODE", "hosted").strip().lower(),
            red_team_model=os.getenv("META_MUSE_RED_MODEL", "muse-spark-1.3").strip(),
            blue_team_model=os.getenv("META_MUSE_BLUE_MODEL", "muse-wonder-1.0").strip(),
            api_timeout_seconds=float(os.getenv("META_MUSE_TIMEOUT_SECONDS", "180")),
            max_output_tokens=int(os.getenv("META_MUSE_MAX_TOKENS", "32768")),
            reasoning_effort=os.getenv("META_MUSE_REASONING_EFFORT", "").strip().lower(),
            research_enabled=os.getenv("PURPLEBOX_RESEARCH", "off").strip().lower() == "on",
            research_scanners=tuple(
                sorted(
                    {
                        s.strip().lower()
                        for s in os.getenv("PURPLEBOX_RESEARCH_SCANNERS", "").split(",")
                        if s.strip().lower() in ALLOWED_RESEARCH_SCANNERS
                    }
                )
            ),
            verifier_timeout_seconds=int(os.getenv("PURPLEBOX_VERIFIER_TIMEOUT_SECONDS", "20")),
        )
        config.validate()
        return config
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc


def require_api_key(config: PurpleBoxConfig) -> None:
    config.validate()
    if config.inference_mode != "local" and not config.meta_api_key:
        raise ConfigurationError(
            "META_MUSE_API_KEY is required for scans. Secure Mitigation System uses Meta Muse only."
        )
