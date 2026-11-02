#!/usr/bin/env bash
# render_demo.sh — provision, capture, and mux the 180 s Secure Mitigation demo.
#
# Joins the standalone showcase parts into ONE deterministic pipeline:
#   video-demo/TTSServer            server.py (:8002), client.py --render, start.sh
#   video-demo/desktop-capture      gamescope/launch_sandbox.sh,
#                                   pipewire/setup_audio_sink.sh (IsolatedAppAudio),
#                                   deskcap (gcc-built binary)
#   video-demo/music-generation     cinematic_cybersec_epic_FINAL.py + FINAL wav bed
#   docs/DEMO_SCRIPT.md             7 narration stems on the 180 s beat clock
#
# NEVER EXECUTE blindly: the full run starts servers, sinks, and capture.
# Static probe instead: `bash -n video-demo/render_demo.sh`
# Dry plan instead:    `video-demo/render_demo.sh --check` (starts NOTHING)
#
# Env (all optional, all with defaults):
#   DEMO_URL       page the sandbox browser shows (default http://127.0.0.1:8000/web/)
#   DEMO_CMD       app command run inside gamescope (default chromium kiosk on DEMO_URL)
#   TTS_HOST       TTS server host (default 127.0.0.1)
#   TTS_PORT       TTS server port (default 8002)
#   TTS_SEED       booth seed note for deterministic stems (default 6420, server-pinned)
#   BED_WAV        FINAL music bed (default .../music-generation/cinematic_cybersec_epic_FINAL.wav)
#   DEMO_SCRIPT    beat sheet with the 7 stem ids (default docs/DEMO_SCRIPT.md)
#   STEM_SRC_DIR   optional override dir with per-stem <id>.txt narration; when
#                  empty (default) the pinned table below (mirroring DEMO_SCRIPT.md)
#                  is used. When SET it must exist and hold all 7 <id>.txt files.
#   WORK_DIR       scratch dir (default video-demo/render); stems land in STEMS_DIR
#   STEMS_DIR      rendered stem wav dir (default $WORK_DIR/stems)
#   OUT            final muxed file (default demo_final.mp4 in WORK_DIR)
#   BEAT_CLOCK     capture bound in seconds (default 180, the 3-minute beat sheet)
#   SANDBOX_DISPLAY nested Wayland display (default wayland-99)
#   SINK_NAME      isolated audio sink (default IsolatedAppAudio)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="$ROOT/video-demo"
TTS_DIR="$DEMO_DIR/TTSServer"
GAMESCOPE_DIR="$DEMO_DIR/desktop-capture/gamescope"
PIPEWIRE_DIR="$DEMO_DIR/desktop-capture/pipewire"
DESKCAP_DIR="$DEMO_DIR/desktop-capture/deskcap"

DEMO_URL="${DEMO_URL:-http://127.0.0.1:8000/web/}"
DEMO_CMD="${DEMO_CMD:-chromium --kiosk \"$DEMO_URL\"}"
TTS_HOST="${TTS_HOST:-127.0.0.1}"
TTS_PORT="${TTS_PORT:-8002}"
TTS_SEED="${TTS_SEED:-6420}"
BED_WAV="${BED_WAV:-$DEMO_DIR/music-generation/cinematic_cybersec_epic_FINAL.wav}"
DEMO_SCRIPT="${DEMO_SCRIPT:-$ROOT/docs/DEMO_SCRIPT.md}"
STEM_SRC_DIR="${STEM_SRC_DIR:-}"
WORK_DIR="${WORK_DIR:-$DEMO_DIR/render}"
STEMS_DIR="${STEMS_DIR:-$WORK_DIR/stems}"
OUT="${OUT:-$WORK_DIR/demo_final.mp4}"
BEAT_CLOCK="${BEAT_CLOCK:-180}"
SANDBOX_DISPLAY="${SANDBOX_DISPLAY:-wayland-99}"
SINK_NAME="${SINK_NAME:-IsolatedAppAudio}"

# Stem ids in beat order (mirror docs/DEMO_SCRIPT.md 1:1). Narration lines are
# TEXT-ONLY, each at most 200 chars, deterministic under booth seed $TTS_SEED.
STEM_IDS=(demo-hook demo-red demo-blue demo-flip demo-replay demo-honest demo-close)

