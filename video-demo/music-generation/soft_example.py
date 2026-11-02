"""Soft 10-second music example: a gentle A-major pad with a slow lullaby lead.

Headless: no audio device needed, RenderEngine renders offline to a buffer.
Run from this directory with the fixture venv:
    ./.venv/bin/python soft_example.py

Design (soft = quiet + slow attack + mellow lowpassed timbre):
  - Pad: three detuned triangle-ish voices (A2/E3/A3/C#4) through a soft
    lowpass, faded in over 4 s so nothing pokes out.
  - Lead: a slow sine lullaby phrase on A-major pentatonic (A4 C#5 E5 ...),
    one note per 2 s with a raised-cosine envelope, mixed ~12 dB under the pad.
  - Master: gentle gain plus a slow amplitude swell so the whole clip
    breathes in and out. Target peak around -24 dBFS.
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
DURATION_SECONDS = 10.0
OUTPUT_NAME = "soft_example.wav"

# Gentle A-major pad: root + fifth + octave + third, lowpassed and quiet.
# Faust traps hit while building this (do not regress):
#   - `time` is reserved (basics.lib BoxIdent) — fades live in numpy.
#   - the mellow lowpass is `fi.lowpass(order, cutoff)`, not `ef.lowpass`.
PAD_DSP = """
declare name "SoftPad";
import("stdfaust.lib");
freqA2  = 110.0;
freqE3  = 164.81;
freqA3  = 220.0;
freqCs4 = 277.18;
voice(f) = f : os.osc : fi.lowpass(2, 900);
mix = voice(freqA2) * 0.30 + voice(freqE3) * 0.22
    + voice(freqA3) * 0.20 + voice(freqCs4) * 0.14;
gain = hslider("level[unit:dB]", -20, -60, 0, 0.1) : ba.db2linear;
process = mix * gain <: si.bus(2);
"""

# Slow lullaby lead: 5 whole notes over the 10 s, soft sine + soft envelope.
LEAD_NOTES_HZ = (440.0, 554.37, 659.25, 554.37, 493.88)  # A4 C#5 E5 C#5 B4
LEAD_NOTE_SECONDS = 2.0


def phrase_envelope(frames: int) -> np.ndarray:
    """One raised-cosine swell per 2 s note, plus a global 10 s swell."""
    t = np.arange(frames) / SAMPLE_RATE
    note_phase = (t % LEAD_NOTE_SECONDS) / LEAD_NOTE_SECONDS
    note_env = 0.5 - 0.5 * np.cos(2.0 * np.pi * note_phase)
    global_env = np.sin(np.pi * np.clip(t / DURATION_SECONDS, 0.0, 1.0)) ** 0.5
    return (note_env * global_env).astype(np.float64)


def render_pad(engine: "daw.RenderEngine") -> np.ndarray:
    pad = engine.make_faust_processor("soft_pad")
    pad.set_dsp_string(PAD_DSP)
    engine.load_graph([(pad, [])])
    pad.set_parameter("/SoftPad/level", -20.0)
    engine.render(DURATION_SECONDS)
    return np.asarray(engine.get_audio(), dtype=np.float64)


def render_lead_line() -> np.ndarray:
    """Render the lead phrase directly with numpy (exact note timing)."""
    frames = int(SAMPLE_RATE * DURATION_SECONDS)
    t = np.arange(frames) / SAMPLE_RATE
    indices = np.clip((t / LEAD_NOTE_SECONDS).astype(int), 0, len(LEAD_NOTES_HZ) - 1)
    freqs = np.array(LEAD_NOTES_HZ, dtype=np.float64)[indices]
    tone = np.sin(2.0 * np.pi * freqs * t)
    tone *= phrase_envelope(frames)
    # Gentle octave shimmer and vibrato for a lullaby feel.
    tone += 0.25 * np.sin(2.0 * np.pi * 2.0 * freqs * t)
    tone *= 1.0 / 1.25
    vibrato = 1.0 + 0.002 * np.sin(2.0 * np.pi * 5.0 * t)
    tone *= vibrato
    stereo = np.stack([tone, tone], axis=0)
    return stereo * 10.0 ** (-32.0 / 20.0)  # lead sits ~12 dB under the pad


def main() -> Path:
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    pad = render_pad(engine)  # shape (2, N) float64

    lead = render_lead_line()
    frames = min(pad.shape[1], lead.shape[1])
    mixed = (pad[:, :frames] + lead[:, :frames]).astype(np.float64)

    # 4 s raised-cosine fade-in on the pad region keeps the attack soft.
    fade4 = int(4.0 * SAMPLE_RATE)
    ramp = 0.5 - 0.5 * np.cos(np.pi * np.arange(fade4) / fade4)
    mixed[:, :fade4] *= 0.15 + 0.85 * ramp

    # Master: soft ceiling plus edge fades so starts/stops never click.
    fade_n = int(0.5 * SAMPLE_RATE)
    edge = np.ones(frames)
    edge[:fade_n] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fade_n) / fade_n)
    edge[-fade_n:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fade_n) / fade_n)
    mixed *= edge
    mixed *= 10.0 ** (-6.0 / 20.0)  # master trim toward -24 dBFS territory

    stereo = np.asarray(mixed.T, dtype=np.float32)
    peak = float(np.max(np.abs(stereo)))
    rms = float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2)))
    if peak <= 0.0:
        raise RuntimeError("Rendered silence; expected a soft audible pad")
    if peak >= 10.0 ** (-12.0 / 20.0):
        raise RuntimeError(f"Too loud for a soft example: peak {peak:.4f} >= -12 dBFS")

    out_path = Path(__file__).resolve().parent / OUTPUT_NAME
    wavfile.write(str(out_path), SAMPLE_RATE, stereo)
    print(
        f"Rendered {stereo.shape[0]} frames "
        f"({stereo.shape[0] / SAMPLE_RATE:.2f}s) "
        f"shape={stereo.shape} peak={peak:.4f} rms={rms:.4f} -> {out_path}"
    )
    return out_path


if __name__ == "__main__":
    main()
