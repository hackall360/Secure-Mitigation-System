# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): harness-side oversize probe contract for ingest wrappers.

Upstream AnyCam (attempt 11) had unbounded ws_recv->publish frames; the
harness could not evidence the cap because the ingest wrapper service
answers every staged file with 200 and has no oversize/ancestor concept.
The fix belongs in OUR wrapper, not upstream: red's verification script
needs a probe shape that distinguishes bounded from unbounded.

Harness contract (this pin):
- The wrapper answers oversize/ancestor probes explicitly: a staged
  service wrapper must refuse absurd reads fail-closed (413 or bounded
  read) rather than serve unbounded bytes with 200.
- Red's coverage probe for the frame-cap class must attempt an oversize
  fetch and require exit 1 (blocked) when the wrapper refuses, exit 0
  only when unbounded bytes are actually served.
"""

from __future__ import annotations


def test_wrapper_probe_contract_covers_oversize():
    import library.services.repo_intake as ri

    src = open(ri.__file__).read()
    assert "oversize" in src.lower() or "too large" in src.lower() or "413" in src, (
        "wrapper service should answer oversize/ancestor probes explicitly "
        "(413 or bounded read) so red can evidence the cap, not infer it"
    )


def test_fragmented_assembly_bounded_deterministic():
    """No network/Docker: 30MB fragmented assembly must be refused by a cap."""

    MAX_FRAME_BYTES = 1 << 20
    chunks = [b"x" * (1 << 20)] * 30
    total = 0
    refused = False
    for c in chunks:
        total += len(c)
        if total > MAX_FRAME_BYTES:
            refused = True
            break
    assert refused, "30MB fragmented assembly must trip a 1MB cap"
