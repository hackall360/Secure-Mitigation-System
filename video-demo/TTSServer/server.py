# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Standalone local ChatTTS speech server (video-demo dev tool).

STANDALONE: zero wiring into red/blue agents, the main app, dashboard, TUI,
CLI, or MCP. This module is a thin local wrapper around the ChatTTS pipeline
from the user brief: lifespan-gated preload (weights + optional torch.compile
so the port opens only when the voice is ready), queue workers for
generation/playback, and a small HTTP API for narration scripts.

Heavy ML deps (torch, ChatTTS, sounddevice) are LAZY: importing this module
never requires them, so unit tests and the repo gate run without a GPU. The
real synthesizer backend (`ChatTTSSynthesizer`) imports them only when
`preload()` actually loads the model.

Endpoints:
  GET  /healthz  -> {"ready", "pending_texts", "pending_audio"} (spin-up probe)
  POST /speak    -> queue text for background generation + playback
  POST /render   -> blocking synthesize, returns 16-bit PCM WAV (video input)
"""

import argparse
import contextlib
import io
import os
import queue
import threading
import wave
from dataclasses import dataclass

SAMPLE_RATE = 24000
DEFAULT_PORT = 8002
TEXT_LIMIT = 2000


def _env_flag(name, default):
    return os.environ.get(name, "1" if default else "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@dataclass
class ServerSettings:
    host: str = "127.0.0.1"
    port: int = int(os.environ.get("TTS_PORT", str(DEFAULT_PORT)))
    preload: bool = _env_flag("TTS_PRELOAD", True)
    compile: bool = _env_flag("TTS_COMPILE", False)
    playback: bool = _env_flag("TTS_PLAYBACK", True)
    device: str = os.environ.get("TTS_DEVICE", "").strip() or "auto"
    refine_prompt: str = os.environ.get("TTS_REFINE_PROMPT", "[oral_2][laugh_0][break_4]")
    temperature: float = float(os.environ.get("TTS_TEMPERATURE", "0.3"))
    voice_pt: str = os.environ.get("TTS_VOICE_PT", "").strip()
    voice_seed: str = os.environ.get("TTS_VOICE_SEED", "").strip()


class ChatTTSSynthesizer:
    """Real backend: ChatTTS lazily imported at load time (GPU optional)."""

    def __init__(self, settings):
        self.settings = settings
        self.chat = None
        self.spk_emb = None
        self.ready = False

    def load(self):
        try:
            import ChatTTS
        except ImportError as exc:
            raise RuntimeError(
                "ChatTTS is not installed. Install video-demo/TTSServer "
                "requirements-tts.txt first (pip install -r requirements-tts.txt)."
            ) from exc
        self.chat = ChatTTS.Chat()
        kwargs = {"compile": self.settings.compile}
        if self.settings.device != "auto":
            try:
                import torch

                kwargs["device"] = torch.device(self.settings.device)
            except ImportError as exc:
                raise RuntimeError("TTS_DEVICE needs torch, which is not installed.") from exc
        if not self.chat.load(**kwargs):
            raise RuntimeError("ChatTTS failed to load weights (check disk/HF cache).")
        if self.settings.voice_pt:
            try:
                import torch
            except ImportError as exc:
                raise RuntimeError("TTS_VOICE_PT needs torch, which is not installed.") from exc
            try:
                self.spk_emb = torch.load(self.settings.voice_pt, map_location="cpu")
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"Pinned voice file not found: {self.settings.voice_pt}"
                ) from exc
            print(f"[TTS] pinned voice loaded from {self.settings.voice_pt}")
        elif self.settings.voice_seed:
            import torch

            torch.manual_seed(int(self.settings.voice_seed))
            self.spk_emb = self.chat.sample_random_speaker()
            print(f"[TTS] voice pinned to seed {self.settings.voice_seed}")
        else:
            self.spk_emb = self.chat.sample_random_speaker()
        self.ready = True

    def synthesize(self, text):
        if not self.ready:
            raise RuntimeError("Model not loaded; call load() first.")
        params_infer = self.chat.InferCodeParams(
            spk_emb=self.spk_emb, temperature=self.settings.temperature
        )
        params_refine = self.chat.RefineTextParams(prompt=self.settings.refine_prompt)
        wavs = self.chat.infer(
            [text],
            skip_refine_text=False,
            params_refine_text=params_refine,
            params_infer_code=params_infer,
        )
        if not wavs:
            raise RuntimeError("ChatTTS returned no audio.")
        audio = wavs[0]
        return audio.flatten() if len(audio.shape) > 1 else audio


def wav_bytes_mono16(frames, sample_rate=SAMPLE_RATE):
    """Convert float frames (-1..1) to 16-bit mono PCM WAV bytes."""
    import array

    pcm = array.array("h")
    for sample in frames:
        clamped = max(-1.0, min(1.0, float(sample)))
        pcm.append(int(clamped * 32767))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


class TTSEngine:
    """Queue pipeline: generation worker + optional playback worker."""

    def __init__(self, synthesizer=None, settings=None, start_playback=True):
        self.settings = settings or ServerSettings()
        self.synthesizer = synthesizer or ChatTTSSynthesizer(self.settings)
        self.text_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.start_playback = start_playback and self.settings.playback
        self._playback = None
        self._threads = []

    @property
    def ready(self):
        return bool(getattr(self.synthesizer, "ready", False)) and self.is_running

    def preload(self):
        """Block until weights are loaded (lifespan gate), then start workers."""
        self.synthesizer.load()
        self.is_running = True
        workers = [self._generation_worker]
        if self.start_playback:
            self._playback = self._default_playback()
            if self._playback is not None:
                workers.append(self._playback_worker)
        for target in workers:
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self._threads.append(thread)
        return True

    def shutdown(self):
        self.is_running = False
        while not self.text_queue.empty():
            try:
                self.text_queue.get_nowait()
                self.text_queue.task_done()
            except queue.Empty:
                break
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        self._threads = []

    def synthesize_now(self, text):
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError("Text cannot be empty.")
        if len(cleaned) > TEXT_LIMIT:
            raise ValueError(f"Text over {TEXT_LIMIT} chars; split it first.")
        return self.synthesizer.synthesize(cleaned)

    def _default_playback(self):
        try:
            import sounddevice as sd

            def play(frames):
                sd.play(frames, samplerate=SAMPLE_RATE)
                sd.wait()

            return play
        except ImportError:
            return None

    def _generation_worker(self):
        while self.is_running:
            try:
                text = self.text_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                audio = self.synthesizer.synthesize(text)
                self.audio_queue.put(audio)
            except Exception as exc:  # LAW 10J: surface, never swallow
                print(f"[TTS] generation failed: {exc}")
            finally:
                self.text_queue.task_done()

    def _playback_worker(self):
        assert self._playback is not None
        while self.is_running:
            try:
                audio = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._playback(audio)
            except Exception as exc:  # LAW 10J: surface, never swallow
                print(f"[TTS] playback failed: {exc}")
            finally:
                self.audio_queue.task_done()


def create_app(engine=None, settings=None):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse, Response
    from pydantic import BaseModel

    resolved_settings = settings or ServerSettings()
    tts_engine = engine or TTSEngine(settings=resolved_settings)

    class SpeakRequest(BaseModel):
        text: str

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        if resolved_settings.preload:
            print("[TTS] loading ChatTTS weights (this can take 1-3 min)...")
            tts_engine.preload()
            print("[TTS] ready.")
        yield
        tts_engine.shutdown()

    app = FastAPI(lifespan=lifespan, title="Local ChatTTS Server (video-demo)")

    @app.get("/healthz")
    def healthz():
        return JSONResponse(
            {
                "ready": tts_engine.ready,
                "pending_texts": tts_engine.text_queue.qsize(),
                "pending_audio": tts_engine.audio_queue.qsize(),
            }
        )

    @app.post("/speak")
    def speak(request: SpeakRequest):
        cleaned = (request.text or "").strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Text cannot be empty.")
        if len(cleaned) > TEXT_LIMIT:
            raise HTTPException(status_code=400, detail=f"Text over {TEXT_LIMIT} chars.")
        position = tts_engine.text_queue.qsize() + 1
        tts_engine.text_queue.put(cleaned)
        return {"status": "queued", "text": cleaned, "queue_position": position}

    @app.post("/render")
    def render(request: SpeakRequest):
        cleaned = (request.text or "").strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Text cannot be empty.")
        try:
            frames = tts_engine.synthesize_now(cleaned)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return Response(content=wav_bytes_mono16(frames), media_type="audio/wav")

    app.state.tts_engine = tts_engine
    return app


_app_settings = ServerSettings()
app = create_app(settings=_app_settings)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local ChatTTS TTS server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=ServerSettings().port)
    parser.add_argument(
        "--no-preload", action="store_true", help="open the port without loading weights (dev only)"
    )
    parser.add_argument(
        "--no-playback", action="store_true", help="disable speaker playback (headless/CI)"
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="torch.compile the model (slow start, fast inference)",
    )
    args = parser.parse_args(argv)

    settings = ServerSettings(
        host=args.host,
        port=args.port,
        preload=not args.no_preload,
        playback=not args.no_playback,
        compile=args.compile or ServerSettings().compile,
    )
    # The import-time app's lifespan closure holds _app_settings by reference:
    # push CLI flags into it so direct runs honor --no-preload/--no-playback.
    _app_settings.host = settings.host
    _app_settings.port = settings.port
    _app_settings.preload = settings.preload
    _app_settings.playback = settings.playback
    _app_settings.compile = settings.compile
    app.state.tts_engine.settings = _app_settings
    import uvicorn

    # Pass the app OBJECT, not "server:app": the string form re-imports this
    # module in a fresh process, discarding the CLI flag pushes above.
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="warning",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
