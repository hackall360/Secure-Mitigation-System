#!/usr/bin/env bash
# launch_sandbox.sh — nested Wayland video sandbox feeding the deskcap node.
#
# Usage: ./launch_sandbox.sh "<app command>"
#   e.g. ./launch_sandbox.sh "alacritty -e my_tui"
#
# What it does:
#   1. Starts gamescope as a nested Wayland session locked to 1920x1080 on
#      its own display (WAYLAND_DISPLAY=wayland-99), running your app.
#      The host GNOME session never sees a screen-share prompt because the
#      capture happens entirely inside the sandbox display.
#   2. Points wf-recorder at that sandbox display and captures raw
#      uncompressed YUV420p frames to stdout (-c rawvideo -x yuv420p -f -).
#   3. Pipes that stdout straight into ../deskcap/deskcap, which publishes
#      it as the "Desktop Capture Camera" PipeWire Video/Source node.
#   4. Trap on EXIT/INT/TERM kills the whole capture pipeline process
#      group (recorder + deskcap) and gamescope — no orphans.
#
# Requires: gamescope, wf-recorder, and a built ../deskcap/deskcap binary.

set -euo pipefail

SANDBOX_DISPLAY="wayland-99"
WIDTH=1920
HEIGHT=1080
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKCAP_BIN="$HERE/../deskcap/deskcap"

if [[ $# -lt 1 ]]; then
    echo "usage: $0 \"<app command>\"" >&2
    exit 2
fi
APP_CMD="$*"

for bin in gamescope wf-recorder; do
    if ! command -v "$bin" >/dev/null 2>&1; then
        echo "missing required binary: $bin" >&2
        exit 2
    fi
done
if [[ ! -x "$DESKCAP_BIN" ]]; then
    echo "deskcap binary not found at $DESKCAP_BIN — run: make -C $HERE/../deskcap" >&2
    exit 2
fi

# XDG_RUNTIME_DIR must exist for Wayland sockets.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="$SANDBOX_DISPLAY"

GAMESCOPE_PID=""
PIPE_PGID=""

cleanup() {
    echo "[sandbox] shutting down…" >&2
    # Kill the whole capture-pipeline process group (wf-recorder|deskcap).
    if [[ -n "${PIPE_PGID:-}" ]]; then
        kill -- "-$PIPE_PGID" 2>/dev/null || true
    fi
    if [[ -n "${GAMESCOPE_PID:-}" ]] && kill -0 "$GAMESCOPE_PID" 2>/dev/null; then
        kill "$GAMESCOPE_PID" 2>/dev/null || true
        wait "$GAMESCOPE_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# 1. Nested sandbox: force internal resolution to 1920x1080.
#    gamescope owns $SANDBOX_DISPLAY; the app runs inside it.
gamescope -W "$WIDTH" -H "$HEIGHT" -- bash -c "$APP_CMD" &
GAMESCOPE_PID=$!

# Give the compositor a moment to publish its Wayland socket.
for _ in $(seq 1 50); do
    if [[ -S "$XDG_RUNTIME_DIR/$SANDBOX_DISPLAY" ]]; then
        break
    fi
    sleep 0.1
done

# 2+3. Capture the sandbox display as raw I420 and pipe into deskcap.
#    -D selects the sandbox display; -c rawvideo -x yuv420p emits exactly
#    3110400 bytes/frame, matching deskcap's stdin contract; -f - = stdout.
#    setsid puts recorder+deskcap in their own process group so the trap
#    can kill the whole pipeline (middle-process job PIDs are unreliable).
setsid env WAYLAND_DISPLAY="$SANDBOX_DISPLAY" \
    wf-recorder -D "$SANDBOX_DISPLAY" -c rawvideo -x yuv420p -f - \
    | "$DESKCAP_BIN" &
PIPE_PGID=$!

wait "$PIPE_PGID"
