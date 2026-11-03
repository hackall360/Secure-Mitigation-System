# SWARM WAVE MATRIX — Worktree Swarm Max (S_current 7.71 → S_target 9.50+)

> Guidance Axiom: Δ = S_target − S_current. Directive bans: NEVER execute final .mp4 render. Monotonic gate: Δscore ≥ 0.
> Branch: `feature/worktree-swarm-max`. Baseline: ledger Run #2 (7.71), gate 1303+2.
> Prior waves SHIPPED (verified 2026-11-03, not re-dispatched): 1.1 flake, 1.3 spark-open, 1.4 beats, 2.1 intake, 2.3 render, 3.2 load-table, 3.3 README.

| Wave ID | Target Subsystem | Where It Is (S_current) | Where It Isn't (Δ) | Assigned Agent | Worktree Path | Gate Status |
|---|---|---|---|---|---|---|
| W1 | narration toggle: `web/js/pages/demo.js` + `/ws/demo` + TTSServer stems | TTS STANDALONE (`client.py --render` works, booth seed 6420); presenter has captions but no TTS hook; beats are text-only data | presenter narration toggle calling pre-rendered stems per stage; 4B 1.50→2.00 | slice-narrate | /tmp/wt-narrate | OPEN |
| W2 | beat-file click-driving: `scripts/demo_driver.py` + `demo.js` | driver is substrate (`--dry-run/--check-beats`); no autonomous playback (no playwright/selenium anywhere) | Muse-authored beat file auto-advances presenter stages without clicks; 2C 2.00→2.50 | slice-driver | /tmp/wt-driver2 | OPEN |
| W3 | Bonus-3 creative assets (Image/Glimmer placeholders) | zero Image/Glimmer references in web/docs/README | gallery title-card + thumbnail assets + doc credit; Bonus-3 5.0→6.5 | slice-assets | /tmp/wt-assets | OPEN |

## Slice isolation (non-overlapping file scopes)

- slice-narrate: `web/js/pages/demo.js` (toggle only) + `web/demo.html` (button only) + `tests/test_demo_narration_red.py` (new) ONLY.
- slice-driver: `scripts/demo_driver.py` (append live mode) + `tests/test_demo_driver_red.py` (append) ONLY.
- slice-assets: `docs/ASSETS.md` (new) + `web/` title-card asset refs (new files only) + `tests/test_assets_red.py` (new) ONLY.
- Coordinator: matrix + ledger + ship (no product files).

## Regression log

- Baseline: gate 1303+2 (develop merge 086c2a7). Flake absent in last 3 gates.
