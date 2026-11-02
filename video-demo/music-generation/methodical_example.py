"""Methodical 10-second composition: a step-by-step scored miniature in A major.

Method (each step prints its own log line so the build is auditable):
  Step 1 TEMPO MAP   — 92 BPM, 16 quarter-note beats = 10.43 s total.
  Step 2 HARMONY     — Amaj7 | F#m7 | D9 | E7, one chord per 4 beats.
  Step 3 BASS        — roots A1/F#1/D2/E2, one note per chord, sine + soft edge.
  Step 4 PADS        — chord thirds/sevenths (C#4/G#3, A3/E4, F#3/C4, G#3/D4),
                       each rendered per chord then crossfaded in numpy.
  Step 5 LEAD        — 8 half-beats: A4 B4 C#5 E5 D5 C#5 B4 A4, per-note renders.
  Step 6 MIX         — bass -26 dB, pad -24 dB, lead -27 dB, global swell,
                       0.5 s edge fades. Peak asserted inside (-30,-12) dBFS.

Measured DawDreamer semantic (do not guess): each `RenderEngine.render()`
call REPLACES the buffer (probe: two 1 s renders each returned (2, 44100),
not (2, 88200)). So every note/chord is an isolated render with its own
tempo-derived duration, and assembly is explicit sample-accurate
concatenation in numpy.

Run from this directory with the fixture venv:
    ./.venv/bin/python methodical_example.py
"""

# NOTE: within third-party imports, dawdreamer must stay first: it must be
# imported before any LLVM-based libraries (jax, numba, torchscript, ...)
# or LLVM init conflicts can segfault.
# Reference: https://github.com/DBraun/DawDreamer (Known Issues).
from pathlib import Path

import dawdreamer as daw
import numpy as np
from scipy.io import wavfile

SAMPLE_RATE = 44100
BLOCK_SIZE = 512
BPM = 92.0
BEAT_SECONDS = 60.0 / BPM
TOTAL_BEATS = 16
DURATION_SECONDS = TOTAL_BEATS * BEAT_SECONDS  # 10.4348 s
OUTPUT_NAME = "methodical_example.wav"

# Faust traps already known in this directory (do not regress):
#   - `time` is reserved (basics.lib BoxIdent) -> envelopes live in numpy.
#   - mellow lowpass is `fi.lowpass(order, cutoff)`, not `ef.lowpass`.
NOTE_DSP_TEMPLATE = """
declare name "Note";
import("stdfaust.lib");
freq = hslider("freq", 440, 20, 4000, 0.01);
lvl = hslider("level[unit:dB]", -18, -60, 0, 0.1) : ba.db2linear;
process = freq : os.osc : fi.lowpass(2, CUTOFF) * lvl <: si.bus(2);
"""

CHORDS = (
    {"name": "Amaj7", "beats": (0, 4), "bass": 55.00, "pad": (277.18, 207.65)},
    {"name": "F#m7", "beats": (4, 8), "bass": 46.25, "pad": (220.00, 329.63)},
    {"name": "D9", "beats": (8, 12), "bass": 73.42, "pad": (174.61, 261.63)},
    {"name": "E7", "beats": (12, 16), "bass": 82.41, "pad": (207.65, 293.66)},
)
LEAD_PHRASE = (
    (0.0, 440.00),  # A4
    (2.0, 493.88),  # B4
    (4.0, 554.37),  # C#5
    (6.0, 659.25),  # E5
    (8.0, 587.33),  # D5
    (10.0, 554.37),  # C#5
    (12.0, 493.88),  # B4
    (14.0, 440.00),  # A4
)
LEAD_BEATS = 2.0
DB = {
    "bass": -26.0,
    "pad": -24.0,
    "lead": -27.0,
    "master": -6.0,
}


def db_to_lin(db: float) -> float:
    return 10.0 ** (db / 20.0)


def raised_cosine(n: int) -> np.ndarray:
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / max(n - 1, 1))


