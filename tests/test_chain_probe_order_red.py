# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): chain link PRE probes must run against the pristine target.

Scout claim (UNVERIFIED at write time): library/workflows/sweep.py runs the
chain link PRE probes (link_a_pre, link_b_pre) AFTER replace_target, so the
recorded link "pre" exits are post-patch observations and the chain
pre/post evidence guarantee is void.

Verdict method: OrderRecordingSandbox fakes ONLY the Docker boundary (the
DockerSandboxManager surface: require_base_images / create_isolated_network
/ start_cloneable_target / replace_target / run_isolated_verifier) while the
REAL execute_sweep_scan drives. The test pins both link PRE probes BEFORE
replace_target. FAIL on current code = TRUE HOLE (RED proof of call order);
PASS = scout error (order is actually correct).
"""

import asyncio

from modules.core.config import PurpleBoxConfig
from tests.helpers import silent_emit

TEST_CONFIG = PurpleBoxConfig(meta_api_key="test-key")

PRIMITIVE_TAG = "primitive-marker-A"
SINK_TAG = "sink-marker-B"

UNIFIED_CHAIN_SCRIPT = (
    "import sys\n"
    f"# {PRIMITIVE_TAG}: benign primitive values, falls through on success\n"
    "print('primitive ok')\n"
    "# --- Link B ---\n"
    f"# {SINK_TAG}: malicious value leveraging the primitive\n"
    "print('sink verdict')\n"
    "sys.exit(0)\n"
)


class OrderRecordingSandbox:
    """Docker-boundary fake (LAW 9): records call order, scripts exit codes."""

    def __init__(self, codes):
        from collections import deque

        self.codes = deque(codes)
        self.events: list = []  # ("probe", script) | ("replace_target",) | ...
        self.closed = False

    def require_base_images(self):
        self.events.append(("require_base_images",))
        return None

    def create_isolated_network(self):
        self.events.append(("create_network",))
        return "test-network"

    def start_cloneable_target(self, *args):
        self.events.append(("start_target",))
        return "container", "snapshot"

    def replace_target(self, *args):
        self.events.append(("replace_target",))
        return "patched-container", "patched-snapshot"

    def run_isolated_verifier(self, *args):
        from modules.core.docker_manager import VerificationResult

        script = args[-1]
        self.events.append(("probe", script))
        return VerificationResult(self.codes.popleft(), "test evidence")

    def close(self):
        self.closed = True


class ChainOrderFakeMuse:
    """Agent double: marked unified chain script only for the chain pass."""

    def __init__(self):
        self.closed = False

    async def run_red_team_pass_analysis(self, pass_id, filename, source, contract=""):
        from modules.core.agents import RedTeamFinding

        script = (
            UNIFIED_CHAIN_SCRIPT if pass_id == "chain" else "import sys\nsys.exit(1)\n"
        )
        return RedTeamFinding(
            vulnerability_class=f"test chain boundary {pass_id}",
            sink_location=filename,
            analysis_summary="Test-only benign marker.",
            verification_script_python=script,
        )

    async def run_blue_team_sanitizer(
        self, filename, source_code, finding=None, evidence="", contract=""
    ):
        from modules.core.agents import BlueTeamPatch

        return BlueTeamPatch(
            sanitization_strategy="Validate IDs",
            diff_summary="Add a guard",
            patched_file_content=source_code.rstrip("\n") + "\n// chain-order-guard\n",
        )

    async def aclose(self):
        self.closed = True


def _describe(events):
    """Compact call-order readout for failure messages."""

    def short(script):
        has_a, has_b = PRIMITIVE_TAG in script, SINK_TAG in script
        if has_a and has_b:
            return "probe:unified"
        if has_a:
            return "probe:link-A"
        if has_b:
            return "probe:link-B"
        return "probe:other"

    return [(i, short(e[1]) if e[0] == "probe" else e[0]) for i, e in enumerate(events)]


def test_chain_link_pre_probes_run_before_replace_target():
    """Link PRE probes must execute on the pristine target (before replace_target).

    sweep.py chain branch calls replace_target (patched container goes live)
    before link_a_pre/link_b_pre, so both "pre" probes observe the PATCHED
    target and the recorded ChainLink pre_exits mislabel post-patch exits as
    pre-patch evidence. First A-without-B / B-without-A probes are the pres
    (unified pre/post carry both markers; link posts run later still).
    """
    from modules.workflows.sweep import execute_sweep_scan

    # baseline, std/deep/ta pre (clear), chain pre, regression, post,
    # link_a_pre, link_b_pre, link_a_post, link_b_post, final health.
    codes = [0, 1, 1, 1, 0, 0, 1, 0, 0, 1, 1, 0]
    sandbox = OrderRecordingSandbox(codes)
    muse = ChainOrderFakeMuse()
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
    assert result.pass_results[3].pass_id == "chain"
    assert sandbox.closed and muse.closed

    kinds = [e[0] for e in sandbox.events]
    replace_idx = kinds.index("replace_target")

    def first_link_event_idx(has, lacks):
        for i, event in enumerate(sandbox.events):
            if event[0] == "probe" and has in event[1] and lacks not in event[1]:
                return i
        raise AssertionError(f"link probe carrying {has!r} never executed")

    link_a_idx = first_link_event_idx(PRIMITIVE_TAG, SINK_TAG)
    link_b_idx = first_link_event_idx(SINK_TAG, PRIMITIVE_TAG)
    order = _describe(sandbox.events)
    assert link_a_idx < replace_idx, (
        f"link_a PRE probe runs AFTER replace_target (patched target): {order}"
    )
    assert link_b_idx < replace_idx, (
        f"link_b PRE probe runs AFTER replace_target (patched target): {order}"
    )
