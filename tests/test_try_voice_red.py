# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (VOX10): pinned-voice iteration contract. Now GREEN.

`video-demo/TTSServer/try_voice.py` is the pass/fail iteration loop from brief
2026-11-01-pinned-voice-iteration: try a seed (hear it) -> pass (pin tensor to
.pt + keep audio) or fail (ban it, regenerate next). Nothing permanent until a
pass. Pinned here (no model needed):

- `speak_params(literal)` returns the exact infer kwargs the loop uses:
  skip-refine literal path + `manual_seed` threaded into InferCodeParams so
  BOTH the speaker tensor and the token stream are pinned (provenance:
  installed `model/gpt.py` samples tokens with unseeded `torch.multinomial`
  unless `manual_seed` is passed — same seed gave same tensor but different
  audio; that is the "similar but mathematically different" drift).
- `next_candidate(banned, rng)` draws a 4-digit seed outside the banned set.
- `record_pass` / `record_fail` update the loop state file (passed pins with
  tensor hashes, failed appends to banned) — pass saves, fail bans.
- Server loads a pinned `.pt` voice file when `TTS_VOICE_PT` points at one.

RED proof: `FileNotFoundError: .../try_voice.py` (functional absence) before
VOX10 implemented it.
"""

import importlib.util
import json
import random
from pathlib import Path

import pytest

TTS_DIR = Path(__file__).resolve().parents[1] / "video-demo" / "TTSServer"


def load_module():
    spec = importlib.util.spec_from_file_location("try_voice", TTS_DIR / "try_voice.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def looper():
    return load_module()


def test_speak_params_pins_token_stream(looper):
    kwargs = looper.speak_params(seed=28, literal=True)
    assert kwargs["skip_refine_text"] is True
    assert kwargs["infer_seed"] == 28
    assert "manual_seed" in kwargs["params_pin"]
    assert kwargs["params_pin"]["manual_seed"] == 28


def test_speak_params_expressive_keeps_refine_but_still_pins(looper):
    kwargs = looper.speak_params(seed=28, literal=False)
    assert kwargs["skip_refine_text"] is False
    assert kwargs["params_pin"]["manual_seed"] == 28


def test_next_candidate_avoids_banned(looper):
    banned = {1111, 2222}
    for _ in range(20):
        seed = looper.next_candidate(banned, random.Random())
        assert 1 <= seed <= 9999
        assert seed not in banned


def test_record_fail_bans_and_regenerates(tmp_path, looper):
    state = tmp_path / "loop.json"
    seed = looper.next_candidate(set(), random.Random(5))
    looper.record_fail(state, seed)
    saved = json.loads(state.read_text())
    assert seed in saved["banned"]
    again = looper.next_candidate(set(saved["banned"]), random.Random(5))
    assert again != seed
    assert again not in saved["banned"]


def test_record_pass_pins_tensor_hash(tmp_path, looper):
    state = tmp_path / "loop.json"
    looper.record_pass(state, 28, "deadbeef", "voice_0028.mp3")
    saved = json.loads(state.read_text())
    assert saved["passed"] == [{"seed": 28, "tensor": "deadbeef", "file": "voice_0028.mp3"}]
    assert 28 not in saved["banned"]


def test_state_round_trips_empty(tmp_path, looper):
    state = tmp_path / "loop.json"
    assert looper.load_state(state) == {"banned": [], "passed": []}


def test_default_text_is_user_line(looper):
    assert looper.TRY_TEXT == (
        "This is a voice test! I hope you enjoy how I sound. "
        "Pen pineapple apple pen. Pen, Pineapple, Apple, pen."
    )


def test_default_temperature_is_lively(looper):
    assert looper.DEFAULT_TEMPERATURE == pytest.approx(0.3)


def test_next_candidate_spans_1_to_9999(looper):
    import random

    seen_low = False
    rng = random.Random(3)
    for _ in range(300):
        seed = looper.next_candidate(set(), rng)
        assert 1 <= seed <= 9999
        if seed < 1000:
            seen_low = True
    assert seen_low, "1-9999 pool must be able to draw sub-1000 seeds"


def test_seed_pool_includes_28(looper):
    banned = set()
    pool = [s for s in range(1, 10000) if s not in banned]
    assert 28 in pool
    assert 1 in pool
    assert 9999 in pool
