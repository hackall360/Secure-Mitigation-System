# Demo video plan — 3:00 total, ~2:00 spoken (TTS Spark voice + music bed)

Scope note: this is the shooting script + VO lines + click path. No video is
created here. VO lines are draft — tighten in the booth, keep the hook first.
Spoken budget ~2:00 of 3:00; the rest is screen action + music.

## Production pipeline: Option B (decided 2026-11-03)

Silent capture with cue notes → dry-run findings → write VO to picture →
booth TTS clips → edit. Rejected Option A (record everything with live
audio, cut down in post).

Why B wins for this video:
- Part 2 is unscriptable: findings VO can only be written from the actual
  verdict. Live narration risks wrong claims about results not yet seen.
- Driving + watching + narrating splits attention at exactly the moments
  worth talking about (verdict landing, the flip, receipt chain). Booth VO
  lands on the frame every time.
- The programmatic TTS pipeline wants final text in, clean clips out. A
  bakes room tone/hesitation/mistiming into the capture; B feeds the
  pipeline what it was built for.
- The music bed mixes against locked VO stems, not shifting live audio.

Division of labor: agent drives the browser + runs the scans + records cue
notes/timings/findings (the labor that makes B work). Human edits (extra
edit load accepted): silent captures + TTS clips + music bed → final cut.

Capture discipline (agent side, during every silent pass): wall-clock cue
marks for each beat moment (verdict landed at mm:ss, receipt visible,
good reaction shot) so the editor never hunts. The click paths below are
the shot list; the cue log is the edit map.

## Dry-run protocol (decided 2026-11-03)

A dry run is the full recording choreography minus recording: the agent
drives everything end to end in the browser (human watches live), with
dry-run sizing (1 red / 1 blue — NOT the recording's 5 red / 3 blue).
After each part's run completes, the agent documents what was actually
visible in the web UI (cue marks, verdict, timings), writes the VO lines
to match that observed reality (adjusting the draft script as needed),
renders them as scratch TTS WAVs (`test_demo_*.wav`), and reports their
paths. The human listens + judges against what they saw; if both pass,
the recording run (5 red / 3 blue) and edit follow.

Dry-run WAV naming: `video-demo/TTSServer/takes/test_demo_<part>_<beat>.wav`
(e.g. `test_demo_part1_hook.wav`, `test_demo_part2_findings.wav`). Scratch
only — never mistaken for final booth takes.

## Part 1 — Demo path (raw capture, slimmed to ~1:00 in post)

On screen: `index.html` hold ~3 s.

VO: "This is Secure Mitigation System. An agentic purple team — red attacks,
blue patches — running on Meta's Muse Spark and Wonder models. Watch what it
can do."

Click: Demo mode card → `demo-setup.html`.

VO: "This is the demo I prepared to show some of what is possible."

Click path (say while doing):
1. PHP target card ("PHP command boundary").
2. Scroll to Run settings. Source: click Live orchestrator.
3. Sweep depth: bump 1 → 2 ("two passes — a deep pass on top of the single finding").
4. Toggle "Ground with threat intel" on. Operational mode: Balanced.
5. "Let's give it a run, and see what it finds." Click Start live demo.

Live run (`demo.html` auto-starts). One or two short interjections while it
runs, e.g. "Red is mapping the surface now" / "Blue has a candidate patch —
watch the re-run." Do NOT narrate continuously; let the stream breathe under
the music.

After the verdict lands (expect verified: exit 0 → 1, chained receipt),
3–4 sentences, e.g.: "There it is. The probe reached the boundary on the
unpatched target, red traced it to the sink, blue answered with a minimal
sanitization patch, and the same probe failed on a fresh patched copy while
regression stayed green. Evidence, chained — not opinion."

Click: back/Start → `index.html`.

VO bridge: "Let's see what happens with an older project in production mode."

## Part 2 — Production path, AnyCam (raw capture, sped up heavily in post)

Target: https://github.com/hackall360/AnyCam — phone-camera-over-LAN to a
PipeWire virtual camera. `anycam.py` is stdlib-only Python (whole server in
one file); `pwcam.c` is the raw-libpipewire source; `static/` holds the
phone/viewer/camtest pages; HTTPS on the phone side (getUserMedia requires
it), plain HTTP on localhost.

On screen: `prod-setup.html`, mode = Repo ingest.

VO: none before the run. Fill these fields on camera:
- Repository URL: `https://github.com/hackall360/AnyCam.git`
- Pinned commit: leave empty (= HEAD as-is).
- Behavior contract (what it should focus on — paste/adapt):
  "AnyCam streams a phone camera over the LAN (HTTPS, self-signed cert,
  WebSocket publish) and serves viewers over localhost HTTP (MJPEG, snapshot,
  WebSocket view, camtest). Preserve the streaming behavior and PipeWire
  publishing. Focus verification on the untrusted input boundary: phone-side
  publish frames/params, viewer query params, snapshot/camtest endpoints, and
  any shell-out or file path derived from remote input."
