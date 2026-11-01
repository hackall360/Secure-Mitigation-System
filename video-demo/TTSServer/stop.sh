#!/usr/bin/env bash
# Spin DOWN the local video-demo TTS server. Kills ONLY the PID this tool
# started (tracked pidfile) — never broad-pkill, per sandbox discipline.
set -euo pipefail
cd "$(dirname "$0")"

PIDFILE=".tts-server.pid"

if [ ! -f "${PIDFILE}" ]; then
  echo "No ${PIDFILE}: nothing started by start.sh to stop."
  exit 0
fi
PID="$(cat "${PIDFILE}")"
if kill -0 "${PID}" 2>/dev/null; then
  kill "${PID}"
  for _ in $(seq 1 50); do
    kill -0 "${PID}" 2>/dev/null || break
    sleep 0.2
  done
  if kill -0 "${PID}" 2>/dev/null; then
    echo "PID ${PID} ignored TERM; sending KILL."
    kill -9 "${PID}"
  fi
  echo "TTS server (pid ${PID}) stopped."
else
  echo "PID ${PID} already gone."
fi
rm -f "${PIDFILE}"
