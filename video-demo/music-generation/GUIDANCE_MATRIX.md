# GUIDANCE MATRIX — music-generation closed-loop ledger (brief 2026-11-01-closed-loop-guidance)

Live Δ tracker for `video-demo/music-generation`. A subsystem exists in
$S_{current}$ **only** when its verification gate exits 0.
Status: `[ ]` UNVERIFIED | `[~]` IN_PROGRESS | `[x]` VERIFIED_ZERO_DELTA.

LAWs governing: 0, 1, 2, 3, 5, 10. Branch: `feature/music-generation-harness`.
Target interpreter: system `python3` (3.14.4; ships numpy 2.4.4 + scipy 1.17.1).
Repo `.venv` (3.12) has neither numpy nor scipy and is NOT the target.

| ID | Subsystem | $S_{current}$ (measured) | $\Delta$ deviation | Corrective vector | Gate | Status |
|----|-----------|--------------------------|--------------------|-------------------|------|--------|
| A | Environment and dependencies | dedicated `video-demo/music-generation/.venv` (py3.14.4): dawdreamer 0.9.0 + numpy 2.5.4 + scipy 1.18.1 importable, RenderEngine(44100,512) constructs. System python3 left untouched (PEP 668 externally managed, not overridden) | 0 — `import dawdreamer, numpy, scipy` exits 0 in fixture venv | fixture-local venv `video-demo/music-generation/.venv` (pip install dawdreamer numpy scipy) | import + RenderEngine construct gate | `[x]` |
| B | DawDreamer test harness (`test_generator.py`) | complete 69-line script: dawdreamer-first import, RenderEngine(44100,512), make_faust_processor sine DSP (os.osc 440 Hz, -6 dB), load_graph, render 3.0 s, get_audio transpose, scipy wav write | 0 — py_compile exit 0, live run exit 0, 132300 frames (3.00 s) stereo peak 0.5012 | none further | compile + live run | `[x]` |
| C | Artifact generation (`test_render.wav`) | `test_render.wav` 1058458 bytes, scipy readback rate 44100 shape (132300, 2) float32 — non-silent tone | 0 — exists, size > 0, frames = 3 s | none further | stat + wav readback | `[x]` |

## Δ-recompute log

- 2026-11-01 recon: `video-demo/` held only TTSServer + desktop-capture; `music-generation/` absent → created. System python3 3.14.4, numpy 2.4.4, scipy 1.17.1 importable; `.venv` 3.12 lacks both. `import dawdreamer` fails on system python3. PyPI shows dawdreamer 0.9.0; install docs support py3.11–3.14 Linux x86_64 via wheel.
- Faust DSP reference (upstream README basic example): `engine.make_faust_processor("faust")` + `set_dsp_string` with `os.osc` sine + `load_graph([(proc, [])])` + `render(seconds)` + `get_audio()` shaped (channels, samples) → `wavfile.write(path, rate, audio.T)`. LLVM caution: import dawdreamer before any LLVM lib.
- 2026-11-01 gates green: fixture `.venv` created (PEP 668 blocked system pip even with --user, so fixture-local venv is the target env). `pip install dawdreamer numpy scipy` → 0.9.0/2.5.4/1.18.1. Gate 1 py_compile exit 0. Gate 2 live run exit 0: 132300 frames, 3.00 s, peak 0.5012 (matches -6 dB sine). Gate 3: test_render.wav 1058458 bytes, readback 44100 Hz (132300, 2) float32. Δ=0 across A/B/C. Note: `.venv/` + `__pycache__/` + `*.wav` are repo-ignored so only GUIDANCE_MATRIX.md + test_generator.py are committable source.
- 2026-11-01 soft 10 s demo (follow-up): harness retest green (exit 0, 132300 frames, peak 0.5012 — no drift). New `soft_example.py`: A-major pad (A2/E3/A3/C#4, fi.lowpass 900 Hz, -20 dB) + numpy lullaby lead (A4 C#5 E5 C#5 B4, 2 s/notes, -32 dB) + 4 s numpy fade-in + master trim, 10.00 s, peak 0.0502 (~-26 dBFS) rms 0.0140, `soft_example.wav` 3528058 bytes. Faust traps fixed: `time` reserved → fades in numpy; `ef.lowpass` undefined → `fi.lowpass(order, cutoff)`.
- 2026-11-01 methodical example: `methodical_example.py` — 92 BPM, 16 beats = 10.4348 s score (Amaj7|F#m7|D9|E7), 20 isolated note renders (bass 4 + pad 8 + lead 8) with logged steps 1–6, peak 0.0787 rms 0.0241, `methodical_example.wav` 3681398 bytes. Engine trap measured: one engine sustains ~2 sequential Faust compiles then `undefined symbol: process`; fix = fresh RenderEngine per note. Filter trap: `fi.lowpass` needs a numeric cutoff baked into the DSP, not an hslider signal.
- 2026-11-01 techno bass synth: `techno_bass_synth_example.py` — 135 BPM, 68 beats = 30.2222 s, 6 tracks (kick 68 four-floor / Faust saw bass 136 off-beat 8ths / hats 136 / 48 Hz rumble 68 tails / 272 bit-crushed digital blips / 5 minor stabs) + sidechain pump + second-half lift, steps 1–8 logged. Peak 0.8913 (~-1 dBFS) rms 0.2708, `techno_bass_synth_example.wav` ~10.6 MB. Renders in ~5 s (151 Faust voices). Saw probe green pre-build.
- 2026-11-01 techno v2 sections: `techno_bass_synth_v2_example.py` — same 30.22 s engine with A B A C A B A D x2 + D-out form (8 x 4-beat sections). B drops bass/rumble, C drops kick/hats/digital/stabs (rumble+bass feature, cutoff 1600), D maximal outro (cutoff 3200, +2 dB lift). 103 bass saws with per-section cutoff morph 900->3200; 60 kicks / 120 hats / 240 blips / 5 stabs after C dropouts. Peak 0.8913 rms 0.2562, head100ms 0.00211 tail100ms 0.00403, first+last samples exactly 0. A/B/C section RMS contrast measured (0.1984/0.1534/0.2255).