- Ground with threat intel: on. Run local scanners: on.
- Model profile: Balanced. Sweep depth: 4. Cycles: 1. Red agents: 5. Blue agents: 3.

Click run. Comments only AFTER it lands (the capture is sped up; say so in
the VO, e.g. "Sped up — this ran for [X]. Here's what it found: [1–2
sentences on the actual findings].")

Small wrinkle: ingest mode's run-sizing fields come from server defaults on
this surface (the form sends ingest_repo/commit/contract; cycles/agents ride
the profile). If the UI will not let you set cycles/agents for ingest, say
so in the VO ("server defaults for sizing") and keep moving — do not fight
the form on camera.

## Outro (over index or tagline card)

VO: "I hope you enjoyed this demo of Secure Mitigation System. One last
thing — this video, and this voice, was orchestrated by me: Meta Muse
Spark, one point three. Thank you for watching."

## Known on-camera risks (my side to fix before recording)

1. Sweep-depth flicker (demo-setup): bumping 1↔2 rapidly oscillates. Prime
   suspect is the stepper's press-and-hold repeat racing an onChange refresh
   (each bump fires onChange → refresh, and the held button's pointerup may
   land on a re-rendered node, leaving the repeat timer stuck). Workaround
   if unfixed: single quick clicks, never hold; or type the value directly.
2. Ingest sizing fields (prod-setup ingest mode): cycles/agents may be
   server-driven on this surface — confirm before recording so the VO line
   ("1 cycle, 5 red, 3 blue") matches what the form actually sends.
3. AnyCam wall-clock is unknown — dry-run Part 2 once to learn the capture
   length and confirm the run completes before promising anything on mic.

## VO rendering lessons (decided 2026-11-03, booth seed 6420)

No single template renders every line. Each line needs its own shaping,
but the aspects below re-use across lines — mix per line, never copy a
whole recipe blindly.

Reusable aspects (the toolkit, not a template):
- Skip-refine (`skip_refine_text=True`): synthesis runs exactly as written.
  The refiner otherwise rewrites the line and scatters its own pauses.
  Default ON for all VO.
- `[uv_break]`: gentle filled pause, for mid-line breaths between clauses.
- `[lbreak]`: hard stop. Use sparingly — one before the closer, one
  trailing so the final phoneme renders instead of hard-cutting (plus
  0.5 s padded digital silence after, always).
- `break_6` (relaxed gaps) over `break_4` (clipped, robotic here).
- Letter-space acronyms/compound tech terms (O S, P H P, host name, escape
  shell arg) — the voice mumbles them joined, spells them spaced.
- Temp 0.3 + top_P 0.7 + top_K 20 pins (README lively triple, deterministic
  with seeded tensor `dd1e40d0f813e52b`).
- End lines on facts, not slogans. A closer that sounds AI-written
  ("Evidence, chained, not opinion") will read AI-spoken no matter the
  recipe — cut it rather than fix the delivery.

What did NOT transfer:
- `[lbreak]` at every boundary (hook v5) sounded upset/agitated. Hard
  stops multiply tension; one is punctuation, four is an argument.
- Temp 0.45/0.5 variants: liveliness knob, not a pause-placement fix.
- Word-break prefixing every sentence without skip-refine: the refiner
  reorganized the marks anyway.
- Long single-breath multi-clause sentences (explainer v1-v8): split the
  sentence instead of tuning the pause. No pause recipe fixes a breath
  that carries three ideas.
- Trailing digital silence alone does NOT save a clipped final phoneme —
  only a rendered trailing `[lbreak]` does.

Final Part 1 takes (all seed 6420, skip-refine, break_6, padded tails):
- `test_demo_part1_hook.wav` (v7 recipe: soft uv mid-line, one lbreak
  before closer, trailing lbreak).
- `test_demo_part1_explainer.wav` (v10: v7 recipe + split breaths +
  spaced acronyms, closer dropped).
- `test_demo_bridge.wav` (single thought, one lbreak, trailing lbreak).