declare -A STEM_TEXT=(
  [demo-hook]="Watch this probe hit a live target in Docker and come back exit zero. The boundary is reachable, and we can prove it."
  [demo-red]="Red maps the surface with Cartographer, then Bloodhound follows tainted input from the route into an unsanitized sink."
  [demo-blue]="Blue answers with the smallest fix that holds: a parameterized query plus an allow list, nothing else touched."
  [demo-flip]="Same probe, fresh target. Exit zero becomes exit one, regression still green, and the Notary chains the receipt."
  [demo-replay]="On a repeat visit the vault replays a prior fix, as in case C34, cutting a fresh investigation down to one retry cycle."
  [demo-honest]="Tokens, cost, and compression stay visible. When proof is inconclusive the harness says exit two and fails closed."
  [demo-close]="Evidence, not opinion. Secure Mitigation System, open source at the repo link below. Try your own target next."
)

banner() { echo "=== Phase $1: $2 ==="; }
fail_block() {
  echo "[render_demo] ERROR: missing required inputs:" >&2
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    echo "  - $line" >&2
  done <<< "$1"
  echo "[render_demo] fix the paths above (or the env overrides) and re-run." >&2
  return 1
}

# ---- input verification (the ONLY thing --check runs) -----------------------
check_inputs() {
  local missing=""
  local note
  note() { missing+="$1"$'\n'; }

  [[ -f "$DEMO_SCRIPT" ]] || note "DEMO_SCRIPT=$DEMO_SCRIPT: beat sheet not found (default docs/DEMO_SCRIPT.md)"
  if [[ -f "$DEMO_SCRIPT" ]]; then
    local id
    for id in "${STEM_IDS[@]}"; do
      grep -q "$id" "$DEMO_SCRIPT" || note "DEMO_SCRIPT=$DEMO_SCRIPT: stem id '$id' absent (7 stems required)"
    done
  fi
  [[ -f "$BED_WAV" ]] || note "BED_WAV=$BED_WAV: FINAL music bed not found (run video-demo/music-generation/cinematic_cybersec_epic_FINAL.py)"
  [[ -x "$TTS_DIR/start.sh" ]] || note "TTS start script missing: $TTS_DIR/start.sh"
  [[ -f "$TTS_DIR/stop.sh" ]] || note "TTS stop script missing: $TTS_DIR/stop.sh (needed for teardown)"
  [[ -f "$TTS_DIR/client.py" ]] || note "TTS render client missing: $TTS_DIR/client.py"
  [[ -f "$TTS_DIR/server.py" ]] || note "TTS server missing: $TTS_DIR/server.py"
  [[ -x "$GAMESCOPE_DIR/launch_sandbox.sh" ]] || note "sandbox launcher missing: $GAMESCOPE_DIR/launch_sandbox.sh"
  [[ -x "$PIPEWIRE_DIR/setup_audio_sink.sh" ]] || note "audio sink setup missing: $PIPEWIRE_DIR/setup_audio_sink.sh"
  [[ -f "$PIPEWIRE_DIR/teardown_audio_sink.sh" ]] || note "audio sink teardown missing: $PIPEWIRE_DIR/teardown_audio_sink.sh (needed for teardown)"
  [[ -f "$DESKCAP_DIR/Makefile" ]] || note "deskcap build file missing: $DESKCAP_DIR/Makefile"
  [[ -f "$DESKCAP_DIR/pwcam_desktop.c" ]] || note "deskcap source missing: $DESKCAP_DIR/pwcam_desktop.c"
  if [[ -n "$STEM_SRC_DIR" ]]; then
    if [[ ! -d "$STEM_SRC_DIR" ]]; then
      note "STEM_SRC_DIR=$STEM_SRC_DIR: directory does not exist (unset STEM_SRC_DIR to use the DEMO_SCRIPT.md pinned stem table)"
    else
      local id
      for id in "${STEM_IDS[@]}"; do
        [[ -f "$STEM_SRC_DIR/$id.txt" ]] || note "STEM_SRC_DIR=$STEM_SRC_DIR: stem text '$id.txt' absent (all 7 <id>.txt files required when overriding)"
      done
    fi
  fi

  if [[ -n "$missing" ]]; then
    fail_block "$missing"
    return 1
  fi
  echo "[render_demo] inputs OK: 7 stems, FINAL bed, TTS/sandbox/audio/deskcap parts present."
}

