# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): full-spectrum coverage sweep — secrets, deps, crypto, auth, config.

The harness audits exactly ONE class today: input-boundary injection
(standard/deep/threat-actor/chain all hunt tainted-data-into-sink with a
probe script). A cyber team covers more. This pin defines the new
coverage-class pass and fails until it exists:

- RED_COVERAGE_SWEEP_SYSTEM_PROMPT exists in library/core/prompts.py and
  directs red across FIVE classes with per-class probe shapes:
  secrets (hardcoded creds/keys/tokens in tree), dependencies
  (manifest pins vs known-bad ranges in the staged tree), crypto
  (weak hashes/ciphers, hardcoded IVs, TLS verification off),
  auth (missing checks on secondary paths, confused roles, default creds),
  config (dangerous defaults, debug flags, overbroad binds).
- agents.run_red_team_pass_analysis accepts pass_id="coverage" and routes
  the coverage prompt (same RedTeamFinding shape: vulnerability_class names
  the class, sink_location the path:line, verification_script_python the
  class-appropriate probe).
- sweep.py SWEEP_PASSES includes "coverage" after "chain" and the loop
  handles it like any other pass (probe -> patch -> verify).
- Terminal verdicts: a coverage finding that verifies flips the run to a
  decision (verified on patch-hold, failed on patch-miss) — never silent.
"""

from __future__ import annotations


def test_coverage_prompt_exists():
    from library.core import prompts as prompts_mod

    assert hasattr(prompts_mod, "RED_COVERAGE_SWEEP_SYSTEM_PROMPT"), (
        "RED_COVERAGE_SWEEP_SYSTEM_PROMPT must exist: secrets/deps/crypto/auth/config"
    )
    text = prompts_mod.RED_COVERAGE_SWEEP_SYSTEM_PROMPT
    for keyword in ("secret", "depend", "crypto", "auth", "config"):
        assert keyword in text.lower(), f"coverage prompt must direct {keyword} review"


def test_agent_dispatches_coverage_pass():
    import inspect

    from library.core import agents as agents_mod

    src = inspect.getsource(agents_mod.MetaMuseClient.run_red_team_pass_analysis)
    assert '"coverage"' in src or "'coverage'" in src, (
        "run_red_team_pass_analysis must route pass_id='coverage'"
    )
    assert "RED_COVERAGE_SWEEP_SYSTEM_PROMPT" in src


def test_sweep_includes_coverage_pass():
    from library.workflows import sweep as sweep_mod

    assert "coverage" in sweep_mod.SWEEP_PASSES, (
        f"SWEEP_PASSES must include coverage, got {sweep_mod.SWEEP_PASSES}"
    )
