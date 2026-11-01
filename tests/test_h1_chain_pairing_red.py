# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9, audit H1): chain-link pre/post pairing fail-first tests.

H1: the middle ChainLink was built as (link_a_pre, link_b_pre) — pre-patch A
paired with pre-patch B — so ChainLink.holds (which keys off post_exit == 1)
gated on a pre-patch value. Correct pairing: link 1 = unified (pre, post);
link 2 = (link_a_pre, link_a_post); link 3 = (link_b_pre, link_b_post), built
once after both post-patch probes return.

Benign exit-code semantics only. FAKE Muse+sandbox; never real Docker/Muse.
"""

import asyncio
import inspect

from modules.core.config import PurpleBoxConfig
from tests.helpers import FakeFixtureSandbox, silent_emit

TEST_CONFIG = PurpleBoxConfig(meta_api_key="test-key")


class H1FakeMuse:
    """Red/blue double emitting a benign marker probe."""

    def __init__(self):
        self.closed = False

    async def run_red_team_pass_analysis(self, pass_id, filename, source, contract=""):
        from modules.core.agents import RedTeamFinding

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

        return BlueTeamPatch(
            sanitization_strategy="Validate IDs",
            diff_summary="Add a guard",
            patched_file_content=source_code.rstrip("\n") + "\n// h1-guard\n",
        )

    async def aclose(self):
        self.closed = True


def _holds_for(a_pre, a_post, b_pre, b_post, pre=0, post=1):
    """holds() verdict for a correctly paired 3-link chain pass."""
    from modules.workflows.sweep import ChainLink, SweepPassResult

    return SweepPassResult(
        pass_id="chain",
        chain_links=[
            ChainLink(pre_exit=pre, post_exit=post),
            ChainLink(pre_exit=a_pre, post_exit=a_post),
            ChainLink(pre_exit=b_pre, post_exit=b_post),
        ],
        regression_passed=True,
        receipt={"chain": [(pre, post), (a_pre, a_post), (b_pre, b_post)]},
    ).holds


def test_h1_vulnerable_chain_holds_when_both_links_blocked():
    """A-pre 0/A-post 1/B-pre 0/B-post 1 must HOLD."""
    assert _holds_for(0, 1, 0, 1) is True


def test_h1_unpatched_chain_does_not_hold():
    """Post-patch probes still reaching the sink (posts 0) must NOT hold."""
    assert _holds_for(0, 0, 0, 0) is False


def test_h1_half_patched_chain_does_not_hold():
    """One post-patch link still open must NOT hold (either side)."""
    assert _holds_for(0, 0, 0, 1) is False
    assert _holds_for(0, 1, 0, 0) is False


def test_h1_source_never_pairs_preA_with_preB():
    """Pin: the file must never pair link_a_pre with link_b_pre again."""
    import modules.workflows.sweep as sweep

    source = inspect.getsource(sweep.execute_sweep_scan)
    assert (
        "ChainLink(pre_exit=link_a_pre.exit_code, post_exit=link_b_pre.exit_code)" not in source
    ), "H1: middle link still pairs pre-patch A with pre-patch B"


def test_h1_source_pairs_each_link_pre_with_own_post():
    """Pin: link 2 = (a_pre, a_post), link 3 = (b_pre, b_post)."""
    import re

    import modules.workflows.sweep as sweep

    source = inspect.getsource(sweep.execute_sweep_scan)
    norm = re.sub(r"\s+", "", source)
    assert "ChainLink(pre_exit=link_a_pre.exit_code,post_exit=link_a_post.exit_code)" in norm
    assert "ChainLink(pre_exit=link_b_pre.exit_code,post_exit=link_b_post.exit_code)" in norm


def test_h1_single_final_chain_links_assignment():
    """Pin: one 3-link construction after both post probes (plus the else-branch)."""
    import modules.workflows.sweep as sweep

    source = inspect.getsource(sweep.execute_sweep_scan)
    assert source.count("passed.chain_links = [") == 2


def test_h1_fully_patched_chain_sweep_verifies():
    """End-to-end: all-pre 0 / all-post 1 across 4 passes must verify.

    On buggy code the middle link reads (a_pre=0, b_pre=0) -> post 0 ->
    sweep 'failed' despite a full patch. Fixed code must verify.
    """
    from modules.workflows.sweep import execute_sweep_scan

    codes = [0] + [0, 0, 1, 0] * 3 + [0, 0, 1, 0, 0, 1, 1, 0]
    sandbox = FakeFixtureSandbox(codes)
    muse = H1FakeMuse()
    result = asyncio.new_event_loop().run_until_complete(
        execute_sweep_scan(
            "node_query_sink",
            silent_emit,
            config=TEST_CONFIG,
            sandbox_factory=lambda settings: sandbox,
            muse_factory=lambda settings: muse,
            max_passes=4,
        )
    )
    chain = result.pass_results[3]
    assert chain.pass_id == "chain"
    assert [(link.pre_exit, link.post_exit) for link in chain.chain_links] == [
        (0, 1),
        (0, 1),
        (0, 1),
    ]
    assert result.verified is True, f"H1: fully patched chain did not verify: {result.status}"
