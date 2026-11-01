# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (TTS1): standalone video-demo TTS server contract.

`video-demo/TTSServer/server.py` is a LOCAL ChatTTS speech server with zero
wiring into red/blue agents, the main app, dashboard, TUI, CLI, or MCP
(standalone brief 2026-11-01-video-demo-tts-standalone). Contract pinned here:

- module imports with NO torch/ChatTTS/sounddevice installed (lazy heavy deps)
- GET /healthz reports ready + queue depths
- POST /speak validates empty text (400), queues valid text, reports position
- POST /render returns 16-bit PCM WAV bytes at 24000 Hz (video pipeline input)
- start.sh / stop.sh exist and are executable (spin up / spin down)
- shutdown leaves no worker threads running (LAW 10I bounded teardown)
- demo narrator pinned: seed 6420 male @ 0.3 literal by default (brief
  2026-11-01-pin-narrator-6420); TTS_VOICE_SEED / TTS_TEMPERATURE / TTS_LITERAL
  override; token stream seeded so renders are deterministic

RED proof: collection ERROR `No module named 'video_demo_tts_server'`
(functional absence, not syntax) before TTS2 implements it.
"""

import importlib.util
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TTS_DIR = Path(__file__).resolve().parents[1] / "video-demo" / "TTSServer"


def load_server():
    spec = importlib.util.spec_from_file_location("video_demo_tts_server", TTS_DIR / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeSynthesizer:
    """Deterministic stand-in: 0.25 s of 440 Hz sine, no torch/GPU/audio."""

    SAMPLE_RATE = 24000

    def __init__(self):
        import math
        from array import array

        frames = array("f")
        for i in range(self.SAMPLE_RATE // 4):
            frames.append(0.3 * math.sin(2.0 * math.pi * 440.0 * i / self.SAMPLE_RATE))
        self.audio = frames
        self.ready = False

    def load(self):
        self.ready = True

    def synthesize(self, text):
        assert text.strip(), "fake synthesizer rejects empty text like the real one"
        return self.audio


@pytest.fixture
def app_module():
    return load_server()


@pytest.fixture
def client(app_module):
    engine = app_module.TTSEngine(synthesizer=FakeSynthesizer(), start_playback=False)
    engine.preload()
    app = app_module.create_app(engine=engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.shutdown()


def test_module_imports_without_heavy_deps(app_module):
    """server.py must import with no torch/ChatTTS/sounddevice present."""
    assert callable(app_module.create_app)
    assert hasattr(app_module, "TTSEngine")


def test_healthz_reports_ready_and_depths(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["pending_texts"] == 0
    assert body["pending_audio"] == 0


def test_speak_rejects_empty_text(client):
    response = client.post("/speak", json={"text": "   "})
    assert response.status_code == 400


def test_speak_queues_and_reports_position(client):
    first = client.post("/speak", json={"text": "Hello video."})
    assert first.status_code == 200
    assert first.json()["status"] == "queued"
    assert first.json()["text"] == "Hello video."
    second = client.post("/speak", json={"text": "Second line."})
    assert second.status_code == 200
    assert second.json()["queue_position"] >= first.json()["queue_position"]


def test_render_returns_wav_bytes_at_24k(client, tmp_path):
    response = client.post("/render", json={"text": "Render me."})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    out = tmp_path / "line.wav"
    out.write_bytes(response.content)
    with wave.open(str(out), "rb") as wav:
        assert wav.getframerate() == 24000
        assert wav.getnchannels() == 1
        assert wav.getnframes() > 0


def test_render_rejects_empty_text(client):
    response = client.post("/render", json={"text": ""})
    assert response.status_code == 400


def test_spin_scripts_exist_and_are_executable():
    for name in ("start.sh", "stop.sh"):
        script = TTS_DIR / name
        assert script.is_file(), f"{name} must exist"
        import os

        assert os.access(script, os.X_OK), f"{name} must be executable"


def test_shutdown_leaves_no_workers(app_module):
    engine = app_module.TTSEngine(synthesizer=FakeSynthesizer(), start_playback=False)
    engine.preload()
    assert engine.is_running is True
    engine.shutdown()
    assert engine.is_running is False
    assert engine.text_queue.empty()


def test_narrator_defaults_to_6420_male_at_03_literal(app_module):
    settings = app_module.ServerSettings()
    assert settings.voice_seed == "6420"
    assert settings.temperature == 0.3
    assert settings.literal is True


def test_narrator_env_overrides_seed_temp_literal(app_module, monkeypatch):
    # Trap: ServerSettings is a dataclass — os.environ.get runs ONCE at
    # import, so monkeypatch-after-import cannot move the defaults. Reload
    # the module with the env set to exercise the override path for real.
    monkeypatch.setenv("TTS_VOICE_SEED", "1869")
    monkeypatch.setenv("TTS_TEMPERATURE", "0.5")
    monkeypatch.setenv("TTS_LITERAL", "0")
    reloaded = load_server()
    settings = reloaded.ServerSettings()
    assert settings.voice_seed == "1869"
    assert settings.temperature == 0.5
    assert settings.literal is False


def test_synthesize_pins_token_stream_to_seed(app_module):
    """Same seed+text must build identical infer params (deterministic delivery).

    Records the kwargs the synthesizer would hand to the ChatTTS pipeline:
    speaker seed, manual_seed, temperature, skip_refine. Two builds from the
    same settings must match exactly; a different seed must differ.
    """
    first = app_module.build_infer_spec(app_module.ServerSettings())
    second = app_module.build_infer_spec(app_module.ServerSettings())
    assert first == second
    assert first["manual_seed"] == 6420
    assert first["temperature"] == 0.3
    assert first["skip_refine_text"] is True
    other = app_module.build_infer_spec(app_module.ServerSettings(voice_seed="1869"))
    assert other["manual_seed"] == 1869
    assert other != first
