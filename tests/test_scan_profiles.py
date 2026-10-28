# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Scan-intensity profile, focus, and ProjectSpec compatibility contracts."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
from config import PurpleBoxConfig
from projects import ProjectSpec
from scan_profiles import SCAN_PROFILES, ScanProfile, focus_for_cycle

EXPECTED_CYCLES = {
    "extra_light": 1,
    "light": 3,
    "medium": 5,
    "heavy": 8,
    "super_heavy": 12,
    "ultra_heavy": 12,
}


def project_values(tmp_path, **overrides):
    values = {
        "path": str(tmp_path),
        "command": ["python3", "app.py"],
        "test_command": ["python3", "-m", "pytest"],
        "contract": "Preserve the public API.",
    }
    values.update(overrides)
    return values


def test_named_scan_profiles_have_stable_values_and_health_metadata():
    assert {key: profile.cycles for key, profile in SCAN_PROFILES.items()} == EXPECTED_CYCLES
    assert all(isinstance(profile, ScanProfile) for profile in SCAN_PROFILES.values())
    assert all(
        profile.key == key and profile.label and profile.description
        for key, profile in SCAN_PROFILES.items()
    )

    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        payload = client.get("/api/health").json()
    assert {
        profile["key"]: profile["cycles"] for profile in payload["scan_profiles"]
    } == EXPECTED_CYCLES


def test_focus_is_deterministic_cumulative_and_bounded_per_logical_round():
    first = focus_for_cycle("extra_light", 1)
    second = focus_for_cycle("extra_light", 2)
    assert isinstance(first, tuple)
    assert second[:-1] == first
    assert any("server-side input validation" in item for item in first)
    assert any("injection" in item and "output encoding" in item for item in first)
    assert any("file, path, and upload" in item for item in first)
    assert any("configuration" in item for item in first)

    penultimate = focus_for_cycle("super_heavy", 23)
    final = focus_for_cycle("super_heavy", 24)
    assert final[:-1] == penultimate
    assert "adversarial synthesis" in final[-1]
    assert not any("automatic discovery" in item for item in final)
    ultra_first = focus_for_cycle("ultra_heavy", 1)
    ultra_final = focus_for_cycle("ultra_heavy", 24)
    assert any("bounded automatic discovery" in item for item in ultra_first)
    assert ultra_final[: len(ultra_first)] == ultra_first

    for profile_key, cycles in EXPECTED_CYCLES.items():
        start = focus_for_cycle(profile_key, 1)
        end = focus_for_cycle(profile_key, cycles * 2)
        assert len(end) >= len(start)
        with pytest.raises(ValueError):
            focus_for_cycle(profile_key, cycles * 2 + 1)
    for bad_round in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            focus_for_cycle("medium", bad_round)
    with pytest.raises(ValueError):
        focus_for_cycle("custom", 1)
    with pytest.raises(ValueError):
        focus_for_cycle("unknown", 1)


def test_project_spec_preserves_custom_clients_and_derives_named_cycles(tmp_path):
    legacy = ProjectSpec.model_validate(project_values(tmp_path, cycles=7))
    assert legacy.scan_profile == "custom"
    assert legacy.cycles == 7
    assert legacy.red_agents == legacy.blue_agents == 5

    defaulted = ProjectSpec.model_validate(project_values(tmp_path))
    assert defaulted.scan_profile == "custom"
    assert defaulted.cycles == 1

    named = ProjectSpec.model_validate(
        project_values(tmp_path, scan_profile="heavy", red_agents=7, blue_agents=6)
    )
    assert named.scan_profile == "heavy"
    assert named.cycles == 8
    assert named.red_agents == 7
    assert named.blue_agents == 6

    matching = ProjectSpec.model_validate(project_values(tmp_path, scan_profile="light", cycles=3))
    assert matching.cycles == 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"scan_profile": "medium", "cycles": 3},
        {"scan_profile": "extra_light", "cycles": True},
        {"scan_profile": "extra_light", "cycles": 1.0},
        {"scan_profile": "unknown"},
        {"red_agents": 0},
        {"red_agents": 13},
        {"blue_agents": 0},
        {"blue_agents": 13},
    ],
)
def test_project_spec_rejects_profile_conflicts_and_invalid_team_sizes(tmp_path, overrides):
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(project_values(tmp_path, **overrides))
