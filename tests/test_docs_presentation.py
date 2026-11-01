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
        "writeLine",
    ):
        assert marker in breakdown, marker
