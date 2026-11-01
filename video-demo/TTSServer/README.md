# TTSServer — local ChatTTS voice for the video demo (STANDALONE)

Local, API-accessible text-to-speech. No wiring into red/blue agents, the main
app, dashboard, TUI, CLI, or MCP — this folder is a dev tool for narrating the
demo video, nothing more.

## Setup (one time)

```bash
cd video-demo/TTSServer
pip install -r requirements-tts.txt   # torch + ChatTTS + audio (heavy, GPU box)
```

Needs ~4 GB VRAM for a 30 s clip; RTX 4070 Super confirmed by the builder.
CPU works but is slow. First boot downloads the `2Noise/ChatTTS` weights.

## Spin up / spin down

```bash
./start.sh            # port 8002 (TTS_PORT overrides); probes first, never double-starts
curl 127.0.0.1:8002/healthz   # {"ready": true, ...} once weights are loaded
./stop.sh             # kills only the PID start.sh tracked
```

Environment knobs: `TTS_PORT` (default 8002 — the main app owns 8000),
`TTS_PLAYBACK=0` (headless: no speakers), `TTS_PRELOAD=0` (open the port
without weights; same as `--no-preload` — probing only, `/render` 503s),
`TTS_COMPILE=1` (torch.compile: slow boot, fast inference), `TTS_DEVICE` (default auto), `TTS_TEMPERATURE`,
`TTS_REFINE_PROMPT`.

Direct run: `python server.py --port 8002 --no-playback --no-preload --compile`
(`--no-preload` opens the port without weights; dev only — `/render` 503s).

## Use it

```bash
python client.py "Your narration line."            # queue + play through speakers
python client.py --render "Your line." --out line.wav   # save 24 kHz WAV for editing
curl -X POST 127.0.0.1:8002/speak -H 'Content-Type: application/json' \
  -d '{"text":"Hello video."}'
curl -X POST 127.0.0.1:8002/render -H 'Content-Type: application/json' \
  -d '{"text":"Hello video."}' --output line.wav
```

Endpoints: `GET /healthz` (ready + queue depths), `POST /speak` (queue,
instant 200), `POST /render` (blocking WAV bytes — the video pipeline input).
Empty text → 400; text over 2000 chars → 400 (split first).

## Notes

- Lifespan gate: the port opens only after weights load (1–3 min first boot).
- Voice is fixed per server session (one sampled speaker embedding).
- Unit tests (`tests/test_tts_server_red.py`) run against a fake synthesizer —
  no torch/GPU/audio needed for the repo gate.
