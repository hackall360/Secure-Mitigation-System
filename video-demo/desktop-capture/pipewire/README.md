# Isolated app audio (`pipewire/`)

Video in the sibling `../gamescope/` sandbox is silent by default. These
scripts route **one app's** audio into a private virtual sink so the demo
can be narrated/recorded without ever touching desktop/system audio.

## Setup

```bash
./setup_audio_sink.sh
```

Loads `module-null-sink` as `IsolatedAppAudio` (idempotent — reuses the
sink if it is already up) and records the module index in
`$XDG_RUNTIME_DIR/deskcap-audio-sink.index`.

## Route an app into the sink

```bash
PULSE_SINK=IsolatedAppAudio my_tui_app
PULSE_SINK=IsolatedAppAudio firefox --new-window https://example.com
```

`PULSE_SINK` is honored by PipeWire's PulseAudio layer, so the app's
streams land **exclusively** on `IsolatedAppAudio`. Desktop sounds,
notifications, and other apps keep using the default sink.

## Record only this sink's monitor

The `.monitor` source carries exactly what the isolated app plays —
nothing from the desktop:

```bash
ffmpeg -f pulse -i IsolatedAppAudio.monitor -c:a aac app_only.m4a
```

PipeWire-native alternative:

```bash
pw-record --target IsolatedAppAudio app_only.wav
```

## Teardown

```bash
./teardown_audio_sink.sh
```

Unloads exactly the module index the setup script recorded (with a
name-scoped fallback that still only matches `IsolatedAppAudio`), then
removes the index file. System/desktop modules are never touched; safe
to run when nothing is up.
