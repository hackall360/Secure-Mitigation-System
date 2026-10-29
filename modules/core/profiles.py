# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Named model profiles a user may pick per scan.

Only these fixed pairs can be chosen from the dashboard or CLI. A browser can never
send an arbitrary model ID. "custom" means "use the server's configured models"
(META_MUSE_RED_MODEL / META_MUSE_BLUE_MODEL), which is also the default.

Role guide for judges: Muse Spark is the fast triage model (red-team analysis
and verification probe); Muse Wonder is the deep-reasoning model (blue-team
sanitization patch). Economy runs Spark for both roles, balanced runs Spark
for red and Wonder for blue, and quality runs Wonder for both roles.
"""

from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from modules.core.config import PurpleBoxConfig


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    description: str
    red_model: str
    blue_model: str


META_PROFILES: dict[str, Profile] = {
    "economy": Profile(
        "economy",
        "Economy",
        "Muse Spark for red (fast triage) and blue (fast patch). Lowest cost.",
        "muse-spark-1.3",
        "muse-spark-1.3",
    ),
    "balanced": Profile(
        "balanced",
        "Balanced",
        "Spark red triage, Wonder blue patch. Default.",
        "muse-spark-1.3",
        "muse-wonder-1.0",
    ),
    "quality": Profile(
        "quality",
        "Quality",
        "Muse Wonder for red (deep analysis) and blue (deep patch). Highest cost.",
        "muse-wonder-1.0",
        "muse-wonder-1.0",
    ),
}

META_API_HOST = "api.meta.ai"


class ProfileError(ValueError):
    """Unknown profile, or one that this endpoint cannot serve."""


def available_profiles(config: PurpleBoxConfig) -> dict[str, Profile]:
    """Meta profiles only make sense against the Meta Model API."""
    if urlsplit(config.meta_base_url).hostname == META_API_HOST:
        return dict(META_PROFILES)
    return {}


def apply_profile(config: PurpleBoxConfig, key: str | None) -> PurpleBoxConfig:
    if key in (None, "", "custom"):
        return config
    profiles = available_profiles(config)
    if key not in profiles:
        raise ProfileError(f"Unknown or unavailable model profile: {key!r}.")
    profile = profiles[key]
    chosen = replace(config, red_team_model=profile.red_model, blue_team_model=profile.blue_model)
    chosen.validate()
    return chosen


def default_profile(config: PurpleBoxConfig) -> str:
    for key, profile in available_profiles(config).items():
        if (profile.red_model, profile.blue_model) == (
            config.red_team_model,
            config.blue_team_model,
        ):
            return key
    return "custom"
