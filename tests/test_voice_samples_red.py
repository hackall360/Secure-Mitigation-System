# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (VOX2+VOX7): seeded voice-sample contract. Now GREEN.

`video-demo/TTSServer/sample_voices.py` generates one audio file per random
4-digit seed so voices can be compared seed-to-seed. Pinned here (no model,
no audio drivers needed):

- `generate_seeds(count, length, rng)` returns `count` UNIQUE ints with exactly
  `length` digits, deterministic for a seeded rng (1-9999 pool, banned seeds
  excluded).
- `sample_filename(seed, ext)` embeds the seed in the basename.
- `SAMPLE_TEXT` is the exact user-specified line.
- A manifest maps every seed to its file.
- VOX7 (literal retry): the 10 rejected seeds in BANNED_SEEDS are never
  generated; `synthesize_for_seed` defaults to literal mode (skip refine
  text, low temperature, top_K 1) so the refiner cannot insert words
  (`sound` -> `sound like` provenance, brief 2026-11-01-voice-seed-retry).

RED proof: collection ERROR `No module named 'sample_voices'`
(functional absence, not syntax) before VOX2 implemented it.
"""

import importlib.util
import random
from pathlib import Path

import pytest

TTS_DIR = Path(__file__).resolve().parents[1] / "video-demo" / "TTSServer"
EXPECTED_TEXT = (
    "This is a voice test! Can you hear how I sound, from a whisper to a "
    "shout? Do you like it, really? Pen, pineapple, apple, pen! Pen... "
    "pineapple... apple... pen."
)


def load_module():
    spec = importlib.util.spec_from_file_location("sample_voices", TTS_DIR / "sample_voices.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sampler():
    return load_module()


def test_sample_text_is_exact_user_line(sampler):
    assert sampler.SAMPLE_TEXT == EXPECTED_TEXT


def test_generate_seeds_ten_unique_in_pool(sampler):
    seeds = sampler.generate_seeds(10, 4, random.Random(1234))
    assert len(seeds) == 10
    assert len(set(seeds)) == 10, "seeds must be unique per run"
    assert all(1 <= s <= 9999 for s in seeds), "pool is 1-9999"


def test_generate_seeds_deterministic_for_seeded_rng(sampler):
    first = sampler.generate_seeds(10, 4, random.Random(99))
    second = sampler.generate_seeds(10, 4, random.Random(99))
    assert first == second


def test_generate_seeds_rejects_impossible_request(sampler):
    with pytest.raises(ValueError):
        sampler.generate_seeds(9000, 1, random.Random(0))


def test_sample_filename_embeds_seed(sampler):
    name = sampler.sample_filename(4821, "mp3")
    assert "4821" in name
    assert name.endswith(".mp3")


def test_sample_filename_wav_fallback(sampler):
    name = sampler.sample_filename(7, "wav")
    assert "7" in name
    assert name.endswith(".wav")


def test_banned_seeds_are_the_ten_rejected(sampler):
    assert set(sampler.BANNED_SEEDS) == {
        5923,
        8059,
        6623,
        6338,
        4545,
        2235,
        3823,
        7908,
        3217,
        4967,
    }, "banned set must be exactly the 10 user-rejected seeds"


def test_generate_seeds_never_returns_banned(sampler):
    seeds = sampler.generate_seeds(10, 4, random.Random(1234))
    assert not (set(seeds) & set(sampler.BANNED_SEEDS)), "retry must exclude rejected seeds"


def test_generate_seeds_skips_banned_deterministically(sampler):
    first = sampler.generate_seeds(10, 4, random.Random(99))
    second = sampler.generate_seeds(10, 4, random.Random(99))
    assert first == second
    assert not (set(first) & set(sampler.BANNED_SEEDS))


def test_literal_mode_is_default(sampler):
    import inspect

    sig = inspect.signature(sampler.synthesize_for_seed)
    assert sig.parameters["literal"].default is True


def test_literal_params_skip_refine_and_tighten_sampling(sampler):
    try:
        infer_code, refine_text, kwargs = sampler.literal_params(0.3)
    except ModuleNotFoundError:
        pytest.skip("ChatTTS not installed in repo venv; source pins it instead")
    assert kwargs["skip_refine_text"] is True
    assert infer_code.temperature == pytest.approx(0.3)
    assert infer_code.top_K == 20
    assert refine_text.prompt == ""


def test_literal_params_source_pins_verbatim_path(sampler):
    import inspect

    source = inspect.getsource(sampler.literal_params)
    assert "skip_refine_text" in source
    assert "top_K" in source
    assert 'prompt=""' in source or "prompt=''" in source
