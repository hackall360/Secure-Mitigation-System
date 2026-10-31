# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: multi-step chained sweep pass (chain_links) fail-first tests.

Expected FAIL until modules/workflows/sweep.py gains a chain pass result
type (SweepPassResult with `chain_links` list of {pre_exit, post_exit})
whose `holds` requires BOTH links post==1 and whose `verified` receipt
records both link exit codes. Inconclusive links (exit 2) fail closed.

Benign marker probes only: exit-code semantics, no payloads. FAKE
Muse+sandbox only; never real Docker/Muse.
RED until the chain feature lands (expect ImportError/AttributeError).
"""

import asyncio

from modules.core.config import PurpleBoxConfig
from tests.helpers import FakeFixtureSandbox, silent_emit

TEST_CONFIG = PurpleBoxConfig(meta_api_key="test-key")


class ChainFakeMuse:
    """Red/blue double emitting a benign marker probe per chain link."""

    def __init__(self):
        self.red_calls: list = []
        self.blue_calls = 0
        self.closed = False

    async def run_red_team_pass_analysis(self, pass_id, filename, source, contract=""):
        from modules.core.agents import RedTeamFinding

        self.red_calls.append(pass_id)
        return RedTeamFinding(
            vulnerability_class=f"test chain boundary {pass_id}",
            sink_location=filename,
            analysis_summary="Test-only benign marker.",
            verification_script_python="import sys\nsys.exit(0)",
        )

    async def run_blue_team_sanitizer(
        self, filename, source_code, finding=None, evidence="", contract=""
    ):
        from modules.core.agents import BlueTeamPatch

        self.blue_calls += 1
        patched = source_code.rstrip("\n") + f"\n// chain-guard-{self.blue_calls}\n"
        return BlueTeamPatch(
            sanitization_strategy="Validate IDs",
            diff_summary="Add a guard",
            patched_file_content=patched,
        )

    async def aclose(self):
        self.closed = True


def _run_chain_sweep(codes):
    from modules.workflows.sweep import execute_sweep_scan

    sandbox = FakeFixtureSandbox(codes)
    muse = ChainFakeMuse()
    coro = execute_sweep_scan(
        "node_query_sink",
        silent_emit,
        config=TEST_CONFIG,
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: muse,
    )
    return asyncio.new_event_loop().run_until_complete(coro)


def test_chain_link_type_exists():
    """Chain link result type exists with pre/post exit semantics."""
    from modules.workflows.sweep import ChainLink  # noqa: F401 RED: missing type

    assert ChainLink is not None


def test_chain_holds_requires_both_links_blocked():
    """holds requires BOTH links post==1; single-link success must NOT hold."""
    from modules.workflows.sweep import ChainLink, SweepPassResult

    both_blocked = SweepPassResult(
        pass_id="standard",
        chain_links=[
            ChainLink(pre_exit=0, post_exit=1),
            ChainLink(pre_exit=0, post_exit=1),
        ],
        regression_passed=True,
        receipt={"chain": [(0, 1), (0, 1)]},
    )
    assert both_blocked.holds is True
    single_success = SweepPassResult(
        pass_id="standard",
        chain_links=[
            ChainLink(pre_exit=0, post_exit=1),
            ChainLink(pre_exit=0, post_exit=0),
        ],
        regression_passed=True,
        receipt={"chain": [(0, 1), (0, 0)]},
    )
    assert single_success.holds is False


def test_chain_verified_requires_both_link_receipts():
    """verified requires the chain receipt recording both link exit codes."""
    codes = [0] + [0, 0, 1, 0] * 3
    result = _run_chain_sweep(codes)
    first = result.pass_results[0]
    assert first.chain_links is not None
    assert len(first.chain_links) == 2
    assert [link.post_exit for link in first.chain_links] == [1, 1]
    assert first.receipt is not None
    assert result.verified is True


def test_chain_inconclusive_link_fails_closed():
    """Inconclusive link (exit 2) fails CLOSED: no verified, raises or failed."""
    from modules.workflows.sweep import ChainLink, SweepPassResult

    inconclusive = SweepPassResult(
        pass_id="standard",
        chain_links=[
            ChainLink(pre_exit=0, post_exit=1),
            ChainLink(pre_exit=0, post_exit=2),
        ],
        regression_passed=True,
        receipt={"chain": [(0, 1), (0, 2)]},
    )
    assert inconclusive.holds is False
    codes = [0, 2]
    result = _run_chain_sweep(codes)
    assert getattr(result, "verified", False) is False
    assert result.status in ("failed", "error")
