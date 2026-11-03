# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: README show-don't-tell (YY8).

The README must SHOW machine output, not tell claims:
- a real offline-scan transcript (4/4 verified lines, pre=0 post=1)
- real pricing numbers from library/core/pricing.py (not adjectives)
- the VerdictReceipt field names a judge can grep
- the LAW 1 ship path as a copy-paste command sequence
Every pin below FAILS on the telling README and PASSES after the refactor.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _text():
    return README.read_text(encoding="utf-8")


def test_readme_shows_real_scan_transcript():
    """Show: at least one verbatim `status=verified pre=0 post=1` line."""
    text = _text()
    assert "status=verified pre=0 post=1" in text, (
        "README must paste real offline_scan output, not describe it"
    )


def test_readme_shows_real_fixture_names_in_transcript():
    """Show: the transcript names real registry fixtures."""
    text = _text()
    for fixture in ("node_query_sink", "php_command_sink"):
        assert fixture in text, f"transcript must name {fixture}"


def test_readme_pricing_shows_numbers_not_adjectives():
    """Show: real per-1M numbers for the red/blue split (from pricing.py)."""
    text = _text()
    # contributor red price + wonder blue price, verbatim from PRICES_PER_MILLION
    assert "0.10" in text, "red contributor input $/1M missing"
    assert "4.00" in text, "blue wonder input $/1M missing"
    assert "20.00" in text, "blue wonder output $/1M missing"


def test_readme_receipt_names_greppable_fields():
    """Show: VerdictReceipt field names a judge can grep in workflow.py."""
    text = _text()
    for field in ("pre_exit_code", "post_exit_code", "regression_passed"):
        assert field in text, f"README must name receipt field {field}"


def test_readme_ship_path_is_copy_paste():
    """Show: the LAW 1 ship path as commands, not prose."""
    text = _text()
    assert "feature/" in text, "ship path must show a feature branch name"
    assert "develop" in text and "main" in text
    # copy-paste push sequence
    assert "git push" in text, "ship path must include the push commands"
