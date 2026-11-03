# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (parity wave W2): env-only knobs + showcase rig have no API surface.

(a) Env-only knobs (META_MUSE_TIMEOUT_SECONDS, META_MUSE_MAX_TOKENS,
META_MUSE_REASONING_EFFORT, PURPLEBOX_VERIFIER_TIMEOUT_SECONDS, research
scanners) change behaviour but appear in no --help and no API.
(b) The showcase rig (TTS booth, capture, DSP, render_demo.sh) is
deliberately standalone with zero product wiring — but no API even
acknowledges it exists.

LAW 9 red-first: pre-change, ``effective_knobs`` and ``showcase_status``
do not exist on library.services.sms_api, so every case below FAILS with
AttributeError. Post-change green: knobs reflect a passed config (pure
read, no mutation); showcase_status reports static presence on the real
tree and fails closed (absent, never raise) on a missing-dir override.
"""

import dataclasses

from library.core.config import PurpleBoxConfig


def test_effective_knobs_reflects_custom_config_not_env():
    """Knobs mirror the PASSED config object, not ambient env."""
    from library.services import sms_api

    cfg = PurpleBoxConfig(
        api_timeout_seconds=42.0,
        max_output_tokens=4096,
        reasoning_effort="high",
        verifier_timeout_seconds=7,
        research_scanners=("grype", "trivy"),
    )
    before = dataclasses.asdict(cfg)
    knobs = sms_api.effective_knobs(cfg)
    assert knobs["timeout_seconds"] == 42.0
    assert knobs["max_tokens"] == 4096
    assert knobs["reasoning_effort"] == "high"
    assert knobs["verifier_timeout"] == 7
    assert knobs["research_scanners"] == ["grype", "trivy"]
    assert dataclasses.asdict(cfg) == before  # pure read: no mutation


def test_effective_knobs_default_loads_live_config():
    """No-arg call reads the live config and returns all five keys."""
    from library.services import sms_api

    knobs = sms_api.effective_knobs()
    assert set(knobs) == {
        "timeout_seconds",
        "max_tokens",
        "reasoning_effort",
        "verifier_timeout",
        "research_scanners",
    }
    assert isinstance(knobs["research_scanners"], list)


def test_showcase_status_real_tree_present_and_syntax_ok():
    """On the real tree: every rig part present, render_demo.sh syntax ok."""
    from library.services import sms_api

    status = sms_api.showcase_status()
    assert status["tts"]["present"] is True
    assert status["tts"]["port"] == 8002
    assert status["tts"]["health_url"].endswith("/healthz")
    assert status["capture"]["present"] is True
    assert len(status["capture"]["scripts"]) >= 1
    assert status["music"]["present"] is True
    assert status["music"]["final_bed"] is not None
    assert status["render"]["script_present"] is True
    assert status["render"]["bash_syntax_ok"] is True


def test_showcase_status_missing_dir_fails_closed_no_raise():
    """Missing-dir override: all absent, syntax False, never raises."""
    from library.services import sms_api

    status = sms_api.showcase_status(root="/nonexistent-parity-probe-dir-xyz")
    assert status["tts"]["present"] is False
    assert status["capture"]["present"] is False
    assert status["capture"]["scripts"] == []
    assert status["music"]["present"] is False
    assert status["music"]["final_bed"] is None
    assert status["render"]["script_present"] is False
    assert status["render"]["bash_syntax_ok"] is False
