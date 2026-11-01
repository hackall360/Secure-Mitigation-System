# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (VOX12): voice-booth TUI contract. Now GREEN.

`video-demo/TTSServer/booth.py` is the listening booth from brief
2026-11-01-voice-booth-tui: batches of 10, per-voice play/relisten/pass/fail,
volume default 50%, stop-or-deal-more at batch end. Pinned here without
audio, model, or a terminal (pure state machine + scripted I/O):

- `BoothState` starts at volume 0.5, empty batch, zero passed/banned.
- `deal_batch(state, n, rng)` fills n unbanned candidates.
- `on_pass` records the pin and advances; `on_fail` bans and auto-advances.
- `set_volume` clamps to 0.0-1.0 (default 0.5).
- `run_booth` drives a scripted session (commands in, transcript out) so the
  whole flow — play, relisten, pass, fail, volume, batch end, deal-more, quit —
  is proven without a human at the keyboard.
- Batch end offers stop or another 10; quitting anytime keeps state saved.

RED proof: `FileNotFoundError: .../booth.py` (functional absence) before
VOX12 implemented it.
"""

import importlib.util
from pathlib import Path

import pytest

TTS_DIR = Path(__file__).resolve().parents[1] / "video-demo" / "TTSServer"


def load_module():
    spec = importlib.util.spec_from_file_location("booth", TTS_DIR / "booth.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def booth():
    return load_module()


def test_default_volume_is_half(booth):
    state = booth.BoothState()
    assert state.volume == 0.5


def test_set_volume_clamps(booth):
    state = booth.BoothState()
    state.set_volume(2.0)
    assert state.volume == 1.0
    state.set_volume(-1.0)
    assert state.volume == 0.0
    state.set_volume(0.75)
    assert state.volume == 0.75


def test_deal_batch_ten_unbanned(booth):
    import random

    state = booth.BoothState()
    state.deal_batch(10, random.Random(7))
    assert len(state.batch) == 10
    assert len(set(state.batch)) == 10
    assert all(1 <= s <= 9999 for s in state.batch)


def test_deal_batch_skips_banned(booth):
    import random

    first = booth.BoothState()
    first.deal_batch(10, random.Random(7))
    banned_one = {first.batch[0]}
    second = booth.BoothState()
    second.banned = set(banned_one)
    second.deal_batch(10, random.Random(7))
    assert first.batch[0] not in second.batch


def test_on_fail_bans_and_advances(booth):
    state = booth.BoothState()
    state.batch = [1111, 2222, 3333]
    state.index = 0
    state.on_fail(1111)
    assert 1111 in state.banned
    assert state.index == 1
    assert state.current() == 2222


def test_on_pass_pins_and_advances(booth):
    state = booth.BoothState()
    state.batch = [1111, 2222]
    state.on_pass(1111, "abc123")
    assert state.passed == [{"seed": 1111, "tensor": "abc123"}]
    assert state.index == 1


def test_batch_end_reports_done(booth):
    state = booth.BoothState()
    state.batch = [1111]
    state.index = 0
    state.on_fail(1111)
    assert state.batch_done() is True


def test_run_booth_scripted_flow(booth):
    import random

    played = []

    def fake_play(seed, volume):
        played.append((seed, volume))

    def fake_render(seed):
        return "hash-%d" % seed

    transcript = booth.run_booth(
        ["p", "p", "r", "v 80", "p", "f", "p", "q"],
        play_fn=fake_play,
        render_fn=fake_render,
        rng=random.Random(11),
        batch_size=3,
    )
    assert transcript["banned"], "fail must ban"
    assert played, "play must be called"
    assert any(v == 0.8 for _, v in played), "volume change must reach playback"
    assert transcript["quit"] is True
