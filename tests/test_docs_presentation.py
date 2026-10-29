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
    assert "$150" in text


def test_readme_links_architecture():
    assert "docs/ARCHITECTURE.md" in README.read_text(encoding="utf-8")


def test_architecture_doc_holds_dense_specs():
    text = ARCH.read_text(encoding="utf-8")
    for marker in (
        "Wave 2 (SPEC 14.8)",
        "Wave 5 (SPEC 14.9)",
        "Frozen-pool mutation inputs",
        "Verdict receipts",
    ):
        assert marker in text, marker
