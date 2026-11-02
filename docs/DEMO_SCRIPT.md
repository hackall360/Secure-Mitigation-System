# Demo Script — 3-minute beat sheet (rubric P1-3, Wave 1.2/1.4)

Timed presenter sheet for the Secure Mitigation System loop. Companion to the
README 3-minute demo guide (prose) and `.jcode/session/docs/DEMO_PACK.md`
(scenarios with receipts: C14 chain, C34 replay). The replay rig
`web/js/stream/scenario.js` drives the interpreter with FAKE-RUN labels; the
`BEATS` array there mirrors these beats 1:1 (range, stage, stem, narration).

TTS: stems are TEXT-ONLY, booth seed 6420 @ t0.3. Never render audio from this
sheet: no TTS server calls, no audio file generation. The presenter reads the
stem lines live; the booth seed pins the reference voice if lines are voiced later.

Budget: 7 beats, contiguous, cumulative end 3:00 = 180.0 s (limit 180.0 s).
Narration total ~700 chars at ~800 chars/min = ~53 s of speech inside 180 s of
screen action. Each stem is one speakable line of at most 200 chars.

## Beat 1 - Hook (0:00-0:15, stage: probe, stem: demo-hook)
- On screen: live probe run against the unpatched fixture; terminal shows boundary check exit 0.
- Narration: "Watch this probe hit a live target in Docker and come back exit zero. The boundary is reachable, and we can prove it."

## Beat 2 - Red investigation (0:15-0:45, stage: analysis, stem: demo-red)
- On screen: Cartographer maps the surface, Bloodhound follows tainted input to the sink, probe ships.
- Narration: "Red maps the surface with Cartographer, then Bloodhound follows tainted input from the route into an unsanitized sink."

## Beat 3 - Blue patch (0:45-1:15, stage: patch, stem: demo-blue)
- On screen: Warden accepts, Stitch applies the sanitation-only diff, Proofreader lints it clean.
- Narration: "Blue answers with the smallest fix that holds: a parameterized query plus an allow list, nothing else touched."

## Beat 4 - Re-run flip (1:15-1:45, stage: regression, stem: demo-flip)
- On screen: same probe against a fresh patched target flips exit 0 to exit 1; Notary chains the VerdictReceipt.
- Narration: "Same probe, fresh target. Exit zero becomes exit one, regression still green, and the Notary chains the receipt."

## Beat 5 - Replay speedup (1:45-2:15, stage: sandbox, stem: demo-replay)
- On screen: vault prior replay (C34 HTTP-cookie combo-gate) or a Greenhouse ai-demo growing a fresh flawed target.
- Narration: "On a repeat visit the vault replays a prior fix, as in case C34, cutting a fresh investigation down to one retry cycle."

## Beat 6 - Observability (2:15-2:45, stage: cleanup, stem: demo-honest)
- On screen: Gauge token and cost badges, compression ratio, and an honest fail-closed exit 2 on an inconclusive run.
- Narration: "Tokens, cost, and compression stay visible. When proof is inconclusive the harness says exit two and fails closed."

## Beat 7 - Close (2:45-3:00, stage: cleanup, stem: demo-close)
- On screen: tagline card plus repo link; session containers, snapshots, and network removed.
- Narration: "Evidence, not opinion. Secure Mitigation System, open source at the repo link below. Try your own target next."

## Machine driver

`scripts/demo_driver.py` (stdlib only: `urllib`, `json`, `argparse`, `time`;
mirrors `scripts/mcp_client_demo.py` localhost + short-timeout patterns) is
the machine substrate that auto-advances these beats without clicks, for a
future agent presenter step. It parses the 7 `## Beat N` headers above with
the same regexes as `tests/test_demo_beats_red.py`, so driver and contract
test can never drift.

- `python scripts/demo_driver.py --dry-run` (default): prints the timed beat
  plan with cumulative `T+Xs` timestamps, validates total <= 180.0 s, exit 0.
- `python scripts/demo_driver.py --live --base http://127.0.0.1:PORT`:
  `/ws/demo` is a websocket, so the driver does NOT post beats to it.
  Instead it prints a `T+Xs: <stage> — <narration>` schedule the operator
  follows with sleep pacing (`--pace 0` disables sleeps), busy-polling
  `GET /api/health` between beats to prove the server is alive. Fail closed
  (non-zero exit) when the server is unreachable.
- `python scripts/demo_driver.py --check-beats`: asserts doc beats ==
  `web/js/stream/scenario.js` BEATS 1:1 (range/stage/stem/narration), exits
  non-zero on drift.

No-audio guarantee: the driver NEVER renders audio, NEVER contacts a TTS
server, and NEVER spawns a browser. Stems stay printable text.
