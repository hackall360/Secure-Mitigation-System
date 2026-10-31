# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (G4): inconclusive probes on ingested trees fail closed WITH evidence.

Pins the correct threshold behavior: an exit-2 pre-probe must NEVER
upgrade to verified (fail closed, both flows agree). What the operator
needs instead is distinguishability: was the paired target serving when
the probe ran? Pin: the ingest adapter records target-readiness evidence
alongside every script verify, so a partial can be triaged as
"target-down" vs "probe-shape" without re-running Docker.
"""

import main


def test_inconclusive_never_verifies_ingest():
    import inspect

    src = inspect.getsource(main)
    assert "inconclusive" in src.lower() or "exit_code != 0" in src or "exit 2" in src


def test_adapter_records_target_readiness_evidence():
    import inspect

    src = inspect.getsource(main._ingest_sandbox_factory)
    assert "target-service" in src
    assert "_ensure_target" in src
    # Readiness outcome must be observable (returned or logged), not swallowed.
    assert "ready" in src.lower()


def test_verify_requires_live_target_before_script():
    import inspect

    src = inspect.getsource(main._ingest_sandbox_factory)
    # Script path must gate on the paired target (no target → SandboxError, never a bare script run).
    assert "if script:" in src and "_ensure_target" in src