def apply_edges(mono: np.ndarray, fade_s: float = 0.02) -> np.ndarray:
    n = min(int(fade_s * SAMPLE_RATE), len(mono) // 4)
    window = raised_cosine(2 * n)
    mono = mono.copy()
    mono[:n] *= window[:n]
    mono[-n:] *= window[n:]
    return mono


_voice_serial = 0


def render_note(freq: float, seconds: float, cutoff: float, level_db: float) -> np.ndarray:
    """Render one note on a FRESH engine (measured: one engine sustains ~2
    sequential Faust compiles, then fails with `undefined symbol: process`;
    a fresh RenderEngine per note renders all 20 score notes reliably)."""
    global _voice_serial
    _voice_serial += 1
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    name = f"note_{_voice_serial}"
    voice = engine.make_faust_processor(name)
    voice.set_dsp_string(NOTE_DSP_TEMPLATE.replace("CUTOFF", f"{float(cutoff):.1f}"))
    engine.load_graph([(voice, [])])
    voice.set_parameter("/Note/freq", float(freq))
    voice.set_parameter("/Note/level", float(level_db))
    engine.render(seconds)
    audio = np.asarray(engine.get_audio(), dtype=np.float64)
    return apply_edges(audio[0])


def assemble(segments: list[np.ndarray], total_frames: int) -> np.ndarray:
    track = np.zeros(total_frames)
    cursor = 0
    for seg in segments:
        end = min(cursor + len(seg), total_frames)
        track[cursor:end] += seg[: end - cursor]
        cursor = end
    return track


def main() -> Path:
    total_frames = int(DURATION_SECONDS * SAMPLE_RATE)
    log: list[str] = []

    chord_s = 4 * BEAT_SECONDS
    log.append(
        f"Step 1 TEMPO MAP: {BPM:g} BPM, {TOTAL_BEATS} beats -> {DURATION_SECONDS:.4f} s ({total_frames} frames)"
    )

    log.append(
        "Step 2 HARMONY: "
        + " | ".join(f"{c['name']} beats {c['beats'][0]}-{c['beats'][1]}" for c in CHORDS)
    )

    bass_segs = [render_note(c["bass"], chord_s, 500.0, 0.0) for c in CHORDS]
    bass = assemble(bass_segs, total_frames) * db_to_lin(DB["bass"])
    log.append(
        f"Step 3 BASS: 4 root renders x {chord_s:.4f} s -> {len(bass_segs)} segments, peak {np.max(np.abs(bass)):.4f}"
    )

    pad_segs: list[np.ndarray] = []
    for c in CHORDS:
        voices = [render_note(f, chord_s, 1200.0, 0.0) for f in c["pad"]]
        pad_segs.append(sum(voices) / len(voices))
    pad = assemble(pad_segs, total_frames) * db_to_lin(DB["pad"])
    log.append(f"Step 4 PADS: 8 chord-tone renders (2/chord) -> peak {np.max(np.abs(pad)):.4f}")

    note_s = LEAD_BEATS * BEAT_SECONDS
    lead_segs = [render_note(f, note_s, 2500.0, 0.0) for _, f in LEAD_PHRASE]
    lead = assemble(lead_segs, total_frames) * db_to_lin(DB["lead"])
    log.append(
        f"Step 5 LEAD: 8 half-note renders x {note_s:.4f} s -> peak {np.max(np.abs(lead)):.4f}"
    )

    mix = bass + pad + lead
    swell = np.sin(np.pi * np.clip(np.arange(total_frames) / total_frames, 0.0, 1.0)) ** 0.5
    mix *= 0.35 + 0.65 * swell
    fade_n = int(0.5 * SAMPLE_RATE)
    edge = np.ones(total_frames)
    edge[:fade_n] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fade_n) / fade_n)
    edge[-fade_n:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fade_n) / fade_n)
    mix *= edge * db_to_lin(DB["master"])
    stereo = np.asarray(np.stack([mix, mix], axis=1), dtype=np.float32)
    peak = float(np.max(np.abs(stereo)))
    rms = float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2)))
    log.append(
        f"Step 6 MIX: bass {DB['bass']} dB + pad {DB['pad']} dB + lead {DB['lead']} dB, master {DB['master']} dB "
        f"-> peak {peak:.4f} rms {rms:.4f}"
    )
    if peak <= 0.0:
        raise RuntimeError("Rendered silence; methodical score must be audible")
    if not db_to_lin(-30.0) < peak < db_to_lin(-12.0):
        raise RuntimeError(f"Peak {peak:.4f} outside methodical soft band (-30,-12) dBFS")

    out_path = Path(__file__).resolve().parent / OUTPUT_NAME
    wavfile.write(str(out_path), SAMPLE_RATE, stereo)
    for line in log:
        print(line)
    print(
        f"Rendered {stereo.shape[0]} frames ({stereo.shape[0] / SAMPLE_RATE:.2f}s) shape={stereo.shape} -> {out_path}"
    )
    return out_path


if __name__ == "__main__":
    main()
