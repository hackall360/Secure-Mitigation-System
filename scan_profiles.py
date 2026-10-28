# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Named scan-intensity profiles and their cumulative review focus."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScanProfile:
    """A fixed, user-facing scan intensity independent of model selection."""

    key: str
    label: str
    cycles: int
    description: str


SCAN_PROFILES: dict[str, ScanProfile] = {
    "extra_light": ScanProfile(
        "extra_light",
        "Extra light",
        1,
        "One focused cycle for a fast boundary check.",
    ),
    "light": ScanProfile(
        "light",
        "Light",
        3,
        "Three cumulative cycles covering the most common attack surfaces.",
    ),
    "medium": ScanProfile(
        "medium",
        "Medium",
        5,
        "Five cumulative cycles adding data, file, and path boundaries.",
    ),
    "heavy": ScanProfile(
        "heavy",
        "Heavy",
        8,
        "Eight cumulative cycles including network, secrets, and configuration review.",
    ),
    "super_heavy": ScanProfile(
        "super_heavy",
        "Super heavy",
        12,
        "Twelve cumulative cycles for exhaustive structured review.",
    ),
    "ultra_heavy": ScanProfile(
        "ultra_heavy",
        "Ultra heavy",
        12,
        "Twelve cumulative cycles with bounded automatic discovery from the first pass.",
    ),
}

_BASELINE_FOCUS = (
    "architecture, assets, and exposed trust boundaries",
    "untrusted sources, data flow, and security-sensitive sinks",
    "server-side input validation and canonicalization",
    "injection, interpreter boundaries, and output encoding",
    "file, path, and upload handling",
    "configuration and deployment hardening",
)

_EXPANDING_FOCUS = (
    "authentication and session management",
    "authorization and access-control enforcement",
    "deserialization, object construction, and parser safety",
    "network, URL, request-forgery, and redirect boundaries",
    "secrets, sensitive-data exposure, and logging",
    "cryptography, randomness, key management, and certificate validation",
    "error handling and information disclosure",
    "dependencies and software-supply-chain boundaries",
    "business logic and abuse cases",
    "state transitions and workflow bypass",
    "concurrency, races, and time-of-check/time-of-use behavior",
    "transaction integrity, rollback, and cleanup",
    "resource exhaustion and abuse controls",
    "security monitoring and audit integrity",
    "memory safety, integer handling, and boundary conditions",
    "changed trust boundaries and external integrations",
    "security regression and review-coverage gaps",
    "Unicode, encoding, and normalization edge cases",
    "cache behavior, key confusion, and stale security decisions",
    "multi-tenant isolation and cross-account data access",
    "credential, token, and privileged-operation lifecycle",
    "replay, ordering, and temporal security assumptions",
    "cross-component exploit chains and control interactions",
    "adversarial synthesis across residual review gaps",
)

_AUTOMATIC_DISCOVERY = "bounded automatic discovery outside established focus areas"


def focus_for_cycle(profile_key: str, cycle: int) -> tuple[str, ...]:
    """Return the deterministic cumulative focus through one named-profile cycle."""

    try:
        profile = SCAN_PROFILES[profile_key]
    except KeyError as exc:
        raise ValueError(f"Unknown scan profile: {profile_key!r}.") from exc
    max_rounds = profile.cycles * 2
    if not isinstance(cycle, int) or isinstance(cycle, bool) or not 1 <= cycle <= max_rounds:
        raise ValueError(f"Review round for {profile_key!r} must be between 1 and {max_rounds}.")
    if profile_key == "ultra_heavy":
        return (*_BASELINE_FOCUS, _AUTOMATIC_DISCOVERY, *_EXPANDING_FOCUS[:cycle])
    return (*_BASELINE_FOCUS, *_EXPANDING_FOCUS[:cycle])
