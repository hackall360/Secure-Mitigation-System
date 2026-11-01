# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""H4: raw verifier stdout must never reach the live WS/UI feed.

Fail-first lane test. The red-phase (and sweep blue-phase) log lines must
carry the exit code ONLY; raw probe output stays in result.traces for
receipts/debugging but never hits emit()/log().
"""

SENTINEL = "H4-SENTINEL-EXPLOIT-BYTES-<script>alert(1)</script>"


class _SentinelSandbox:
    """Docker double whose verifier output always carries the sentinel."""

    def __init__(self, codes):
        self.codes = iter(codes)
        self.closed = False
        self.replaced = False

    def require_base_images(self):
        return None

    def create_isolated_network(self):
        return "test-network"

    def start_cloneable_target(self, *args):
        return "container", "snapshot"

    def replace_target(self, *args):
        self.replaced = True
        return "patched-container", "patched-snapshot"

    def run_isolated_verifier(self, *args):
        from library.core.docker_manager import VerificationResult

        return VerificationResult(next(self.codes), SENTINEL)

    def close(self):
        self.closed = True


def _collector():
    messages: list = []

    async def emit(team, message):
        messages.append((team, message))

    return emit, messages


def _live_text(messages):
    return "\n".join(str(m) for _, m in messages)


async def test_h4_red_phase_log_hides_probe_output():
    """workflow.py red-phase log line: exit code present, raw output absent."""
    from library.workflows.workflow import execute_purple_workflow
    from tests.helpers import TEST_CONFIG, FakeFixtureMuse

    emit, messages = _collector()
    sandbox = _SentinelSandbox([0, 0, 0, 1, 0])
    muse = FakeFixtureMuse()
    result = await execute_purple_workflow(
        "node_query_sink",
        emit,
        config=TEST_CONFIG,
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: muse,
    )
    assert result.success
    live = _live_text(messages)
    probe_lines = [m for t, m in messages if "Boundary check exited" in str(m)]
    assert probe_lines, "expected at least one Boundary-check live log line"
    assert any(str(result.pre_exit_code) in str(m) for m in probe_lines)
    assert SENTINEL not in live, "raw verifier stdout leaked to the live feed"
    assert result.traces["before"] == SENTINEL, "raw output must stay in traces"


async def test_h4_blue_phase_log_hides_probe_output():
    """workflow.py post-patch log line: exit code present, raw output absent."""
    from library.workflows.workflow import execute_purple_workflow
    from tests.helpers import TEST_CONFIG, FakeFixtureMuse

    emit, messages = _collector()
    sandbox = _SentinelSandbox([0, 0, 0, 1, 0])
    muse = FakeFixtureMuse()
    result = await execute_purple_workflow(
        "node_query_sink",
        emit,
        config=TEST_CONFIG,
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: muse,
    )
    assert result.success
    post_lines = [m for t, m in messages if "Post-patch boundary check exited" in str(m)]
    assert post_lines, "expected a post-patch live log line"
    assert any(str(result.post_exit_code) in str(m) for m in post_lines)
    assert SENTINEL not in _live_text(messages)
    assert result.traces["after"] == SENTINEL


async def test_h4_sweep_logs_hide_probe_output():
    """sweep.py pre/post/link log lines: exit codes present, raw output absent."""
    from library.workflows.sweep import execute_sweep_scan
    from tests.test_sweep_passes import TEST_CONFIG as SWEEP_CONFIG
    from tests.test_sweep_passes import SweepFakeMuse

    emit, messages = _collector()
    # chain pass exercises link_a/link_b pre+post: baseline + 3 normal passes
    # of (pre, regression, post, final-health) + chain pass of (pre,
    # regression, post, link_a_pre, link_b_pre, link_a_post, link_b_post,
    # final-health). Verdict-agnostic: H1 owns sweep flow; H4 only pins that
    # the live feed never carries raw verifier stdout.
    codes = [0] + [0, 0, 1, 0] * 3 + [0, 0, 0, 0, 0, 0, 0, 0]
    sandbox = _SentinelSandbox(codes)
    muse = SweepFakeMuse()
    result = await execute_sweep_scan(
        "node_query_sink",
        emit,
        config=SWEEP_CONFIG,
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: muse,
        max_passes=4,
    )
    live = _live_text(messages)
    probe_lines = [m for t, m in messages if "exited" in str(m) and "sweep" in str(m).lower()]
    assert probe_lines, "expected sweep boundary live log lines"
    link_lines = [m for m in probe_lines if "Link" in str(m)]
    assert len(link_lines) >= 4, f"expected link A/B pre+post lines, got: {link_lines}"
    assert SENTINEL not in live, "raw verifier stdout leaked to the sweep live feed"
    assert any(v == SENTINEL for v in result.traces.values())
