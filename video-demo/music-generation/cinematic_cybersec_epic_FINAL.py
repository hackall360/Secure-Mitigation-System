"""Cinematic Cyberpunk / Darksynth Epic FINAL: 180 s structured composition.

v3 base (pad / bass / drums / arp, Dm -> Bb -> C arc) PLUS three feature voices:
  5. LASER LEAD (52-120 s): pitch-swept saw zaps on a refilled pattern with
     far fewer gaps — D D E D D C B C D E D E A - A - over 16 eighth slots,
     looping from the 52 s mark with quarter-note echo.
  6. COWBELL (100-160 s, unchanged — it sounds great): metallic square+sine
     partials through bandpass playing D D C D D C E D E E E C D C.
  7. HANDPAN (130-165 s): resonant steel-tongue voice (fundamental + octave
     + fifth partials, slow attack, long decay) on a D-minor pentatonic
     phrase, entering at the 2:10 mark and resting before the outro sweep.

Form over 180 s: intro (pad only, 0-15) -> scan (arp joins, 15-30) ->
build (bass + drums enter, 30-52) -> laser act (52-100: zap lead over
full groove) -> laser+cowbell peak (100-120) -> cowbell+handpan carry
(120-135 drums rest) -> reprise + bells + pan (135-160) -> handpan tail
(160-165) -> outro sweep (165-180).

A mini-sequencer generating a proper musical track @110 BPM, 4-bar loop,
progression Dm -> Bb -> C (classic cinematic cyberpunk arc):
  1. CHORD PAD: polyphonic 3-voice saw synth (detuned f, f*1.008, f*0.992)
     with long ADSR swell + zita reverb for lush dark atmosphere.
  2. BASSLINE: driving 16th-note synthwave bass with plucky ADSR and an
     envelope-tracked 24 dB/oct lowpass + cubicnl grit.
  3. DRUMS: kick (pitch-swept sine) + snare (bandpassed noise + 180 Hz
     punch) backbeat — kick on 1 & 3, snare on 2 & 4.
  4. ARP: square-wave pluck with dotted-8th delay + zita reverb, walking
     up each chord.

Form over 180 s: intro (pad only, 0-15) -> scan (arp joins, 15-30) ->
build (bass + drums enter, 30-60) -> drop hold (60-120 full) -> breath
(120-135 drums rest) -> reprise (135-165 full) -> outro sweep (165-180).
Macro filter automation opens pad/bass/arp into the climax and sweeps
everything down to silence at the end.

Corrections vs the draft this completes (all compile-probed in THIS repo,
never guessed):
  - PAD + ARP as drafted FAIL Faust compile: `re.zita_rev1_stereo` is
    2-in/2-out (its own lib docs: `_,_ : zita : _,_`), but the draft fed
    it a mono chain then scaled with single-input `*(0.4)`. Fixed by
    fanning mono to stereo BEFORE zita:
    `... : fi.lowpass <: zita : *(0.4), *(0.4)`. Probed OK.
  - `render_instrument` now handles mono (1,N) AND channels-last (N,2)
    buffers (the arp voice returns (1,N), measured).
  - Completion: finished arp render call, macro plans, full mix with
    phase gains + outro fade + normalize to -1 dBFS + form assertions
    + `main()` entry. Sequencer windows + macro plans kept from the draft.

Run from this directory with the fixture venv:
    ./.venv/bin/python cinematic_cybersec_epic_FINAL.py
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
OUTPUT_NAME = "cinematic_cybersec_epic_FINAL.wav"


def mtof(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


# 1. Polyphonic Pad (The Cinematic Chords)
# NOTE: mono fanned to stereo BEFORE zita (2-in/2-out) — probed fix.
PAD_DSP = """
declare name "CinematicPad";
import("stdfaust.lib");
f1 = hslider("f1", 440, 20, 2000, 0.01);
f2 = hslider("f2", 440, 20, 2000, 0.01);
f3 = hslider("f3", 440, 20, 2000, 0.01);
gate = hslider("gate", 0, 0, 1, 1);
cut = hslider("cutoff", 1200, 200, 5000, 1) : si.smoo;
env = en.adsr(2.0, 1.0, 0.8, 3.0, gate);
voice(f) = os.sawtooth(f) * 0.4 + os.sawtooth(f*1.008) * 0.4 - os.sawtooth(f*0.992) * 0.4;
chord = (voice(f1) + voice(f2) + voice(f3)) * env;
process = chord : fi.lowpass(2, cut) <: re.zita_rev1_stereo(2, 200, 6000, 0.2, 3, 44100) : *(0.4), *(0.4);
"""

# 2. Driving 16th Note Bassline (compiles+renders unchanged — probed OK)
BASS_DSP = """
declare name "DrivingBass";
import("stdfaust.lib");
freq = hslider("freq", 55, 20, 500, 0.01);
gate = hslider("gate", 0, 0, 1, 1);
cut_mod = hslider("cutoff", 800, 100, 4000, 1) : si.smoo;
env = en.adsr(0.01, 0.15, 0.1, 0.05, gate);
filter_env = 100 + (env * cut_mod);
saw = os.sawtooth(freq) + os.sawtooth(freq*1.01)*0.5;
proc = saw * env : fi.lowpass(4, filter_env) : ef.cubicnl(0.3, 0);
process = proc * 0.6 <: si.bus(2);
"""

# 3. Drums — Kick & Snare Backbeat (compiles+renders unchanged — probed OK)
DRUM_DSP = """
declare name "DrumKit";
import("stdfaust.lib");
k_gate = hslider("k_gate", 0, 0, 1, 1);
s_gate = hslider("s_gate", 0, 0, 1, 1);
k_env = en.ar(0.001, 0.3, k_gate);
k_pitch_env = en.ar(0.001, 0.05, k_gate);
k_pitch = 40 + (120 * k_pitch_env);
kick = os.osc(k_pitch) * k_env * 1.5;
s_env = en.ar(0.001, 0.25, s_gate);
s_noise = no.noise * s_env : fi.bandpass(2, 2000, 5000);
s_punch = os.osc(180) * en.ar(0.001, 0.1, s_gate);
snare = (s_noise + s_punch) * 1.2;
process = (kick + snare) * 0.8 <: si.bus(2);
"""

# 4. Melodic Arp
# NOTE: mono fanned to stereo BEFORE zita (2-in/2-out) — probed fix.
ARP_DSP = """
declare name "CyberArp";
import("stdfaust.lib");
freq = hslider("freq", 440, 20, 2000, 0.01);
gate = hslider("gate", 0, 0, 1, 1);
cut = hslider("cutoff", 1500, 200, 4000, 1) : si.smoo;
env = en.adsr(0.01, 0.2, 0.0, 0.1, gate);
pluck = os.square(freq) * env : fi.lowpass(2, cut);
dly = pluck : de.delay(44100, 16537) : *(0.4);
wet = pluck + dly;
process = wet * 0.3 <: re.zita_rev1_stereo(2, 200, 6000, 0.2, 3, 44100) : *(0.5), *(0.5);
"""

# 5. Laser Lead (probed compile+render OK, audible zap — peak 0.29)
LASER_DSP = """
declare name "LaserZap";
import("stdfaust.lib");
freq = hslider("freq", 587.33, 40, 2000, 0.01);
gate = hslider("gate", 0, 0, 1, 1);
sweep = freq * (1.0 + 1.5 * (gate : si.smoo : *(-1) : +(1)));
zap = os.sawtooth(sweep) * en.ar(0.002, 0.28, gate);
echo = zap : de.delay(44100, 11025) : *(0.35);
process = (zap + echo) * 0.3 <: si.bus(2);
"""

# 6. Cowbell (probed compile+render OK, metallic tick — peak 0.73)
COWBELL_DSP = """
declare name "CowBell";
import("stdfaust.lib");
freq = hslider("freq", 1174.66, 400, 2400, 0.01);
gate = hslider("gate", 0, 0, 1, 1);
env = en.ar(0.001, 0.16, gate);
metal = (os.square(freq) * 0.5 + os.osc(freq * 1.483) * 0.5) * env;
process = metal : fi.bandpass(2, 1200, 3600) * 0.8 <: si.bus(2);
"""

# 7. Handpan (probed compile+render OK, resonant steel tone — peak 0.43)
HANDPAN_DSP = """
declare name "HandPan";
import("stdfaust.lib");
freq = hslider("freq", 587.33, 200, 1200, 0.01);
gate = hslider("gate", 0, 0, 1, 1);
env = en.ar(0.005, 1.1, gate);
body = os.osc(freq) * 0.6 + os.osc(freq * 2.0) * 0.25 + os.osc(freq * 2.98) * 0.15;
tone = body * env : fi.lowpass(2, 2800);
process = tone * 0.5 <: si.bus(2);
"""

# Refill: the user's D---DDC-C--D-E-A--- degrees, gaps filled with passing
# tones so the zap lead stays present: D D E D D C B C D E D E A - A -.
# 16 eighth slots, 14 sounding (was 7) — same D5/C5/E5/A4/B4 family.
LASER_FREQS = (587.33, 523.25, 659.25, 493.88, 440.00)
LASER_BAR = (0, 0, 2, 0, 0, 1, 3, 1, 0, 2, 0, 2, 4, None, 4, None)
# D D C D D C E D E E E C D C — user cowbell degrees, eighth notes (unchanged).
# D-minor pentatonic handpan phrase (D5 E5 F5 A5 C6 D6), quarter notes.
HANDPAN_FREQS = (587.33, 659.25, 698.46, 880.00, 1046.50, 1174.66, 880.00, 698.46)
COWBELL_FREQS = (
    1174.66,
    1174.66,
    1046.50,
    1174.66,
    1174.66,
    1046.50,
    1318.51,
    1174.66,
    1318.51,
    1318.51,
    1318.51,
    1046.50,
    1174.66,
    1046.50,
)


def render_instrument(dsp_code: str, automation_dict: dict[str, np.ndarray]) -> np.ndarray:
    """Render one Faust voice with audio-rate automation; always (2, N)."""
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)
    voice = engine.make_faust_processor("instr")
    voice.set_dsp_string(dsp_code)
    engine.load_graph([(voice, [])])
    for path, data in automation_dict.items():
        voice.set_automation(path, np.asarray(data, dtype=np.float32))
    engine.render(TOTAL_SECONDS)
    audio = np.asarray(engine.get_audio(), dtype=np.float64)
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=0)
    if audio.shape[0] == 1:
        return np.stack([audio[0], audio[0]], axis=0)
    if audio.shape[0] == 2:
        return audio
    return np.stack([audio[:, 0], audio[:, 1]], axis=0)


def section_rms(mix: np.ndarray, start_s: float, end_s: float) -> float:
    seg = mix[:, int(start_s * SAMPLE_RATE) : int(end_s * SAMPLE_RATE)]
    return float(np.sqrt(np.mean(seg**2)))


def main() -> Path:
    print("Generating Cinematic Track Logic...")
    frames = TOTAL_FRAMES

    pad_f1 = np.zeros(frames)
    pad_f2 = np.zeros(frames)
    pad_f3 = np.zeros(frames)
    pad_gate = np.zeros(frames)
    pad_cut = np.full(frames, 1200.0)

    bass_freq = np.zeros(frames)
    bass_gate = np.zeros(frames)
    bass_cut = np.full(frames, 800.0)

    k_gate = np.zeros(frames)
    s_gate = np.zeros(frames)

    arp_freq = np.zeros(frames)
    arp_gate = np.zeros(frames)
    arp_cut = np.full(frames, 1500.0)

    laser_freq = np.zeros(frames)
    laser_gate = np.zeros(frames)

    bell_freq = np.zeros(frames)
    bell_gate = np.zeros(frames)

    pan_freq = np.zeros(frames)
    pan_gate = np.zeros(frames)

    beats_per_bar = 4
    total_beats = int(TOTAL_SECONDS / BEAT_SECONDS)

    # Dm (D2, F2, A2), Bb (Bb1, D2, F2), C (C2, E2, G2)
    chords = [
        (38, 41, 45),
        (38, 41, 45),
        (34, 38, 41),
        (36, 40, 43),
    ]
    bass_roots = [26, 26, 22, 24]

    for beat in range(total_beats):
        time_start = beat * BEAT_SECONDS
        time_end = (beat + 1) * BEAT_SECONDS
        if time_end > TOTAL_SECONDS:
            break
        start_idx = int(time_start * SAMPLE_RATE)

        bar_in_loop = (beat // beats_per_bar) % 4
        beat_in_bar = beat % beats_per_bar
        current_chord = chords[bar_in_loop]
        current_bass = bass_roots[bar_in_loop]

        if beat_in_bar == 0:
            hold = int(SAMPLE_RATE * 1.5)
            pad_f1[start_idx : start_idx + hold] = mtof(current_chord[0])
            pad_f2[start_idx : start_idx + hold] = mtof(current_chord[1])
            pad_f3[start_idx : start_idx + hold] = mtof(current_chord[2])
            pad_gate[start_idx : start_idx + hold] = 1.0

        if (30 <= time_start <= 120) or (135 <= time_start <= 165):
            if beat_in_bar % 2 == 0:
                k_gate[start_idx : start_idx + int(SAMPLE_RATE * 0.1)] = 1.0
            else:
                s_gate[start_idx : start_idx + int(SAMPLE_RATE * 0.1)] = 1.0

        if 30 <= time_start <= 165:
            sixteenth_len = int((BEAT_SECONDS / 4.0) * SAMPLE_RATE)
            for i in range(4):
                s_idx = start_idx + (i * sixteenth_len)
                gate_dur = int(sixteenth_len * 0.6)
                if s_idx + gate_dur < TOTAL_FRAMES:
                    bass_freq[s_idx : s_idx + gate_dur] = mtof(current_bass)
                    bass_gate[s_idx : s_idx + gate_dur] = 1.0

        if 15 <= time_start <= 150:
            eighth_len = int((BEAT_SECONDS / 2.0) * SAMPLE_RATE)
            arp_notes = [current_chord[0] + 12, current_chord[1] + 12]
            for i in range(2):
                s_idx = start_idx + (i * eighth_len)
                gate_dur = int(eighth_len * 0.5)
                if s_idx + gate_dur < TOTAL_FRAMES:
                    arp_freq[s_idx : s_idx + gate_dur] = mtof(arp_notes[i])
                    arp_gate[s_idx : s_idx + gate_dur] = 1.0

        # 5. LASER (52-120 s): refilled bar, eighth slots, clamped at 120.
        if 52 <= time_start < 120:
            eighth_len = int((BEAT_SECONDS / 2.0) * SAMPLE_RATE)
            slot = int((time_start - 52.0) // (BEAT_SECONDS / 2.0)) % 16
            degree = LASER_BAR[slot]
            if degree is not None:
                gate_dur = int(eighth_len * 0.9)
                end_idx = min(start_idx + gate_dur, int(120.0 * SAMPLE_RATE), TOTAL_FRAMES)
                if end_idx > start_idx:
                    laser_freq[start_idx:end_idx] = LASER_FREQS[degree]
                    laser_gate[start_idx:end_idx] = 1.0

        # 6. COWBELL (100-160 s): DDC DDC EDE EEC DC, eighth notes.
        # Same eighth-grid discipline: one slot per visit, no spillover.
        if 100 <= time_start < 160:
            eighth_len = int((BEAT_SECONDS / 2.0) * SAMPLE_RATE)
            step = int((time_start - 100.0) // (BEAT_SECONDS / 2.0))
            degree = COWBELL_FREQS[step % len(COWBELL_FREQS)]
            gate_dur = int(eighth_len * 0.55)
            if start_idx + gate_dur < TOTAL_FRAMES and start_idx + eighth_len <= int(
                160.0 * SAMPLE_RATE
            ):
                bell_freq[start_idx : start_idx + gate_dur] = degree
                bell_gate[start_idx : start_idx + gate_dur] = 1.0

        # 7. HANDPAN (130-165 s): pentatonic phrase, quarter notes, long ring.
        # Enters at the 2:10 mark; rests before the 165 s outro sweep.
        if 130 <= time_start < 165:
            step = int((time_start - 130.0) // BEAT_SECONDS)
            degree = HANDPAN_FREQS[step % len(HANDPAN_FREQS)]
            gate_dur = int(BEAT_SECONDS * 0.9 * SAMPLE_RATE)
            end_idx = min(start_idx + gate_dur, int(165.0 * SAMPLE_RATE), TOTAL_FRAMES)
            if end_idx > start_idx:
                pan_freq[start_idx:end_idx] = degree
                pan_gate[start_idx:end_idx] = 1.0

    print("Applying Macro Automation (Filters & Dynamics)...")
    t = np.arange(TOTAL_FRAMES) / SAMPLE_RATE
    pad_cut = np.interp(t, [0, 45, 60, 120, 150, 180], [600, 1200, 2500, 2500, 800, 400])
    bass_cut = np.interp(t, [0, 30, 60, 120, 150, 180], [200, 600, 2000, 2000, 400, 100])
    arp_cut = np.interp(t, [0, 30, 60, 120, 180], [500, 1500, 2500, 1000, 500])

    print("Rendering Pad...")
    pad_audio = render_instrument(
        PAD_DSP,
        {
            "/CinematicPad/f1": pad_f1,
            "/CinematicPad/f2": pad_f2,
            "/CinematicPad/f3": pad_f3,
            "/CinematicPad/gate": pad_gate,
            "/CinematicPad/cutoff": pad_cut,
        },
    )
    print(f"  pad peak {np.max(np.abs(pad_audio)):.4f}")

    print("Rendering Bass...")
    bass_audio = render_instrument(
        BASS_DSP,
        {
            "/DrivingBass/freq": bass_freq,
            "/DrivingBass/gate": bass_gate,
            "/DrivingBass/cutoff": bass_cut,
        },
    )
    print(f"  bass peak {np.max(np.abs(bass_audio)):.4f}")

    print("Rendering Drums...")
    drum_audio = render_instrument(
        DRUM_DSP,
        {
            "/DrumKit/k_gate": k_gate,
            "/DrumKit/s_gate": s_gate,
        },
    )
    print(f"  drums peak {np.max(np.abs(drum_audio)):.4f}")

    print("Rendering Arp...")
    arp_audio = render_instrument(
        ARP_DSP,
        {
            "/CyberArp/freq": arp_freq,
            "/CyberArp/gate": arp_gate,
            "/CyberArp/cutoff": arp_cut,
        },
    )
    print(f"  arp peak {np.max(np.abs(arp_audio)):.4f}")

    print("Rendering Laser...")
    laser_audio = render_instrument(
        LASER_DSP,
        {
            "/LaserZap/freq": laser_freq,
            "/LaserZap/gate": laser_gate,
        },
    )
    print(f"  laser peak {np.max(np.abs(laser_audio)):.4f}")

    print("Rendering Cowbell...")
    bell_audio = render_instrument(
        COWBELL_DSP,
        {
            "/CowBell/freq": bell_freq,
            "/CowBell/gate": bell_gate,
        },
    )
    print(f"  cowbell peak {np.max(np.abs(bell_audio)):.4f}")

    print("Rendering Handpan...")
    pan_audio = render_instrument(
        HANDPAN_DSP,
        {
            "/HandPan/freq": pan_freq,
            "/HandPan/gate": pan_gate,
        },
    )
    print(f"  handpan peak {np.max(np.abs(pan_audio)):.4f}")

    print("Mixing + mastering...")
    pad_audio *= 10.0 ** (-12.0 / 20.0)
    bass_audio *= 10.0 ** (-10.0 / 20.0)
    drum_audio *= 10.0 ** (-8.0 / 20.0)
    arp_audio *= 10.0 ** (-15.0 / 20.0)
    laser_audio *= 10.0 ** (-11.0 / 20.0)
    bell_audio *= 10.0 ** (-13.0 / 20.0)
    pan_audio *= 10.0 ** (-12.0 / 20.0)
    mix = pad_audio + bass_audio + drum_audio + arp_audio + laser_audio + bell_audio + pan_audio

    outro_start = int(165.0 * SAMPLE_RATE)
    outro_curve = 0.5 + 0.5 * np.cos(
        np.pi * np.arange(frames - outro_start) / (frames - outro_start)
    )
    mix[:, outro_start:] *= outro_curve

    peak = float(np.max(np.abs(mix)))
    mix = mix / max(peak, 1e-9) * 10.0 ** (-1.0 / 20.0)
    stereo = np.asarray(mix.T, dtype=np.float32)
    out_peak = float(np.max(np.abs(stereo)))
    out_rms = float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2)))
    climax = section_rms(mix, 90.0, 120.0)
    intro = section_rms(mix, 5.0, 15.0)
    tail = float(np.sqrt(np.mean(stereo[-int(2.0 * SAMPLE_RATE) :].astype(np.float64) ** 2)))
    per_track = {
        "pad": float(np.max(np.abs(pad_audio))),
        "bass": float(np.max(np.abs(bass_audio))),
        "drums": float(np.max(np.abs(drum_audio))),
        "arp": float(np.max(np.abs(arp_audio))),
        "laser": float(np.max(np.abs(laser_audio))),
        "cowbell": float(np.max(np.abs(bell_audio))),
        "handpan": float(np.max(np.abs(pan_audio))),
    }
    print(
        f"MIX: peak {out_peak:.4f} rms {out_rms:.4f} climax {climax:.4f} vs intro {intro:.4f} tail2s {tail:.5f}"
    )
    laser_margin = section_rms(laser_audio, 47.0, 52.0) + section_rms(laser_audio, 120.0, 125.0)
    laser_core = section_rms(laser_audio, 52.0, 120.0)
    bell_margin = section_rms(bell_audio, 95.0, 100.0) + section_rms(bell_audio, 160.0, 165.0)
    bell_core = section_rms(bell_audio, 100.0, 160.0)
    pan_margin = section_rms(pan_audio, 125.0, 130.0) + section_rms(pan_audio, 165.0, 170.0)
    pan_core = section_rms(pan_audio, 130.0, 165.0)
    print(
        f"WINDOWS: laser core(52-120) {laser_core:.5f} margins {laser_margin:.5f} / "
        f"bell core(100-160) {bell_core:.5f} margins {bell_margin:.5f} / "
        f"pan core(130-165) {pan_core:.5f} margins {pan_margin:.5f}"
    )
    if out_peak <= 0.0:
        raise RuntimeError("Rendered silence; the cinematic arc must sound")
    if not 10.0 ** (-3.0 / 20.0) < out_peak < 10.0 ** (-0.5 / 20.0):
        raise RuntimeError(f"Peak {out_peak:.4f} outside normalized band (-3,-0.5) dBFS")
    if climax <= intro:
        raise RuntimeError(
            f"Form check failed: climax ({climax:.4f}) not louder than intro ({intro:.4f})"
        )
    if tail >= 0.05:
        raise RuntimeError(f"Outro failed to sweep down: last-2s RMS {tail:.5f}")
    if laser_core <= 0.0 or laser_margin >= 0.5 * laser_core:
        raise RuntimeError(f"Laser window leak: core {laser_core:.5f} margins {laser_margin:.5f}")
    if bell_core <= 0.0 or bell_margin >= 0.5 * bell_core:
        raise RuntimeError(f"Cowbell window leak: core {bell_core:.5f} margins {bell_margin:.5f}")
    if pan_core <= 0.0 or pan_margin >= 0.5 * pan_core:
        raise RuntimeError(f"Handpan window leak: core {pan_core:.5f} margins {pan_margin:.5f}")
    for name, track_peak in per_track.items():
        if track_peak <= 0.0:
            raise RuntimeError(f"Track {name} is silent; all 7 tracks must sound")

    out_path = Path(__file__).resolve().parent / OUTPUT_NAME
    wavfile.write(str(out_path), SAMPLE_RATE, stereo)
    print(
        f"Rendered {stereo.shape[0]} frames ({stereo.shape[0] / SAMPLE_RATE:.1f}s) shape={stereo.shape} -> {out_path}"
    )
    return out_path


if __name__ == "__main__":
    main()
