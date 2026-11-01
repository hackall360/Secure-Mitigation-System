#!/usr/bin/env bash
# teardown_audio_sink.sh — unload ONLY the IsolatedAppAudio null sink.
#
# Unloads the exact module index recorded by setup_audio_sink.sh, so no
# system/desktop module is ever touched. Safe to run when nothing is up.

set -euo pipefail

SINK_NAME="IsolatedAppAudio"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
RUNTIME_FILE="$RUNTIME_DIR/deskcap-audio-sink.index"

if ! command -v pactl >/dev/null 2>&1; then
    echo "missing required binary: pactl" >&2
    exit 2
fi

if [[ -f "$RUNTIME_FILE" ]]; then
    INDEX="$(cat "$RUNTIME_FILE")"
    if pactl unload-module "$INDEX" 2>/dev/null; then
        echo "[audio] unloaded module $INDEX ('$SINK_NAME')."
    else
        echo "[audio] module $INDEX already gone."
    fi
    rm -f "$RUNTIME_FILE"
else
    # Fallback: resolve the sink's owner module by name (still scoped to
    # our sink only — never unloads anything else).
    OWNER="$(pactl list sinks 2>/dev/null | awk -v name="$SINK_NAME" '
        /^Sink / { cur="" }
        /Name: / { if ($2 == name) cur=1 }
        cur && /Owner Module: / { print $3; exit }')"
    if [[ -n "${OWNER:-}" ]]; then
        pactl unload-module "$OWNER"
        echo "[audio] unloaded '$SINK_NAME' (module $OWNER)."
    else
        echo "[audio] sink '$SINK_NAME' not present — nothing to do."
    fi
fi
