# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Environment configuration. Loading the UI never requires an inference key."""

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """An invalid setting prevents a real scan from starting."""


@dataclass(frozen=True)
class PurpleBoxConfig:
    meta_api_key: str = field(default="", repr=False)
    meta_base_url: str = "https://inference.baseten.co/v1"
    red_team_model: str = "meta-models/muse-spark-open-1026"
    blue_team_model: str = "meta-models/muse-spark-open-1026"
    target_base_image: str = "purplebox-target-base:latest"
    verifier_base_image: str = "purplebox-verifier-base:latest"
    clone_repo_prefix: str = "purplebox-clone-cache"
    container_mem_limit: str = "256m"
    container_cpu_nano: int = 500_000_000
    network_prefix: str = "purplebox_isolated_net"
    api_timeout_seconds: float = 90.0
    verifier_timeout_seconds: int = 20
    docker_timeout_seconds: int = 30
    max_source_bytes: int = 65_536

    def validate(self) -> None:
        url = urlsplit(self.meta_base_url)
        hostname = url.hostname or ""
        allowed = hostname == "api.meta.ai" or any(
            hostname.endswith(suffix) for suffix in (".baseten.co", ".api.baseten.co", ".modal.run")
        )
        if (
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
        if not 1 <= self.api_timeout_seconds <= 300:
            raise ConfigurationError("META_MUSE_TIMEOUT_SECONDS must be between 1 and 300.")
        if not 1 <= self.verifier_timeout_seconds <= 120:
            raise ConfigurationError(
                "PURPLEBOX_VERIFIER_TIMEOUT_SECONDS must be between 1 and 120."
            )


def load_config() -> PurpleBoxConfig:
    try:
        config = PurpleBoxConfig(
            meta_api_key=os.getenv("META_MUSE_API_KEY", "").strip(),
            meta_base_url=os.getenv("META_MUSE_BASE_URL", "https://inference.baseten.co/v1")
            .strip()
            .rstrip("/"),
            red_team_model=os.getenv(
                "META_MUSE_RED_MODEL", "meta-models/muse-spark-open-1026"
            ).strip(),
            blue_team_model=os.getenv(
                "META_MUSE_BLUE_MODEL", "meta-models/muse-spark-open-1026"
            ).strip(),
            api_timeout_seconds=float(os.getenv("META_MUSE_TIMEOUT_SECONDS", "90")),
            verifier_timeout_seconds=int(os.getenv("PURPLEBOX_VERIFIER_TIMEOUT_SECONDS", "20")),
        )
        config.validate()
        return config
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc


def require_api_key(config: PurpleBoxConfig) -> None:
    config.validate()
    if not config.meta_api_key:
        raise ConfigurationError(
            "META_MUSE_API_KEY is required for scans. PurpleBox uses Meta Muse only."
        )
