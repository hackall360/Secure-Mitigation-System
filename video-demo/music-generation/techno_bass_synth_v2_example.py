"""Techno bass synth v2: the 30-second track with A B A C A B A D sections.

V2 answers the v1 note ("it was okay"): the groove now modulates
periodically instead of running one static texture for 30 s. Eight
4-beat sections (1.7778 s each) morph, drop out, and change over time:

  A (0-1, 2-3, 4-5, 6-7 of the form) — full groove: everything in.
  B (sections 1, 5) — bass dropout: kick/hats/digital/stab stay, bass and
      rumble drop to near silence, hats+digital lift +2 dB to fill the hole.
  C (section 3) — rumble+bass feature: kick, hats, and digital drop out,
      bass cutoff opens wide, rumble swells; the floor-shake breakdown.
  D (section 7) — maximal outro: every track in, +2 dB lift, brightest
      bass cutoff; then the 30th-second fade carries it out.

Slow morphs are per-section gain + per-note lowpass cutoff plans (numeric
cutoffs baked into the DSP string — trap-safe). Fades: the first second
fades in and the last (30th) second fades out with raised-cosine edges,
applied at mastering AFTER peak normalization so the wav truly starts and
ends near silence.

Run from this directory with the fixture venv:
    ./.venv/bin/python techno_bass_synth_v2_example.py
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
OUTPUT_NAME = "techno_bass_synth_v2_example.wav"

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

# 8 sections x 4 beats: A B A C A B A D. Each entry names the section and
# the per-track gain multipliers + bass lowpass cutoff that voice it.
# A = full groove, B = bass/rumble dropout, C = rumble+bass feature,
# D = maximal outro.
SECTIONS = (
    {
        "label": "A",
        "beats": (0, 4),
        "bass": 1.0,
        "rumble": 1.0,
        "kick": 1.0,
        "hats": 1.0,
        "digital": 1.0,
        "stab": 1.0,
        "cutoff": 900.0,
    },
    {
        "label": "B",
        "beats": (4, 8),
        "bass": 0.0,
        "rumble": 0.05,
        "kick": 1.0,
        "hats": 1.26,
        "digital": 1.26,
        "stab": 1.0,
        "cutoff": 900.0,
    },
    {
        "label": "A",
        "beats": (8, 12),
        "bass": 1.0,
        "rumble": 1.0,
        "kick": 1.0,
        "hats": 1.0,
        "digital": 1.0,
        "stab": 1.0,
        "cutoff": 1100.0,
    },
    {
        "label": "C",
        "beats": (12, 16),
        "bass": 1.15,
        "rumble": 1.6,
        "kick": 0.0,
        "hats": 0.0,
        "digital": 0.0,
        "stab": 0.0,
        "cutoff": 1600.0,
    },
    {
        "label": "A",
        "beats": (16, 20),
        "bass": 1.0,
        "rumble": 1.0,
        "kick": 1.0,
        "hats": 1.0,
        "digital": 1.0,
        "stab": 1.0,
        "cutoff": 1100.0,
    },
    {
        "label": "B",
        "beats": (20, 24),
        "bass": 0.0,
        "rumble": 0.05,
        "kick": 1.0,
        "hats": 1.26,
        "digital": 1.26,
        "stab": 1.0,
        "cutoff": 900.0,
    },
    {
        "label": "A",
        "beats": (24, 28),
        "bass": 1.0,
        "rumble": 1.0,
        "kick": 1.0,
        "hats": 1.0,
        "digital": 1.0,
        "stab": 1.0,
        "cutoff": 1400.0,
    },
    {
        "label": "D",
        "beats": (28, 32),
        "bass": 1.2,
        "rumble": 1.3,
        "kick": 1.0,
        "hats": 1.2,
        "digital": 1.2,
        "stab": 1.0,
        "cutoff": 3200.0,
    },
)
# The 68-beat track holds 17 bars; the 8-section plan covers the first
# 32 beats (8 bars) and then repeats with the D outro stretched over the
# final bar so the form reads A B A C A B A D across the whole 30 s.
SECTION_REPEATS = (0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 3, 4, 5, 6, 7, 7)

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
    (164.81, 196.00, 246.94),
    (196.00, 246.94, 293.66),
    (220.00, 261.63, 329.63),
    (164.81, 196.00, 246.94),
    (196.00, 246.94, 293.66),
)

_voice_serial = 0


def render_dsp(dsp: str, params: dict[str, float], seconds: float) -> np.ndarray:
    """One isolated Faust render on a fresh engine (directory trap note)."""
    global _voice_serial
    _voice_serial += 1
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    voice = engine.make_faust_processor(f"v{_voice_serial}")
    voice.set_dsp_string(dsp)
    engine.load_graph([(voice, [])])
    for path, value in params.items():
        voice.set_parameter(path, float(value))
    engine.render(seconds)
    return np.asarray(engine.get_audio(), dtype=np.float64)[0]


def section_at(beat: float) -> dict:
    bar = min(int(beat // 4), len(SECTION_REPEATS) - 1)
    return SECTIONS[SECTION_REPEATS[bar]]


def kick_hit() -> np.ndarray:
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


def bass_note(freq: float, seconds: float, cutoff: float) -> np.ndarray:
    raw = render_dsp(
        BASS_DSP_TEMPLATE.replace("CUTOFF", f"{float(cutoff):.1f}"),
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
    form = " ".join(SECTIONS[i]["label"] for i in SECTION_REPEATS[:8])

    log.append(
        f"Step 1 FORM: {BPM:g} BPM, {TOTAL_BEATS} beats "
        f"-> {DURATION_SECONDS:.4f} s; sections A B A C A B A D x2 + D out "
        f"(first 8: {form})"
    )

    kick = np.zeros(total_frames)
    one_kick = kick_hit()
    kick_positions = [int(b * BEAT_SECONDS * SAMPLE_RATE) for b in range(TOTAL_BEATS)]
    gained_kicks = 0
    for b in range(TOTAL_BEATS):
        pos = kick_positions[b]
        gain = section_at(b + 0.001)["kick"]
        if gain == 0.0:
            continue
        gained_kicks += 1
        end = min(pos + len(one_kick), total_frames)
        kick[pos:end] += one_kick[: end - pos] * gain
    kick *= 10.0 ** (-8.0 / 20.0)
    log.append(
        f"Step 2 KICK: {gained_kicks}/{len(kick_positions)} hits (C drops out), peak {np.max(np.abs(kick)):.4f}"
    )

    eighth_s = BEAT_SECONDS / 2.0
    bass = np.zeros(total_frames)
    cursor = int(0.5 * BEAT_SECONDS * SAMPLE_RATE)
    n_bass = 0
    for i in range(2 * TOTAL_BEATS):
        beat = (cursor / SAMPLE_RATE) / BEAT_SECONDS
        plan = section_at(beat)
        if plan["bass"] > 0.0:
            freq = BASS_PATTERN[i % len(BASS_PATTERN)]
            seg = bass_note(freq, eighth_s * 0.92, plan["cutoff"])
            end = min(cursor + len(seg), total_frames)
            bass[cursor:end] += seg[: end - cursor] * plan["bass"]
            n_bass += 1
        cursor += int(eighth_s * SAMPLE_RATE)
        if cursor >= total_frames:
            break
    bass *= 10.0 ** (-11.0 / 20.0)
    log.append(
        f"Step 3 BASS: {n_bass} saws, cutoff morphs 900->3200 by plan, peak {np.max(np.abs(bass)):.4f}"
    )

    hats = np.zeros(total_frames)
    rng = np.random.default_rng(135)
    tick_n = int(0.05 * SAMPLE_RATE)
    n_hats = 0
    for i in range(2 * TOTAL_BEATS):
        beat = (i * eighth_s) / BEAT_SECONDS
        gain = section_at(beat)["hats"]
        if gain == 0.0:
            continue
        pos = int(i * eighth_s * SAMPLE_RATE)
        if pos + tick_n >= total_frames:
            break
        tick = rng.standard_normal(tick_n)
        tick *= np.exp(-np.arange(tick_n) / (0.006 * SAMPLE_RATE))
        hats[pos : pos + tick_n] += tick * (0.35 if i % 2 == 0 else 0.6) * gain
        n_hats += 1
    hats *= 10.0 ** (-20.0 / 20.0)
    log.append(f"Step 4 HATS: {n_hats} ticks (C drops out), peak {np.max(np.abs(hats)):.4f}")

    rumble = np.zeros(total_frames)
    tail_n = int(0.38 * SAMPLE_RATE)
    tail_t = np.arange(tail_n) / SAMPLE_RATE
    tail = np.sin(2.0 * np.pi * 48.0 * tail_t) * np.exp(-tail_t * 7.0)
    n_rumble = 0
    for b in range(TOTAL_BEATS):
        gain = section_at(b + 0.001)["rumble"]
        if gain == 0.0:
            continue
        pos = kick_positions[b]
        end = min(pos + tail_n, total_frames)
        rumble[pos:end] += tail[: end - pos] * gain
        n_rumble += 1
    swell = np.linspace(0.6, 1.3, total_frames)
    rumble = rumble * swell * 10.0 ** (-16.0 / 20.0)
    log.append(
        f"Step 5 RUMBLE: {n_rumble} sub tails (B ducked, C featured), peak {np.max(np.abs(rumble)):.4f}"
    )

    digital = np.zeros(total_frames)
    blip_s = BEAT_SECONDS / 4.0
    sq_phases = np.array([110.0, 165.0, 220.0, 330.0, 277.18, 138.59])
    n_blips = 0
    for i in range(4 * TOTAL_BEATS):
        beat = (i * blip_s) / BEAT_SECONDS
        gain = section_at(beat)["digital"]
        if gain == 0.0:
            continue
        pos = int(i * blip_s * SAMPLE_RATE)
        ln = min(int(blip_s * 0.8 * SAMPLE_RATE), total_frames - pos)
        if ln <= 0:
            break
        f = sq_phases[(i * 5 + (i // 16)) % len(sq_phases)]
        sq = np.sign(np.sin(2.0 * np.pi * f * np.arange(ln) / SAMPLE_RATE))
        env = np.exp(-np.arange(ln) / (0.02 * SAMPLE_RATE))
        digital[pos : pos + ln] += (np.round(sq * env * 3.0) / 3.0) * gain
        n_blips += 1
    digital *= 10.0 ** (-22.0 / 20.0)
    log.append(
        f"Step 6 DIGITAL: {n_blips} crushed blips (C drops out), peak {np.max(np.abs(digital)):.4f}"
    )

    stab_track = np.zeros(total_frames)
    bar_s = 4 * BEAT_SECONDS
    n_stabs = 0
    for bar, freqs in zip((0, 4, 8, 10, 16), STAB_CHORDS, strict=True):
        if section_at(bar + 0.001)["stab"] == 0.0:
            continue
        pos = int(bar * bar_s * SAMPLE_RATE)
        seg = stab_hit(freqs)
        end = min(pos + len(seg), total_frames)
        stab_track[pos:end] += seg[: end - pos]
        n_stabs += 1
    stab_track *= 10.0 ** (-17.0 / 20.0)
    log.append(
        f"Step 7 STABS: {n_stabs} chord hits (C drops out), peak {np.max(np.abs(stab_track)):.4f}"
    )

    duck = np.ones(total_frames)
    duck_n = int(0.28 * SAMPLE_RATE)
    curve = 1.0 - 0.72 * np.exp(-np.arange(duck_n) / (0.09 * SAMPLE_RATE))
    for pos in kick_positions:
        end = min(pos + duck_n, total_frames)
        duck[pos:end] = np.minimum(duck[pos:end], curve[: end - pos])
    bed = (bass + hats + rumble + digital + stab_track) * duck
    mix = kick + bed
    d_lift = np.ones(total_frames)
    d_lift[int(28 * BEAT_SECONDS * SAMPLE_RATE) :] = 10.0 ** (2.0 / 20.0)
    mix *= d_lift
    # Punchy master FIRST: normalize to -1 dBFS with soft saturation ...
    peak = float(np.max(np.abs(mix)))
    mix = np.tanh(mix / max(peak, 1e-9) * 1.4) * (10.0 ** (-1.0 / 20.0) / np.tanh(1.4))
    # ... THEN the requested edge fades, so head/tail truly reach silence.
    fade_head = int(1.0 * SAMPLE_RATE)
    fade_tail = int(1.0 * SAMPLE_RATE)
    mix[:fade_head] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fade_head) / fade_head)
    tail_curve = 0.5 + 0.5 * np.cos(np.pi * np.arange(fade_tail) / fade_tail)
    mix[-fade_tail:] *= tail_curve
    stereo = np.asarray(np.stack([mix, mix], axis=1), dtype=np.float32)
    out_peak = float(np.max(np.abs(stereo)))
    out_rms = float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2)))
    head_rms = float(np.sqrt(np.mean(stereo[: int(0.1 * SAMPLE_RATE)].astype(np.float64) ** 2)))
    tail_rms = float(np.sqrt(np.mean(stereo[-int(0.1 * SAMPLE_RATE) :].astype(np.float64) ** 2)))
    per_track = {
        "kick": float(np.max(np.abs(kick))),
        "bass": float(np.max(np.abs(bass))),
        "hats": float(np.max(np.abs(hats))),
        "rumble": float(np.max(np.abs(rumble))),
        "digital": float(np.max(np.abs(digital))),
        "stab": float(np.max(np.abs(stab_track))),
    }
    log.append(
        f"Step 8 MIX: 6 tracks + pump + D lift + 1 s head / 30th-s tail fades "
        f"-> peak {out_peak:.4f} rms {out_rms:.4f} head100ms {head_rms:.5f} tail100ms {tail_rms:.5f}"
    )
    if out_peak <= 0.0:
        raise RuntimeError("Rendered silence; techno must hit hard")
    if not 10.0 ** (-3.0 / 20.0) < out_peak < 10.0 ** (-0.5 / 20.0):
        raise RuntimeError(f"Peak {out_peak:.4f} outside punchy band (-3,-0.5) dBFS")
    if head_rms >= 0.02 or tail_rms >= 0.02:
        raise RuntimeError(
            f"Edge fades missed: head {head_rms:.5f} tail {tail_rms:.5f} (need < 0.02)"
        )
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
