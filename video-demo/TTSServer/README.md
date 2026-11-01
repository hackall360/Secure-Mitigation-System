# TTSServer — local ChatTTS voice for the video demo (STANDALONE)

## Voice booth (pick your narrator)

`booth.py` is the interactive listening loop — you run it, it plays voices,
you pass or fail them. Batches of 10; pass pins the voice (`.pt` tensor +
audio kept), fail bans the seed and moves on.

```bash
cd video-demo/TTSServer
~/.local/share/tts-voice-samples/bin/python booth.py
```

Commands: `p` play, `r` relisten, `pass`, `fail`, `v 0-100` (volume, default
50), `s` skip, `more` (another 10), `q` quit. At each batch end it asks
`Another 10? [y/n]`. State saves to `booth.json` (banned + passed), so you
can quit anytime and resume — failed seeds never come back.

Knobs: `--text "Your line."` (what every voice reads), `--temperature`
(lower = more fixed delivery; upstream suggests near-zero for max fixity),
`--expressive` (restore the laugh/break style), `TTS_VOICE_PT` (server loads
a passed `.pt`), `TTS_VOICE_SEED` (server pins a seed directly).

Iteration audio lives in `.booth-scratch/` (temp, never committed); passed
voices land in `passed/` (`.pt` tensor + `.mp3`).


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
`TTS_COMPILE=1` (torch.compile: slow boot, fast inference), `TTS_DEVICE` (default auto), `TTS_TEMPERATURE`
(default 0.3), `TTS_REFINE_PROMPT`, `TTS_VOICE_SEED` (default 6420 — the
picked male narrator; empty string restores a random voice), `TTS_VOICE_PT`
(load a passed `.pt` instead of the seed), `TTS_LITERAL=0` (restore the
refiner; default 1 keeps lines verbatim, so the server reads exactly what
you send).

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
- Narrator pinned by default: seed 6420 (male) @ temperature 0.3, literal —
  the voice picked in the booth bake-off. Same seed + same line = same audio
  every render (token stream seeded, not just the embedding).
- Unit tests (`tests/test_tts_server_red.py`) run against a fake synthesizer —
  no torch/GPU/audio needed for the repo gate.
