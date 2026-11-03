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
