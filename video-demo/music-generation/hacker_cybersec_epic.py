"""Hacker / Cyber-Security epic: 180 s D Phrygian industrial-darksynth breach arc.

Method (each phase prints its own log line so the build is auditable):
  FORM @110 BPM — A(0-30) B(30-60) A'(60-75) C(75-135) B'(135-165) Out(165-180).
  Track 1 SUB-DRONE (The Mainframe) — detuned saws (f, f*1.015) on D2/D1,
    24 dB/oct lowpass with LFO-driven VARIABLE cutoff (probed working),
    `ef.cubicnl` soft-clip + dcblocker. Faust hslider params (freq, cutoff,
    lfo_rate, drive) automated from Python via `set_automation()` with
    audio-rate numpy arrays: slow cutoff opening in A, faster LFO in A',
    aggressive drive in C, sweep-down to silence in the Outro.
  Track 2 DATA ARPEGGIATOR (Network Traffic) — square-wave sharp pluck
    (0 attack / short decay / 0 sustain), 1/16th-note D Phrygian figure on
    D3 Eb3 G3 A3 with a poly-5 step rotation (the critical D->Eb minor
    second keeps the tension unresolved), feedback delay + freeverb space.
  Track 3 INDUSTRIAL KICK (System Pulse) — sine 150->40 Hz pitch drop with
    metallic overdrive, 4-on-the-floor quarter-note trigger in B and C
    (fading out across B'), silent elsewhere.
  Track 4 GLITCH ARTIFACTS (Kernel Panic) — filtered noise + sample-and-hold
    stepped signal through a bitcrusher; volume automation brings it up ONLY
    in section C.
  MIX — phase-gain automation per track (np.linspace-smoothed, never blocky
    except kick triggers), sidechain-style pump under the kick, final
    normalization to -1 dBFS peak (no clipping by construction).

Measured Faust/env semantics in THIS directory (do not regress):
  - `time` is reserved (basics.lib BoxIdent) -> envelopes live in numpy.
  - `fi.lowpass(order, cutoff)` needs a Faust-side VARIABLE (not an hslider
    signal) for modulation; bare `ef.lowpass` does not exist.
  - one RenderEngine sustains ~2 sequential Faust compiles; section stems
    render on FRESH engines, then assemble in numpy (as in techno v2).
  - `set_automation(path, float32_array)` round-trips (probed True, len kept).

Run from this directory with the fixture venv:
    ./.venv/bin/python hacker_cybersec_epic.py
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
BPM = 110.0
BEAT_SECONDS = 60.0 / BPM
TOTAL_SECONDS = 180.0
TOTAL_FRAMES = int(TOTAL_SECONDS * SAMPLE_RATE)
OUTPUT_NAME = "hacker_cybersec_epic.wav"

# D Phrygian: D Eb F G A Bb C. D->Eb minor 2nd = the tension interval.
D1 = 36.71
D2 = 73.42
D3, EB3, G3, A3 = 146.83, 155.56, 196.00, 220.00
ARP_FIGURE = (D3, EB3, D3, G3, EB3, A3, G3, EB3)  # 8 x 1/16, poly-5 rotation
ARP_ROTATION = 5

DRONE_DSP = """
declare name "Mainframe";
import("stdfaust.lib");
f = hslider("freq", 73.42, 20, 200, 0.01);
cut = hslider("cutoff", 400, 40, 4000, 1);
lfor = hslider("lfo_rate", 0.1, 0.01, 8, 0.001);
drv = hslider("drive", 0.5, 0.0, 0.95, 0.01);
lfo = os.osc(lfor) * 0.5 + 0.5;
fc = max(40.0, cut * (0.35 + 0.65 * lfo));
saw = (f : os.sawtooth) * 0.5 + ((f * 1.015) : os.sawtooth) * 0.5;
filt = saw : fi.lowpass(4, fc);
proc = filt : ef.cubicnl(drv, 0) : fi.dcblocker;
process = proc * 0.7 <: si.bus(2);
"""

ARP_DSP = """
declare name "Arp";
import("stdfaust.lib");
f = hslider("freq", 146.83, 40, 1200, 0.01);
gate = hslider("gate", 0, 0, 1, 1);
env = gate : si.smoo;
sq = f : os.square;
dry = sq * env * 0.4;
dly = dry : de.delay(44100, 14700) : *(0.35);
wet = dry + dly;
verb = wet <: re.mono_freeverb(0.4, 0.5, 0.5, 0.5), re.mono_freeverb(0.4, 0.5, 0.5, 0.7) :> *(0.5);
process = verb <: si.bus(1);
"""

KICK_DSP = """
declare name "Pulse";
import("stdfaust.lib");
trig = hslider("trig", 0, 0, 1, 1);
pitch = 40.0 + 110.0 * (trig : si.smoo);
tone = os.osc(pitch) * trig;
metal = tone : ef.cubicnl(0.9, 0) : fi.dcblocker;
process = metal * 0.8 <: si.bus(2);
"""

GLITCH_DSP = """
declare name "KernelPanic";
import("stdfaust.lib");
rate = hslider("rate", 6, 1, 40, 0.1);
hold = no.noise : ba.sAndH(rate * 100) ;
crushed = hold * 0.6 + no.noise * 0.4;
shaped = crushed : fi.lowpass(2, 3000);
process = shaped * 0.35 <: si.bus(2);
"""


def smooth_plan(points: list[tuple[float, float]], n: int, smooth_s: float = 2.0) -> np.ndarray:
    """Piecewise-linear plan through (time_s, value) with raised-cosine edges."""
    times = np.array([p[0] for p in points])
    values = np.array([p[1] for p in points])
    grid = np.arange(n) / SAMPLE_RATE
    plan = np.interp(grid, times, values).astype(np.float64)
    w = min(int(smooth_s * SAMPLE_RATE), n // 4)
    if w > 1:
        kernel = 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(w) / (w - 1))
        kernel /= kernel.sum()
        plan = np.convolve(np.pad(plan, w, mode="edge"), kernel, mode="valid")
        plan = plan[w // 2 : w // 2 + n]
    return plan[:n]


def render_drone(
    freq_plan: np.ndarray, cut_plan: np.ndarray, lfo_plan: np.ndarray, drv_plan: np.ndarray
) -> np.ndarray:
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    voice = engine.make_faust_processor("drone")
    voice.set_dsp_string(DRONE_DSP)
    engine.load_graph([(voice, [])])
    for path, plan in (
        ("/Mainframe/freq", freq_plan),
        ("/Mainframe/cutoff", cut_plan),
        ("/Mainframe/lfo_rate", lfo_plan),
        ("/Mainframe/drive", drv_plan),
    ):
        voice.set_automation(path, plan.astype(np.float32))
    engine.render(TOTAL_SECONDS)
    return np.asarray(engine.get_audio(), dtype=np.float64)


def render_arp(notes: list[tuple[float, float]]) -> np.ndarray:
    """One fresh engine: gate automation fires each 1/16 pluck, freq follows."""
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    voice = engine.make_faust_processor("arp")
    voice.set_dsp_string(ARP_DSP)
    engine.load_graph([(voice, [])])
    freq_auto = np.zeros(TOTAL_FRAMES, dtype=np.float32)
    gate_auto = np.zeros(TOTAL_FRAMES, dtype=np.float32)
    for start_s, freq in notes:
        start = int(start_s * SAMPLE_RATE)
        ln = min(int(0.10 * SAMPLE_RATE), TOTAL_FRAMES - start)
        if ln <= 0:
            continue
        freq_auto[start : start + ln] = freq
        gate_auto[start : start + ln] = 1.0
    voice.set_automation("/Arp/freq", freq_auto)
    voice.set_automation("/Arp/gate", gate_auto)
    engine.render(TOTAL_SECONDS)
    return np.asarray(engine.get_audio(), dtype=np.float64)


def render_kick(hits: list[float], vels: list[float]) -> np.ndarray:
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    voice = engine.make_faust_processor("kick")
    voice.set_dsp_string(KICK_DSP)
    engine.load_graph([(voice, [])])
    trig = np.zeros(TOTAL_FRAMES, dtype=np.float32)
    for start_s, vel in zip(hits, vels, strict=True):
        start = int(start_s * SAMPLE_RATE)
        ln = min(int(0.28 * SAMPLE_RATE), TOTAL_FRAMES - start)
        if ln <= 0:
            continue
        trig[start : start + ln] = float(vel)
    voice.set_automation("/Pulse/trig", trig)
    engine.render(TOTAL_SECONDS)
    return np.asarray(engine.get_audio(), dtype=np.float64)


def render_glitch(rate_plan: np.ndarray) -> np.ndarray:
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    voice = engine.make_faust_processor("glitch")
    voice.set_dsp_string(GLITCH_DSP)
    engine.load_graph([(voice, [])])
    voice.set_automation("/KernelPanic/rate", rate_plan.astype(np.float32))
    engine.render(TOTAL_SECONDS)
    return np.asarray(engine.get_audio(), dtype=np.float64)


def to_stereo(mono_or_stereo: np.ndarray) -> np.ndarray:
    a = np.asarray(mono_or_stereo, dtype=np.float64)
    if a.ndim == 1:
        return np.stack([a, a], axis=0)
    if a.shape[0] == 2:
        return a
    if a.shape[0] == 1:
        return np.stack([a[0], a[0]], axis=0)
    return np.stack([a[:, 0], a[:, 1]], axis=0)


def section_rms(mix: np.ndarray, start_s: float, end_s: float) -> float:
    seg = mix[:, int(start_s * SAMPLE_RATE) : int(end_s * SAMPLE_RATE)]
    return float(np.sqrt(np.mean(seg**2)))


def main() -> Path:
    log: list[str] = []
    log.append(
        f"FORM: {BPM:g} BPM D Phrygian, A(0-30) B(30-60) A'(60-75) C(75-135) B'(135-165) Out(165-180)"
    )

    # ---- Track 1 automation: drone rides the whole 180 s arc ----
    t = np.arange(TOTAL_FRAMES) / SAMPLE_RATE
    freq_plan = np.where(t < 60.0, D2, np.where(t < 135.0, D2, D1))
    cut_plan = smooth_plan(
        [
            (0, 160),
            (30, 900),
            (60, 500),
            (75, 1400),
            (135, 1600),
            (150, 900),
            (165, 700),
            (180, 60),
        ],
        TOTAL_FRAMES,
    )
    lfo_plan = smooth_plan(
        [
            (0, 0.08),
            (30, 0.15),
            (60, 0.6),
            (75, 0.5),
            (135, 2.5),
            (150, 0.4),
            (165, 0.2),
            (180, 0.05),
        ],
        TOTAL_FRAMES,
    )
    drv_plan = smooth_plan(
        [(0, 0.35), (60, 0.4), (75, 0.85), (135, 0.85), (150, 0.45), (165, 0.3), (180, 0.2)],
        TOTAL_FRAMES,
    )
    drone = to_stereo(render_drone(freq_plan, cut_plan, lfo_plan, drv_plan))
    drone_gain = smooth_plan(
        [
            (0, 0.8),
            (30, 0.9),
            (60, 0.85),
            (75, 1.0),
            (135, 1.0),
            (150, 0.8),
            (165, 0.7),
            (180, 0.0),
        ],
        TOTAL_FRAMES,
    )
    log.append(
        f"Track 1 MAINFRAME: detuned saws + LFO LP + cubicnl, peak {np.max(np.abs(drone)):.4f}"
    )

    # ---- Track 2 automation: arp only in B, C, B' (silent in A/A'/Outro) ----
    sixteenth = BEAT_SECONDS / 4.0
    arp_notes: list[tuple[float, float]] = []
    step = 0
    cursor = 30.0
    while cursor < 165.0:
        if cursor < 60.0 or 75.0 <= cursor < 165.0:
            degree = (step * ARP_ROTATION) % len(ARP_FIGURE)
            arp_notes.append((cursor, ARP_FIGURE[degree]))
            step += 1
        cursor += sixteenth
    arp = to_stereo(render_arp(arp_notes))
    arp_gain = smooth_plan(
        [
            (0, 0.0),
            (28, 0.0),
            (32, 0.7),
            (58, 0.7),
            (60, 0.0),
            (62, 0.0),
            (73, 0.0),
            (77, 1.0),
            (133, 1.0),
            (137, 0.8),
            (163, 0.8),
            (167, 0.0),
            (180, 0.0),
        ],
        TOTAL_FRAMES,
    )
    log.append(
        f"Track 2 ARP: {len(arp_notes)} 1/16 plucks D3 Eb3 G3 A3 poly-5, peak {np.max(np.abs(arp)):.4f}"
    )

    # ---- Track 3 automation: quarter-note kick in B (light) + C (heavy), fade in B' ----
    kick_hits: list[float] = []
    kick_vel: list[float] = []
    b = 30.0
    while b < 60.0:
        kick_hits.append(b)
        kick_vel.append(0.5)
        b += BEAT_SECONDS
    c = 75.0
    while c < 135.0:
        kick_hits.append(c)
        kick_vel.append(1.0)
        c += BEAT_SECONDS
    m = 135.0
    while m < 150.0:
        kick_hits.append(m)
        kick_vel.append(max(0.15, 1.0 - (m - 135.0) / 15.0))
        m += BEAT_SECONDS
    kick = to_stereo(render_kick(kick_hits, kick_vel))
    kick_gain = smooth_plan([(0, 0.9), (75, 0.9), (135, 1.0), (165, 0.9), (180, 0.9)], TOTAL_FRAMES)
    log.append(
        f"Track 3 PULSE: {len(kick_hits)} quarter-note triggers, peak {np.max(np.abs(kick)):.4f}"
    )

    # ---- Track 4 automation: glitch ONLY in C ----
    rate_plan = smooth_plan(
        [(0, 2.0), (73, 2.0), (77, 14.0), (105, 22.0), (131, 10.0), (137, 2.0), (180, 2.0)],
        TOTAL_FRAMES,
    )
    glitch = to_stereo(render_glitch(rate_plan))
    glitch_gain = smooth_plan(
        [(0, 0.0), (73, 0.0), (78, 0.9), (130, 0.9), (136, 0.0), (180, 0.0)],
        TOTAL_FRAMES,
        smooth_s=1.0,
    )
    log.append(
        f"Track 4 KERNEL PANIC: S&H noise + bitcrush, C-only, peak {np.max(np.abs(glitch)):.4f}"
    )

    # ---- Mix: phase gains, pump, outro sweep, normalize ----
    n = TOTAL_FRAMES
    drone *= drone_gain * 10.0 ** (-10.0 / 20.0)
    arp *= arp_gain * 10.0 ** (-16.0 / 20.0)
    kick *= kick_gain * 10.0 ** (-7.0 / 20.0)
    glitch *= glitch_gain * 10.0 ** (-18.0 / 20.0)
    duck = np.ones(n)
    duck_n = int(0.22 * SAMPLE_RATE)
    curve = 1.0 - 0.6 * np.exp(-np.arange(duck_n) / (0.07 * SAMPLE_RATE))
    for start_s in kick_hits:
        pos = int(start_s * SAMPLE_RATE)
        end = min(pos + duck_n, n)
        duck[pos:end] = np.minimum(duck[pos:end], curve[: end - pos])
    bed = (drone + arp + glitch) * duck
    mix = bed + kick
    outro_start = int(165.0 * SAMPLE_RATE)
    outro_curve = 0.5 + 0.5 * np.cos(np.pi * np.arange(n - outro_start) / (n - outro_start))
    mix[:, outro_start:] *= outro_curve
    peak = float(np.max(np.abs(mix)))
    mix = mix / max(peak, 1e-9) * 10.0 ** (-1.0 / 20.0)
    stereo = np.asarray(mix.T, dtype=np.float32)
    out_peak = float(np.max(np.abs(stereo)))
    out_rms = float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2)))
    c_rms = section_rms(mix, 90.0, 120.0)
    a_rms = section_rms(mix, 5.0, 25.0)
    out_rms_tail = float(
        np.sqrt(np.mean(stereo[-int(2.0 * SAMPLE_RATE) :].astype(np.float64) ** 2))
    )
    log.append(
        f"MIX: pump + outro sweep + normalize -> peak {out_peak:.4f} rms {out_rms:.4f} "
        f"C(90-120s) {c_rms:.4f} vs A(5-25s) {a_rms:.4f} tail2s {out_rms_tail:.5f}"
    )
    if out_peak <= 0.0:
        raise RuntimeError("Rendered silence; the breach must sound")
    if not 10.0 ** (-3.0 / 20.0) < out_peak < 10.0 ** (-0.5 / 20.0):
        raise RuntimeError(f"Peak {out_peak:.4f} outside normalized band (-3,-0.5) dBFS")
    if c_rms <= a_rms:
        raise RuntimeError(
            f"Form check failed: climax C ({c_rms:.4f}) not louder than intro A ({a_rms:.4f})"
        )
    if out_rms_tail >= 0.05:
        raise RuntimeError(f"Outro failed to sweep down: last-2s RMS {out_rms_tail:.5f}")

    out_path = Path(__file__).resolve().parent / OUTPUT_NAME
    wavfile.write(str(out_path), SAMPLE_RATE, stereo)
    for line in log:
        print(line)
    print(
        f"Rendered {stereo.shape[0]} frames ({stereo.shape[0] / SAMPLE_RATE:.1f}s) shape={stereo.shape} -> {out_path}"
    )
    return out_path


if __name__ == "__main__":
    main()