print_plan() {
  echo "[render_demo] --check: verifying inputs only, starting NOTHING."
  echo "[render_demo] phase plan (BEAT_CLOCK=${BEAT_CLOCK}s, TTS=${TTS_HOST}:${TTS_PORT}, OUT=$OUT):"
  echo "  Phase 1/6: preflight — verify tools, TTS/python deps, and input files"
  echo "  Phase 2/6: provision — start TTS server (start.sh), IsolatedAppAudio sink, gamescope sandbox on $DEMO_URL"
  echo "  Phase 3/6: render — client.py --render per DEMO_SCRIPT stem id into $STEMS_DIR (TEXT-ONLY, seed $TTS_SEED)"
  echo "  Phase 4/6: capture — gamescope->wf-recorder->deskcap video + monitor-only audio, bounded by the ${BEAT_CLOCK}s beat clock"
  echo "  Phase 5/6: mux — ffmpeg joins video + FINAL bed + stems to the stems timeline -> $OUT"
  echo "  Phase 6/6: teardown — trap EXIT kills pipeline group + gamescope + TTS + audio sink even on failure"
}

# ---- full-run preflight (tools + built binary; NOT run by --check) -----------
check_tools() {
  local missing=""
  local bin
  for bin in gamescope wf-recorder pactl python3; do
    command -v "$bin" >/dev/null 2>&1 || missing+="tool '$bin' not on PATH (install it; see video-demo/desktop-capture/README.md)"$'\n'
  done
  if ! command -v ffmpeg >/dev/null 2>&1 && ! command -v pw-record >/dev/null 2>&1; then
    missing+="audio recorder missing: need 'ffmpeg' or 'pw-record' on PATH (monitor-only capture of $SINK_NAME)"$'\n'
  fi
  [[ -x "$DESKCAP_DIR/deskcap" ]] || missing+="deskcap binary not built: $DESKCAP_DIR/deskcap (build with: make -C $DESKCAP_DIR)"$'\n'
  python3 -c "import dawdreamer" 2>/dev/null || missing+="python3 module 'dawdreamer' missing (music bed rendering needs it: pip install dawdreamer)"$'\n'
  python3 -c "import fastapi, uvicorn" 2>/dev/null || missing+="TTS server deps missing (fastapi/uvicorn; install: pip install -r $TTS_DIR/requirements-tts.txt)"$'\n'
  if [[ -n "$missing" ]]; then
    fail_block "$missing"
    return 1
  fi
  echo "[render_demo] tools OK."
}

# ---- teardown: kills EVERYTHING this script started, even on failure ---------
GAMESCOPE_PID=""
PIPE_PGID=""
REC_PID=""
AUD_PID=""

cleanup() {
  banner "6/6 teardown" "kill pipeline + gamescope + TTS + audio sink"
  if [[ -n "${REC_PID}" ]] && kill -0 "$REC_PID" 2>/dev/null; then
    kill "$REC_PID" 2>/dev/null || true
    wait "$REC_PID" 2>/dev/null || true
  fi
  if [[ -n "${AUD_PID}" ]] && kill -0 "$AUD_PID" 2>/dev/null; then
    kill "$AUD_PID" 2>/dev/null || true
    wait "$AUD_PID" 2>/dev/null || true
  fi
  if [[ -n "${PIPE_PGID}" ]]; then
    kill -- "-$PIPE_PGID" 2>/dev/null || true
  fi
  if [[ -n "${GAMESCOPE_PID}" ]] && kill -0 "$GAMESCOPE_PID" 2>/dev/null; then
    kill "$GAMESCOPE_PID" 2>/dev/null || true
    wait "$GAMESCOPE_PID" 2>/dev/null || true
  fi
  if [[ -x "$TTS_DIR/stop.sh" ]]; then
    "$TTS_DIR/stop.sh" 2>/dev/null || true
  fi
  if [[ -f "$PIPEWIRE_DIR/teardown_audio_sink.sh" ]]; then
    "$PIPEWIRE_DIR/teardown_audio_sink.sh" 2>/dev/null || true
  fi
  echo "[render_demo] teardown complete."
}

usage() {
  sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}"
  echo "Usage: $(basename "${BASH_SOURCE[0]}") [--check] [--help]"
  echo "  --check   verify inputs exist + print the 6-phase plan; start NOTHING"
}

