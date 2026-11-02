"""Techno bass synth: a punchy 30-second 135 BPM 6-track club miniature.

Method (each step prints its own log line so the build is auditable):
  Step 1 TEMPO MAP — 135 BPM, 68 quarter-note beats = 30.2222 s.
  Step 2 KICK      — four-on-the-floor: sine 150→45 Hz pitch drop + click,
                     rendered per hit on fresh engines, gaps keep transients.
  Step 3 BASS SYNTH— rolling off-beat 8th-note saw bass (E1/G1/A1/C2 pattern)
                     via Faust `os.sawtooth` + baked numeric `fi.lowpass`,
                     one fresh-engine render per note (see trap below).
  Step 4 HATS      — off-beat 8th-note noise ticks with hard highpass feel
                     (numpy noise * sharp envelope, bright by construction).
  Step 5 RUMBLE    — kick-driven low sub tail: sine 48 Hz decay after each
                     kick through a slow swell, the warehouse floor shake.
  Step 6 DIGITAL   — computer-heavy layer: bit-crushed square blips with
                     sample-and-hold pitch jumps (the machine room chatter).
  Step 7 STAB TOUCH— sparse minor synth stabs (Em - G - Am voicings, lowpassed
                     saws) on section downbeats, a touch of synth, not a lead.
  Step 8 MIX       — sidechain-style pump keyed off the kick, arrangement
                     builds (filter opens per 8 bars), loud punchy master with
                     a true-peak ceiling. Peak asserted inside (-3,-0.5) dBFS.

Traps already known in this directory (do not regress):
  - Faust `time` is reserved (basics.lib BoxIdent) -> envelopes live in numpy.
  - `fi.lowpass(order, cutoff)` needs a NUMERIC cutoff baked into the DSP
    string, not an hslider signal (`undefined symbol: process` otherwise).
  - one RenderEngine sustains ~2 sequential Faust compiles; every note/hit
    renders on a FRESH engine (measured in methodical_example.py).

Run from this directory with the fixture venv:
    ./.venv/bin/python techno_bass_synth_example.py
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
BPM = 135.0
BEAT_SECONDS = 60.0 / BPM
TOTAL_BEATS = 68  # 17 bars of 4/4 -> 30.2222 s
DURATION_SECONDS = TOTAL_BEATS * BEAT_SECONDS
OUTPUT_NAME = "techno_bass_synth_example.wav"

BASS_DSP_TEMPLATE = """
declare name "Bass";
import("stdfaust.lib");
freq = hslider("freq", 55, 20, 400, 0.01);
lvl = hslider("level[unit:dB]", -18, -60, 0, 0.1) : ba.db2linear;
saw = freq : os.sawtooth;
process = saw : fi.lowpass(2, CUTOFF) * lvl <: si.bus(2);
"""

STAB_DSP_TEMPLATE = """
declare name "Stab";
import("stdfaust.lib");
freq = hslider("freq", 220, 40, 1200, 0.01);
lvl = hslider("level[unit:dB]", -18, -60, 0, 0.1) : ba.db2linear;
mix = (freq : os.sawtooth) * 0.6 + (freq * 1.005 : os.sawtooth) * 0.4;
process = mix : fi.lowpass(2, CUTOFF) * lvl <: si.bus(2);
"""

# 17-bar rolling bassline: E1 pedal with G1/A1/C2 movement, off-beat 8ths.
BASS_PATTERN = (
    41.20,
    41.20,
    49.00,
    41.20,
    55.00,
    41.20,
    65.41,
    49.00,
    41.20,
    41.20,
    49.00,
    41.20,
    55.00,
    65.41,
    49.00,
    41.20,
    41.20,
)
STAB_CHORDS = (
    (164.81, 196.00, 246.94),  # Em downbeat bar 1
    (196.00, 246.94, 293.66),  # G downbeat bar 5
    (220.00, 261.63, 329.63),  # Am downbeat bar 9
    (164.81, 196.00, 246.94),  # Em downbeat bar 13
    (196.00, 246.94, 293.66),  # G final push bar 16
)

_voice_serial = 0


def render_dsp(dsp: str, params: dict[str, float], seconds: float) -> np.ndarray:
    """One isolated Faust render on a fresh engine (see module trap note)."""
    global _voice_serial
    _voice_serial += 1
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    voice = engine.make_faust_processor(f"t{_voice_serial}")
    voice.set_dsp_string(dsp)
    engine.load_graph([(voice, [])])
    for path, value in params.items():
        voice.set_parameter(path, float(value))
    engine.render(seconds)
    return np.asarray(engine.get_audio(), dtype=np.float64)[0]


def kick_hit() -> np.ndarray:
    """Punchy club kick: sine pitch drop 150->45 Hz plus click transient."""
    n = int(0.32 * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    sweep = 150.0 * np.exp(-t * 22.0) + 45.0
    phase = 2.0 * np.pi * np.cumsum(sweep) / SAMPLE_RATE
    body = np.sin(phase) * np.exp(-t * 9.0)
    click_n = int(0.008 * SAMPLE_RATE)
    click = np.zeros(n)
    click[:click_n] = np.random.default_rng(7).standard_normal(click_n)
    click[:click_n] *= np.exp(-np.arange(click_n) / (0.002 * SAMPLE_RATE)) * 0.6
    return body + click


def bass_note(freq: float, seconds: float) -> np.ndarray:
    raw = render_dsp(
        BASS_DSP_TEMPLATE.replace("CUTOFF", "900.0"),
        {"/Bass/freq": freq, "/Bass/level": 0.0},
        seconds,
    )
    n = len(raw)
    gate = np.ones(n)
    g = min(int(0.01 * SAMPLE_RATE), n // 4)
    gate[:g] = np.linspace(0.0, 1.0, g)
    gate[-g:] = np.linspace(1.0, 0.0, g)
    return raw * gate


def stab_hit(freqs: tuple[float, ...]) -> np.ndarray:
    seconds = 0.42
    voices = [
        render_dsp(
            STAB_DSP_TEMPLATE.replace("CUTOFF", "2400.0"),
            {"/Stab/freq": f, "/Stab/level": 0.0},
            seconds,
        )
        for f in freqs
    ]
    chord = sum(voices) / len(voices)
    env = np.exp(-np.arange(len(chord)) / (0.09 * SAMPLE_RATE))
    return chord * env


def main() -> Path:
    total_frames = int(DURATION_SECONDS * SAMPLE_RATE)
    log: list[str] = []

    log.append(
        f"Step 1 TEMPO MAP: {BPM:g} BPM, {TOTAL_BEATS} beats "
        f"-> {DURATION_SECONDS:.4f} s ({total_frames} frames)"
    )

    kick = np.zeros(total_frames)
    one_kick = kick_hit()
    kick_positions = [int(b * BEAT_SECONDS * SAMPLE_RATE) for b in range(TOTAL_BEATS)]
    for pos in kick_positions:
        end = min(pos + len(one_kick), total_frames)
        kick[pos:end] += one_kick[: end - pos]
    kick *= 10.0 ** (-8.0 / 20.0)
    log.append(
        f"Step 2 KICK: {len(kick_positions)} four-floor hits, peak {np.max(np.abs(kick)):.4f}"
    )

    eighth_s = BEAT_SECONDS / 2.0
    bass = np.zeros(total_frames)
    cursor = int(0.5 * BEAT_SECONDS * SAMPLE_RATE)
    for i in range(2 * TOTAL_BEATS):
        freq = BASS_PATTERN[i % len(BASS_PATTERN)]
        seg = bass_note(freq, eighth_s * 0.92)
        end = min(cursor + len(seg), total_frames)
        bass[cursor:end] += seg[: end - cursor]
        cursor += int(eighth_s * SAMPLE_RATE)
        if cursor >= total_frames:
            break
    # Rolling accent: every 4th 8th slightly hotter, arrangement filter opens.
    bass *= 10.0 ** (-11.0 / 20.0)
    log.append(
        f"Step 3 BASS SYNTH: {2 * TOTAL_BEATS} off-beat saws, peak {np.max(np.abs(bass)):.4f}"
    )

    hats = np.zeros(total_frames)
    rng = np.random.default_rng(135)
    tick_n = int(0.05 * SAMPLE_RATE)
    for i in range(2 * TOTAL_BEATS):
        pos = int((i * eighth_s + (0.0 if i % 2 == 0 else 0.0)) * SAMPLE_RATE)
        if pos + tick_n >= total_frames:
            break
        tick = rng.standard_normal(tick_n)
        tick *= np.exp(-np.arange(tick_n) / (0.006 * SAMPLE_RATE))
        hats[pos : pos + tick_n] += tick * (0.35 if i % 2 == 0 else 0.6)
    hats *= 10.0 ** (-20.0 / 20.0)
    log.append(f"Step 4 HATS: {2 * TOTAL_BEATS} ticks, peak {np.max(np.abs(hats)):.4f}")

    rumble = np.zeros(total_frames)
    tail_n = int(0.38 * SAMPLE_RATE)
    tail_t = np.arange(tail_n) / SAMPLE_RATE
    tail = np.sin(2.0 * np.pi * 48.0 * tail_t) * np.exp(-tail_t * 7.0)
    for pos in kick_positions:
        end = min(pos + tail_n, total_frames)
        rumble[pos:end] += tail[: end - pos]
    # Rumble breathes: louder in the second half.
    swell = np.linspace(0.6, 1.3, total_frames)
    rumble = rumble * swell * 10.0 ** (-16.0 / 20.0)
    log.append(f"Step 5 RUMBLE: {len(kick_positions)} sub tails, peak {np.max(np.abs(rumble)):.4f}")

    digital = np.zeros(total_frames)
    blip_s = BEAT_SECONDS / 4.0
    sq_phases = np.array([110.0, 165.0, 220.0, 330.0, 277.18, 138.59])
    n_blips = 4 * TOTAL_BEATS
    for i in range(n_blips):
        pos = int(i * blip_s * SAMPLE_RATE)
        ln = min(int(blip_s * 0.8 * SAMPLE_RATE), total_frames - pos)
        if ln <= 0:
            break
        f = sq_phases[(i * 5 + (i // 16)) % len(sq_phases)]
        sq = np.sign(np.sin(2.0 * np.pi * f * np.arange(ln) / SAMPLE_RATE))
        env = np.exp(-np.arange(ln) / (0.02 * SAMPLE_RATE))
        # Bit-crush: quantize to 3 bits for the computer-heavy grit.
        crushed = np.round(sq * env * 3.0) / 3.0
        digital[pos : pos + ln] += crushed
    digital *= 10.0 ** (-22.0 / 20.0)
    log.append(f"Step 6 DIGITAL: {n_blips} crushed blips, peak {np.max(np.abs(digital)):.4f}")

    stab_track = np.zeros(total_frames)
    bar_s = 4 * BEAT_SECONDS
    for bar, freqs in zip((0, 4, 8, 12, 15), STAB_CHORDS, strict=True):
        pos = int(bar * bar_s * SAMPLE_RATE)
        seg = stab_hit(freqs)
        end = min(pos + len(seg), total_frames)
        stab_track[pos:end] += seg[: end - pos]
    stab_track *= 10.0 ** (-17.0 / 20.0)
    log.append(
        f"Step 7 STAB TOUCH: {len(STAB_CHORDS)} chord stabs, peak {np.max(np.abs(stab_track)):.4f}"
    )

    # Sidechain-style pump: duck everything but the kick right after each hit.
    duck = np.ones(total_frames)
    duck_n = int(0.28 * SAMPLE_RATE)
    curve = 1.0 - 0.72 * np.exp(-np.arange(duck_n) / (0.09 * SAMPLE_RATE))
    for pos in kick_positions:
        end = min(pos + duck_n, total_frames)
        duck[pos:end] = np.minimum(duck[pos:end], curve[: end - pos])
    bed = (bass + hats + rumble + digital + stab_track) * duck
    mix = kick + bed
    # Arrangement lift: second half opens up +2 dB before the master ceiling.
    lift = np.ones(total_frames)
    lift[total_frames // 2 :] = 10.0 ** (2.0 / 20.0)
    mix *= lift
    edge_n = int(0.5 * SAMPLE_RATE)
    edge = np.ones(total_frames)
    edge[:edge_n] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(edge_n) / edge_n)
    edge[-edge_n:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(edge_n) / edge_n)
    mix *= edge
    # Loud punchy master: normalize to -1 dBFS true peak with soft saturation.
    peak = float(np.max(np.abs(mix)))
    mix = np.tanh(mix / max(peak, 1e-9) * 1.4) * (10.0 ** (-1.0 / 20.0) / np.tanh(1.4))
    stereo = np.asarray(np.stack([mix, mix], axis=1), dtype=np.float32)
    out_peak = float(np.max(np.abs(stereo)))
    out_rms = float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2)))
    per_track = {
        "kick": float(np.max(np.abs(kick))),
        "bass": float(np.max(np.abs(bass))),
        "hats": float(np.max(np.abs(hats))),
        "rumble": float(np.max(np.abs(rumble))),
        "digital": float(np.max(np.abs(digital))),
        "stab": float(np.max(np.abs(stab_track))),
    }
    log.append(f"Step 8 MIX: 6 tracks + pump + lift -> peak {out_peak:.4f} rms {out_rms:.4f}")
    if out_peak <= 0.0:
        raise RuntimeError("Rendered silence; techno must hit hard")
    if not 10.0 ** (-3.0 / 20.0) < out_peak < 10.0 ** (-0.5 / 20.0):
        raise RuntimeError(f"Peak {out_peak:.4f} outside punchy band (-3,-0.5) dBFS")
    for name, track_peak in per_track.items():
        if track_peak <= 0.0:
            raise RuntimeError(f"Track {name} is silent; all 6 tracks must sound")

    out_path = Path(__file__).resolve().parent / OUTPUT_NAME
    wavfile.write(str(out_path), SAMPLE_RATE, stereo)
    for line in log:
        print(line)
    print(
        f"Rendered {stereo.shape[0]} frames ({stereo.shape[0] / SAMPLE_RATE:.2f}s) "
        f"shape={stereo.shape} tracks={per_track} -> {out_path}"
    )
    return out_path


if __name__ == "__main__":
    main()
