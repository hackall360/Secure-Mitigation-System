#!/usr/bin/env bash
# setup_audio_sink.sh — create the isolated app-audio sink.
#
# Loads module-null-sink as "IsolatedAppAudio". Any app launched with
#   PULSE_SINK=IsolatedAppAudio <app>
# routes its audio exclusively to this virtual sink — the desktop/system
# sink is untouched, so route/unroute never leaks into each other.
#
# Record ONLY this sink's monitor (never the desktop):
#   ffmpeg -f pulse -i IsolatedAppAudio.monitor -c:a aac app_only.m4a
# or: pw-record --target IsolatedAppAudio app_only.wav   (PipeWire-native)
#
# The module index is saved to $RUNTIME_FILE so teardown unloads exactly
# the module this script loaded (never a system module).

set -euo pipefail

SINK_NAME="IsolatedAppAudio"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
RUNTIME_FILE="$RUNTIME_DIR/deskcap-audio-sink.index"

if ! command -v pactl >/dev/null 2>&1; then
    echo "missing required binary: pactl (pipewire-pulse or pulseaudio-utils)" >&2
    exit 2
fi

# Idempotent: reuse the existing sink if one is already up.
if pactl list short sinks 2>/dev/null | grep -qw "$SINK_NAME"; then
    echo "[audio] sink '$SINK_NAME' already present — nothing to do."
    echo "[audio] launch apps with: PULSE_SINK=$SINK_NAME <app>"
    echo "[audio] record monitor only: ffmpeg -f pulse -i $SINK_NAME.monitor -c:a aac app_only.m4a"
    exit 0
fi

INDEX="$(pactl load-module module-null-sink sink_name="$SINK_NAME" \
    sink_properties=device.description="$SINK_NAME")"
echo "$INDEX" > "$RUNTIME_FILE"
chmod 600 "$RUNTIME_FILE"

echo "[audio] sink '$SINK_NAME' created (module index $INDEX)."
echo "[audio] launch apps with: PULSE_SINK=$SINK_NAME <app>"
echo "[audio] record monitor only: ffmpeg -f pulse -i $SINK_NAME.monitor -c:a aac app_only.m4a"
echo "[audio]   (or PipeWire-native: pw-record --target $SINK_NAME app_only.wav)"
echo "[audio] tear down with: ./teardown_audio_sink.sh"