main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then usage; return 0; fi
  if [[ "${1:-}" == "--check" ]]; then
    check_inputs || return 1
    print_plan
    return 0
  fi
  if [[ $# -gt 0 ]]; then echo "unknown arg: $1 (see --help)" >&2; return 2; fi

  trap cleanup EXIT INT TERM

  banner "1/6 preflight" "verify tools, deps, and input files"
  check_inputs
  check_tools

  banner "2/6 provision" "TTS server + $SINK_NAME sink + gamescope sandbox"
  TTS_PORT="$TTS_PORT" "$TTS_DIR/start.sh"
  for _ in $(seq 1 60); do
    if curl -fs -m 2 "http://$TTS_HOST:$TTS_PORT/healthz" >/dev/null 2>&1; then break; fi
    sleep 2
  done
  curl -fs -m 2 "http://$TTS_HOST:$TTS_PORT/healthz" >/dev/null \
    || { echo "[render_demo] TTS server never answered /healthz on :$TTS_PORT" >&2; return 1; }
  "$PIPEWIRE_DIR/setup_audio_sink.sh"
  # Sandbox runs the demo page; launch_sandbox.sh blocks on capture, so
  # background it: the trap still owns the whole group on EXIT.
  setsid "$GAMESCOPE_DIR/launch_sandbox.sh" "$DEMO_CMD" &
  PIPE_PGID=$!
  GAMESCOPE_PID=$PIPE_PGID
  mkdir -p "$STEMS_DIR"

  banner "3/6 render" "client.py --render per stem into $STEMS_DIR (TEXT-ONLY, seed $TTS_SEED)"
  local id text
  for id in "${STEM_IDS[@]}"; do
    if [[ -n "$STEM_SRC_DIR" ]]; then
      text="$(cat "$STEM_SRC_DIR/$id.txt")"
    else
      text="${STEM_TEXT[$id]}"
    fi
    python3 "$TTS_DIR/client.py" --render "$text" \
      --out "$STEMS_DIR/$id.wav" --host "$TTS_HOST" --port "$TTS_PORT"
  done

  banner "4/6 capture" "gamescope->wf-recorder->deskcap video + monitor-only audio (${BEAT_CLOCK}s beat clock)"
  local raw_video="$WORK_DIR/capture.mkv" app_audio="$WORK_DIR/app_audio.wav"
  setsid env WAYLAND_DISPLAY="$SANDBOX_DISPLAY" \
    wf-recorder -D "$SANDBOX_DISPLAY" -f "$raw_video" &
  REC_PID=$!
  # Monitor ONLY the isolated sink: desktop/system audio can never leak in.
  if command -v ffmpeg >/dev/null 2>&1; then
    ffmpeg -y -f pulse -i "$SINK_NAME.monitor" -t "$BEAT_CLOCK" "$app_audio" &
  else
    timeout "$BEAT_CLOCK" pw-record --target "$SINK_NAME" "$app_audio" &
  fi
  AUD_PID=$!
  # The BEATS driver plays in the sandbox page while capture runs the clock.
  sleep "$BEAT_CLOCK"
  kill "$REC_PID" 2>/dev/null || true; wait "$REC_PID" 2>/dev/null || true; REC_PID=""
  wait "$AUD_PID" 2>/dev/null || true; AUD_PID=""

  banner "5/6 mux" "ffmpeg joins video + FINAL bed + stems -> $OUT"
  local concat_list="$WORK_DIR/stems.txt" stems_mix="$WORK_DIR/stems_concat.wav"
  : > "$concat_list"
  for id in "${STEM_IDS[@]}"; do echo "file '$STEMS_DIR/$id.wav'" >> "$concat_list"; done
  ffmpeg -y -f concat -safe 0 -i "$concat_list" -c:a pcm_s16le "$stems_mix"
  ffmpeg -y -i "$raw_video" -i "$BED_WAV" -i "$stems_mix" -filter_complex \
    "[1:a]volume=0.18[bed];[bed][2:a]amix=inputs=2:duration=longest[mix]" \
    -map 0:v -map "[mix]" -c:v libx264 -c:a aac -shortest "$OUT"
  echo "[render_demo] done: $OUT"

  banner "6/6 teardown" "see trap (runs on EXIT even on failure)"
}

main "$@"
