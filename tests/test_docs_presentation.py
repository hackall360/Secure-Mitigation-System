# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first presentation gate for Milestone 1 (hackathon pitch refactor).

The executive README must carry the hook, flowchart, quick start, --ai-demo,
AI narrative, Why-Muse? section, and ARCHITECTURE.md links; dense specs live
in docs/ARCHITECTURE.md. RED until M1 lands.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ARCH = ROOT / "docs" / "ARCHITECTURE.md"
HOOK = (
    "An autonomous purple-team CI/CD pipeline that uses Meta Muse "
    "to write security patches, and air-gapped Docker "
    "to cryptographically prove they work."
)


def test_readme_hook_sentence():
    assert HOOK in README.read_text(encoding="utf-8")


def test_readme_mermaid_flowchart():
    assert "```mermaid" in README.read_text(encoding="utf-8")


def test_readme_quickstart_and_ai_demo():
    text = README.read_text(encoding="utf-8")
    assert "--ai-demo" in text
    assert "--serve" in text


def test_readme_ai_narrative_90_percent():
    assert "~90%" in README.read_text(encoding="utf-8")


def test_readme_why_muse():
    text = README.read_text(encoding="utf-8")
    assert "muse-spark-1.3" in text.lower() or "Spark 1.3" in text
    assert "muse-wonder-1.0" in text.lower() or "Wonder 1.0" in text
    assert "library/core/pricing.py" in text


def test_readme_links_architecture():
    assert "docs/ARCHITECTURE.md" in README.read_text(encoding="utf-8")


def test_architecture_doc_holds_dense_specs():
    text = ARCH.read_text(encoding="utf-8")
    for marker in (
        "Wave 2 (SPEC 14.8)",
        "Wave 5 (SPEC 14.9)",
        "Frozen-pool mutation inputs",
        "Verdict receipts",
        "PURPLEBOX_VAULT_DIR",
        "PURPLEBOX_LOG_RAW_RESPONSES",
    ):
        assert marker in text, marker


def test_readme_v1_sections():
    text = README.read_text(encoding="utf-8")
    for marker in (
        "3-minute demo guide",
        "Competitive differentiation",
        "--mcp",
        "sms_scan_source",
        "sms_verify_receipt",
        "binary_argv_echo",
        "Context compression",
        "Vault recall",
    ):
        assert marker in text, marker


def test_architecture_project_map_paths_exist():
    """L2: every .py path cited in the ARCHITECTURE.md project map must exist on disk.

    The map once cited the pre-rename `modules/...` spelling; `modules/` now
    holds only the `__init__.py` alias shim, so those citations were dead.
    Canonical spelling is `library/...`.
    """
    import re

    text = ARCH.read_text(encoding="utf-8")
    start = text.index("## Project map")
    fence_start = text.index("```text", start)
    fence_end = text.index("```", fence_start + len("```text"))
    block = text[fence_start:fence_end]
    # Only directory-qualified citations (contain a "/"); bare basenames like
    # deep_scan.py / dev.py are description fragments, not path citations.
    paths = re.findall(r"(?<![\w./-])([\w.-]+/[\w./-]*\.py)", block)
    assert paths, "no .py paths found in project map block"
    missing = sorted({p for p in paths if not (ROOT / p).is_file()})
    assert not missing, f"project map cites missing files: {missing}"


def test_readme_version_badge_matches_app():
    import re

    text = README.read_text(encoding="utf-8")
    match = re.search(r"version-([0-9]+\.[0-9]+\.[0-9]+)-blue", text)
    assert match, "version badge missing"
    import main as app_module

    assert match.group(1) == app_module.APP_VERSION


def test_readme_competitor_refusal_names():
    """C1: README names the contest brief's refusing models (grounded)."""

    text = README.read_text(encoding="utf-8")
    for marker in ("Opus 5.5", "Fable 5.1", "Luna 6", "Sol 6.1"):
        assert marker in text, marker


def test_readme_cost_claim_grounded_in_pricing():
    """C2: cost wording points at pricing.py; ungrounded pool figure stays out."""

    text = README.read_text(encoding="utf-8")
    assert "library/core/pricing.py" in text
    assert "$150" not in text
    assert "about a fifth of Wonder per token" not in text


def test_how_it_works_fixture_count_matches_registry():
    """M5: HOW_IT_WORKS names every registry fixture; count == registry size."""

    from library.core.registry import TARGETS_REGISTRY

    text = (ROOT / "docs" / "HOW_IT_WORKS.md").read_text(encoding="utf-8")
    assert "Five bundled targets" in text
    found = [key for key in TARGETS_REGISTRY if key in text]
    assert sorted(found) == sorted(TARGETS_REGISTRY), (
        f"missing: {sorted(set(TARGETS_REGISTRY) - set(found))}"
    )


def test_architecture_fixture_table_covers_registry():
    """M5: ARCHITECTURE.md fixture table has a row per registry key."""

    from library.core.registry import TARGETS_REGISTRY

    text = ARCH.read_text(encoding="utf-8")
    for key in TARGETS_REGISTRY:
        assert key in text, key


def test_cli_image_count_matches_dockerfiles():
    """M6: CLI.md + ARCHITECTURE.md image count == Dockerfiles in docker/."""

    dockerfiles = sorted((ROOT / "docker").glob("Dockerfile.*"))
    assert len(dockerfiles) >= 3, [p.name for p in dockerfiles]
    cli = (ROOT / "docs" / "reference" / "CLI.md").read_text(encoding="utf-8").lower()
    assert "three base images" in cli
    assert "two base images" not in cli and "both base images" not in cli
    assert "three pre-built images" in ARCH.read_text(encoding="utf-8").lower()


def test_tags_app_version_matches_version_py():
    """M7: docs/TAGS.md cites the current APP_VERSION."""

    from library.core.version import APP_VERSION

    text = (ROOT / "docs" / "TAGS.md").read_text(encoding="utf-8")
    assert APP_VERSION in text
    assert '"0.12.0"' not in text


def test_readme_lists_every_mcp_tool():
    """M8: every name in MCP_TOOLS appears in README.md."""

    from library.services.mcp_bridge import MCP_TOOLS

    text = README.read_text(encoding="utf-8")
    names = [tool["name"] for tool in MCP_TOOLS]
    assert len(names) >= 6, names
    missing = [name for name in names if name not in text]
    assert not missing, f"README missing MCP tools: {missing}"


def test_readme_links_technical_breakdown():
    """C3: README links the deep-cut doc; the doc exists with dense sections."""

    text = README.read_text(encoding="utf-8")
    assert "docs/TECHNICAL_BREAKDOWN.md" in text
    breakdown = (ROOT / "docs" / "TECHNICAL_BREAKDOWN.md").read_text(encoding="utf-8")
    for marker in (
        "SWEEP_PASSES",
        "network_mode",
        "PURPLEBOX_VAULT_DIR",
        "verify_receipt",
        "CommsFeed",
    ):
        assert marker in breakdown, marker
