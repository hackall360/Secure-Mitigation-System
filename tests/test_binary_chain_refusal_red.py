# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED-first: binary sweep refuses max_passes=4 (H2).

The source sweep gates the chain pass on 3-link chain evidence
(SweepPassResult.holds() requires len(chain_links) == 3 for pass_id
"chain"), but execute_binary_sweep never assigns chain_links anywhere:
a binary "chain" verdict would fall through to the generic
receipt-and-post==1 branch with none of the 3-link evidence. WS accepts
"4", so the hole is reachable via socket today. Fail closed: refuse
max_passes=4 on the binary path with an explicit error naming the chain
pass, logged + raised before the pass loop. No Docker/Muse calls happen.
"""

import asyncio

from modules.core.config import PurpleBoxConfig
from tests.helpers import silent_emit

ELF_MAGIC = b"\x7fELF" + b"\x00" * 60
TEST_CONFIG = PurpleBoxConfig(meta_api_key="test-key")


def _unused_sandbox_factory(settings):
    raise AssertionError("binary sandbox must not start when the chain pass is refused")


def _unused_muse_factory(settings):
    raise AssertionError("muse must not be consulted when the chain pass is refused")


def test_binary_sweep_refuses_chain_pass():
    """max_passes=4 on the binary path fails closed naming the chain pass."""
    from modules.services.binary_intake import validate_binary_blob
    from modules.workflows.binary_sweep import execute_binary_sweep

    spec = validate_binary_blob(ELF_MAGIC, filename="t.elf", contract="Only stdin matters.")
    result = asyncio.new_event_loop().run_until_complete(
        execute_binary_sweep(
            spec,
            silent_emit,
            config=TEST_CONFIG,
            sandbox_factory=_unused_sandbox_factory,
            muse_factory=_unused_muse_factory,
            max_passes=4,
        )
    )
    assert result.status == "error"
    assert "chain" in result.message.lower()
    assert result.pass_results == []
    assert result.baseline_passed is False


def test_binary_sweep_still_allows_three_passes():
    """max_passes=3 keeps working: all three non-chain passes run and hold."""
    from modules.core.docker_manager import VerificationResult
    from modules.services.binary_intake import validate_binary_blob
    from modules.workflows.binary_sweep import execute_binary_sweep
    from tests.test_sweep_passes import SweepFakeMuse

    class FakeBinarySandbox:
        def __init__(self):
            self.calls = 0
            self.closed = False

        def require_base_images(self):
            return None

        def require_binary_image(self):
            return None

        def create_isolated_network(self):
            return "net"

        def binary_static_profile(self, network, blob):
            return "ELF 64-bit (fake profile)"

        def start_binary_harness(self, network, blob, mitigation=""):
            return "container", "snapshot"

        def replace_binary_harness(self, previous, snapshot, network, mitigation=""):
            return "container2", "snapshot2"

        def run_isolated_verifier(self, network, script):
            self.calls += 1
            if self.calls == 1:
                return VerificationResult(0, "harness baseline passed")
            return VerificationResult(1, "blocked")

        def close(self):
            self.closed = True

    async def go():
        spec = validate_binary_blob(
            ELF_MAGIC, filename="t.elf", contract="Only stdin matters."
        )
        sandbox = FakeBinarySandbox()
        muse = SweepFakeMuse()
        result = await execute_binary_sweep(
            spec,
            silent_emit,
            config=TEST_CONFIG,
            sandbox_factory=lambda s: sandbox,
            muse_factory=lambda s: muse,
            max_passes=3,
        )
        return result, sandbox, muse

    result, sandbox, muse = asyncio.new_event_loop().run_until_complete(go())
    assert [p.pass_id for p in result.pass_results] == ["standard", "deep", "threat_actor"]
    assert result.status == "verified"
    assert sandbox.calls > 1 and sandbox.closed and muse.closed
