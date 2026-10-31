# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): resilient env-aware probe contract for Red prompts (Target 1, 2a-8).

Gap: ingested wild trees yield "partial" because the generated pre-probe dies
with exit 2 on unknown startup states or path variances instead of proving a
deterministic 0/1 verdict.

Contract pinned BEFORE the prompt change (expect FAIL on the new markers):
every Red prompt (standard, deep, threat_actor, chain) must instruct the model
to write probes that

- retry transient network failures with a bounded loop (no bare single
  urlopen as the only network call);
- wait for target readiness (readiness loop or bounded retry with sleep);
- tolerate path/shape variance (try alternate routes/envelopes before exit 2);
- reserve exit 2 for genuinely exhausted retries, never for the first error.

Benign contract strings only: prompt-content markers, no payloads. FAKE
nothing here: these are pure string assertions on prompt constants.
"""

import pytest

_PROMPT_NAMES = (
    "RED_TEAM_SYSTEM_PROMPT",
    "RED_DEEP_SWEEP_SYSTEM_PROMPT",
    "RED_THREAT_ACTOR_SYSTEM_PROMPT",
    "RED_CHAIN_SYSTEM_PROMPT",
)

_RESILIENCE_MARKERS = (
    ("retry", "bounded retry", "retry"),
    ("readiness", "wait for the target / readiness", "readiness"),
    ("path variance", "alternate paths / shape variance", "alternate"),
    ("bounded", "no unbounded loops", "bounded"),
    ("exit 2 only after", "exit 2 reserved for exhausted retries", "exhausted"),
)


def _load_prompt(name: str) -> str:
    import modules.core.prompts as prompts

    return getattr(prompts, name)


@pytest.mark.parametrize("prompt_name", _PROMPT_NAMES)
def test_red_probe_contract_demands_resilience(prompt_name):
    """Each Red prompt instructs env-aware resilient probes (exit 0/1, not 2)."""
    lowered = _load_prompt(prompt_name).lower()
    for _, _desc, marker in _RESILIENCE_MARKERS:
        assert marker in lowered, f"{prompt_name} missing resilience marker: {marker!r}"


def test_red_prompts_keep_deterministic_exit_contract():
    """Resilience must not soften the deterministic 0/1/2 exit contract."""
    import modules.core.prompts as prompts

    for name in _PROMPT_NAMES:
        lowered = getattr(prompts, name).lower()
        assert "exit with exactly one of" in lowered, name
        assert "0 only if" in lowered, name
        assert "1 only if" in lowered, name
