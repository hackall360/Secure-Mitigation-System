# Headless desktop capture sandbox (`video-demo/desktop-capture/`)

Headless screen-capture + virtual-camera pipeline. Captures a
`gamescope` nested Wayland session (no GNOME portal prompts) and
publishes it as a hardware-style webcam via a custom PipeWire node;
audio stays isolated in a virtual null sink.

Requires host tools: `gamescope`, `wf-recorder`, `gcc` +
`libpipewire-0.3` dev headers, `pactl`, `ffmpeg`/`pw-record`.

## Layout

- `deskcap/` — clean-room C PipeWire `Video/Source` node
  (`pwcam_desktop.c` + `Makefile` → `deskcap` binary).
- `gamescope/` — `launch_sandbox.sh "<app command>"`: nested 1920x1080
  session on `WAYLAND_DISPLAY=wayland-99` → `wf-recorder` rawvideo
  (`-c rawvideo -x yuv420p -f -`) piped into `deskcap`; trap kills the
  pipeline process group + gamescope on exit.
- `pipewire/` — `setup_audio_sink.sh` / `teardown_audio_sink.sh`:
  isolated `IsolatedAppAudio` null sink (`PULSE_SINK=` routing,
  monitor-only record one-liner); see `pipewire/README.md`.

## Node contract (`deskcap`)

- `EnumFormat`: exactly one capability — I420 `1920x1080 @ 60fps`.
- `SPA_PARAM_Buffers`: offers `MemFd | MemPtr` (+ Header meta) — the
  non-DmaBuf path WebRTC capturers map.
- Ingestion: `reader_thread` reads raw I420 frames of exactly
  `3110400` bytes (`1920*1080*1.5`) from stdin in a loop; `on_process`
  `memcpy`s the latest frame into the SPA buffer. No JPEG decode, no
  scaling libraries (`turbojpeg`/`libswscale` absent by design).
- Reference note: the sibling AnyCam tree was studied for architecture
  only (node shape, buffer negotiation mechanics); `pwcam_desktop.c`
  is a 100% clean-room rewrite — different names, structure, comments,
  single locked format instead of a multi-format table, buffer-swap
  intake instead of a decode pipeline.

## Build + quick verify

```bash
make -C video-demo/desktop-capture/deskcap   # produces deskcap/
ldd video-demo/desktop-capture/deskcap/deskcap  # expect libpipewire only
python3 -m pytest tests/test_desktop_capture_red.py -q
```

## Trap learned here

Killing a `producer | consumer &` pipeline by the middle job PID leaves
the tail alive (`kill $!` hits only the last stage; `jobs -p` omits the
middle). Proven live: `kill` on recorded PIDs left `sleep 72` running.
Fix used in `launch_sandbox.sh`: `setsid` the pipeline into its own
process group, trap `kill -- -PGID` for the group + plain `kill` for
gamescope. Verified: group kill left zero strays.
