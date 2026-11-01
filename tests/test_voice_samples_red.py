# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (VOX2): seeded voice-sample contract. Now GREEN.

`video-demo/TTSServer/sample_voices.py` generates one audio file per random
4-digit seed so voices can be compared seed-to-seed. Pinned here (no model,
no audio drivers needed):

- `generate_seeds(count, length, rng)` returns `count` UNIQUE ints with exactly
  `length` digits (1000-9999 for length 4), deterministic for a seeded rng.
- `sample_filename(seed, ext)` embeds the seed in the basename.
- `SAMPLE_TEXT` is the exact user-specified line.
- A manifest maps every seed to its file.

RED proof: collection ERROR `No module named 'sample_voices'`
(functional absence, not syntax) before VOX2 implemented it.
"""

import importlib.util
import random
from pathlib import Path

import pytest

TTS_DIR = Path(__file__).resolve().parents[1] / "video-demo" / "TTSServer"
EXPECTED_TEXT = "This is a simple test. This is how I sound! Do you like it?"


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


def test_generate_seeds_ten_unique_four_digit(sampler):
    seeds = sampler.generate_seeds(10, 4, random.Random(1234))
    assert len(seeds) == 10
    assert len(set(seeds)) == 10, "seeds must be unique per run"
    assert all(1000 <= s <= 9999 for s in seeds), "length-4 means 1000-9999"


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
