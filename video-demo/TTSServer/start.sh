#!/usr/bin/env bash
# Spin UP the local video-demo TTS server (standalone, port 8002 by default).
# Probes the port first (LAW 7 discipline): if a live server already answers
# /healthz, this script does nothing instead of stacking a second process.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${TTS_PORT:-8002}"
PIDFILE=".tts-server.pid"
LOGFILE=".tts-server.log"

if curl -fs -m 2 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
  echo "TTS server already live on :${PORT} (leaving it alone)."
  exit 0
fi
if [ -f "${PIDFILE}" ] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "Stale live PID in ${PIDFILE}; run ./stop.sh first."
  exit 1
fi
rm -f "${PIDFILE}"

PLAYBACK_FLAGS=""
if [ "${TTS_PLAYBACK:-1}" = "0" ]; then
  PLAYBACK_FLAGS="--no-playback"
fi
PRELOAD_FLAGS=""
if [ "${TTS_PRELOAD:-1}" = "0" ]; then
  PRELOAD_FLAGS="--no-preload"
fi
COMPILE_FLAGS=""
if [ "${TTS_COMPILE:-0}" = "1" ]; then
  COMPILE_FLAGS="--compile"
fi

# shellcheck disable=SC2086
nohup python3 server.py --port "${PORT}" ${PLAYBACK_FLAGS} ${PRELOAD_FLAGS} ${COMPILE_FLAGS} \
  >"${LOGFILE}" 2>&1 &
echo $! >"${PIDFILE}"
echo "TTS server starting on :${PORT} (pid $(cat "${PIDFILE}"), log ${LOGFILE})."
echo "First boot loads ChatTTS weights (1-3 min); poll with:"
echo "  curl http://127.0.0.1:${PORT}/healthz"
