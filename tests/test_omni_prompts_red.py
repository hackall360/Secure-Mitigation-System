# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): MISSION OMNI-INGEST Wave 3 — prompts target generalized
computational flaws, not just web input boundaries.

The directive orders: no web-exclusive assumptions; memory safety,
race conditions, weak crypto, unsafe FFI, logic flaws; probes verify
computational soundness, not just HTTP codes.

Audit result (verified firsthand): personas carry NO web-exclusive
assumptions (beats are input/flow/encoding/manifest language — already
language-agnostic). The REAL web-tether is narrower and mechanical:

1. Project-loop red REQUIRES the verification script to be Python
   (`RED_BATCH_SYSTEM_PROMPT`: "A verification script must be Python").
   For a C/Rust/Go tree, red cannot express `gcc`/`cargo test`/`go test`
   evidence — the probe language is web-ecosystem-shaped.
2. Project-loop red/blue prompts never name the compiled classes:
   buffer overflows, use-after-free, uninitialized memory, data races,
   unsafe FFI bounds, integer overflow. Without named classes, red
   under-hunts them even when the sources are C/Rust.

Contract (honest Wave 3 — verified against the sandbox FIRST):
- The batch prompt NAMES the compiled classes (memory safety, races, FFI,
  integer, weak crypto) so red hunts them in SOURCE.
- Probe language STAYS Python: the verifier executes `python3 -c`
  (subprocess banned), so build-execution probes need a new execution
  path (Wave 2 provisioned image). The prompt says this explicitly
  instead of authorizing shell red cannot run.
- Python probes evidence flaws STATICALLY (pattern + reachability),
  and never claim unobserved runtime behavior.
"""

from __future__ import annotations


def test_batch_prompt_allows_static_probes_for_compiled_trees():
    from modules.services import project_agents as pa

    text = pa.RED_BATCH_SYSTEM_PROMPT.lower()
    assert "python" in text
    assert "static" in text or "pattern" in text, (
        "batch prompt must define the static-evidence probe shape for trees "
        "with no HTTP surface"
    )


def test_batch_prompt_names_compiled_classes():
    from modules.services import project_agents as pa

    text = pa.RED_BATCH_SYSTEM_PROMPT.lower()
    assert "buffer" in text and "overflow" in text
    for cls in ("use-after-free", "race", "ffi", "integer"):
        assert cls in text, f"batch prompt must name {cls!r} as a hunt class"
