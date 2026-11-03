# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
# Core gap-fill (verification sweep vcore): uncovered pure branches.
"""RED-first: each test targets lines no existing test executes (verify_cov gaps).

pricing.total_tokens / pricing unknown-model (lines 48, 61); config accept/reject
branches (local URL, mem/cpu/image/name/scanner/max-bytes/require-key); 
project_models non-dict/symlink/mode guards; scan_profiles ultra_heavy derivation.
"""

import pytest


def test_scan_usage_total_tokens_sums_prompt_plus_completion():
    from modules.core.pricing import CallUsage, ScanUsage

    usage = ScanUsage(
        calls=[
            CallUsage(role="red", model="m", prompt_tokens=100, completion_tokens=50),
            CallUsage(role="blue", model="m", prompt_tokens=7, completion_tokens=3),
        ]
    )
    assert usage.total_tokens == 160
    assert ScanUsage().total_tokens == 0


def test_estimate_cost_unknown_model_returns_none():
    from modules.core.pricing import estimate_cost, usage_from_response

    assert estimate_cost("gpt-4-nope", 1_000, 0, 500) is None
    call = usage_from_response(
        "red", "gpt-4-nope", {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}, 1.0
    )
    assert call.cost_usd is None
    assert estimate_cost("muse-spark-1.3", -5, -5, -5) == 0.0


def test_config_rejects_local_non_loopback_and_bad_modes():
    from dataclasses import replace

    from modules.core.config import ConfigurationError, PurpleBoxConfig

    with pytest.raises(ConfigurationError):
        replace(
            PurpleBoxConfig(),
            inference_mode="local",
            meta_base_url="https://example.com/v1",
        ).validate()
    with pytest.raises(ConfigurationError):
        replace(PurpleBoxConfig(), inference_mode="cloud").validate()
    with pytest.raises(ConfigurationError):
        replace(PurpleBoxConfig(), observability_mode="staging").validate()


def test_config_rejects_bad_numeric_and_docker_name_bounds():
    from dataclasses import replace

    from modules.core.config import ConfigurationError, PurpleBoxConfig

    for kw in (
        {"verifier_timeout_seconds": 0},
        {"docker_timeout_seconds": 601},
        {"api_timeout_seconds": 301},
        {"container_cpu_nano": 0},
        {"container_mem_limit": "10x"},
        {"target_base_image": ""},
        {"clone_repo_prefix": "bad prefix!"},
        {"research_scanners": ("trivy", "trivy")},
        {"research_scanners": ("trivy", "grype")},
        {"max_source_bytes": 1023},
    ):
        with pytest.raises(ConfigurationError):
            replace(PurpleBoxConfig(), **kw).validate()


def test_local_config_needs_no_api_key_but_hosted_does():
    from dataclasses import replace

    from modules.core.config import ConfigurationError, PurpleBoxConfig, require_api_key

    local = replace(
        PurpleBoxConfig(),
        inference_mode="local",
        meta_base_url="http://127.0.0.1:8080",
    )
    local.validate()
    require_api_key(local)
    with pytest.raises(ConfigurationError, match="META_MUSE_API_KEY"):
        require_api_key(PurpleBoxConfig())


def test_project_models_reject_nondict_symlink_and_bad_fields(tmp_path):
    import os

    from pydantic import ValidationError

    from modules.core.project_models import ProjectFileMetadata, ProjectSpec

    with pytest.raises(ValidationError):
        ProjectSpec.model_validate("custom")
    assert ProjectFileMetadata(size=1, mode=0o100755).executable is True
    assert ProjectFileMetadata(size=1, mode=0o100644).executable is False
    link = tmp_path / "lnk"
    os.symlink("/etc", link)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(
            {
                "path": str(link),
                "command": ["python3", "app.py"],
                "test_command": ["pytest"],
                "contract": "c",
            }
        )
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(
            {
                "path": str(tmp_path),
                "command": ["python3", "app.py"],
                "test_command": ["pytest"],
                "contract": "c",
                "image": "bad image!!",
            }
        )
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(
            {
                "path": str(tmp_path),
                "command": [""],
                "test_command": ["pytest"],
                "contract": "c",
            }
        )


def test_scan_profiles_ultra_heavy_derivation_and_image_guard(tmp_path):
    from pydantic import ValidationError

    from modules.core.project_models import ProjectSpec
    from modules.core.registry import TARGETS_REGISTRY
    from modules.core.scan_profiles import SCAN_PROFILES, focus_for_cycle

    light1 = focus_for_cycle("light", 1)
    assert light1[0].startswith("architecture, assets")
    ultra1 = focus_for_cycle("ultra_heavy", 1)
    assert any("bounded automatic discovery" in item for item in ultra1)
    ultra_max = focus_for_cycle("ultra_heavy", SCAN_PROFILES["ultra_heavy"].cycles * 2)
    assert ultra_max[: len(ultra1)] == ultra1
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(
            {
                "path": str(tmp_path),
                "command": ["echo"],
                "test_command": ["x"],
                "contract": "c",
                "image": "x" * 256,
            }
        )
    assert "rawUserId" in TARGETS_REGISTRY["node_query_sink"].read_source()
