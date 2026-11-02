# SWARM WAVE MATRIX — Closed-Loop Rubric Maximization (S_current 7.06 → S_target 9.50+)

> Guidance Axiom: Δ = S_target − S_current drives corrective waves until Δ = 0.
> Directive bans: NEVER execute final .mp4 render. Monotonic gate: Δscore ≥ 0 per sub-criterion.
> Branch: `feature/rubric-max-wave1` (Wave 1). Baseline: gate 1063 passed + 2 skipped (one load flake observed).

| Wave ID | Target Subsystem | Where It Is (S_current) | Where It Isn't (Δ) | Assigned Agent | Gate Status |
|---|---|---|---|---|---|
| 1.1 | `tests/test_project_entrypoints.py:118` flake | 2 s wall-clock `cleaned.wait(2)` races portal-thread cancel under load → intermittent `CancelledError` | `except BaseException` + `finally` double-set; 30 s event wait + busy deadline-poll; 50× isolated + gate 1083 green | slice/flake-fix | DONE |
| 1.2 | Narration (beat file + replay captions) | Beats exist only as prose in DEMO_PACK; no machine-readable beat file; TTS unwired | `scripts/demo_driver.py` (`--dry-run/--live/--check-beats`); `--check-beats` 1:1 vs BEATS; 5/5 green | slice/driver | DONE |
| 1.3 | Open-weight proof (`config.py`, `pricing.py`) | ID regex + env comments only; `pricing.py` lacks spark-open entry (runtime cost crash); no verification doc | 2 provisional entries + 3 smoke tests + `docs/OPEN_WEIGHT.md`; `test_pricing` pin updated | slice/open-weight | DONE |
| 1.4 | `docs/DEMO_SCRIPT.md` 180 s beats | README 3-min guide prose only; no timed beat doc | 7 beats cumulative 180.0 s, BEATS mirror, 4/4 green | slice/beat-script | DONE |
| 2.1 | Real intake clone | F-01/F-02 honest refusals | `_ingest_repo_to_project` (CLI+TUI): staging clone → 0700 stage → detect → project path; F-pins retired stronger; 6/6 green | coordinator | DONE |
| 2.2 | AI demo driver | No playback driver | `scripts/demo_driver.py` shipped (substrate for auto-advance); full click-driving deferred | slice/driver | DONE-substrate |
| 2.3 | `render_demo.sh` | No script | 6-phase provision/capture/mux + `--check`; `bash -n` + 5/5 green; never executed | slice/render | DONE |
| 3.x | Assets + load table + README | No hackathon section; no load table; `/ws/system` stub | README section DONE; `docs/LOAD_TABLE.md` + system-stays-stub decision + pin test DONE | coordinator | DONE |

## Wave 1 slice isolation (non-overlapping file scopes)

- slice/flake-fix: `tests/test_project_entrypoints.py` ONLY.
- slice/beat-script: `docs/DEMO_SCRIPT.md` (new) + `web/js/stream/scenario.js` (BEATS data only) + `tests/test_demo_beats_red.py` (new) ONLY.
- slice/open-weight: `library/core/pricing.py` + `tests/test_config_agents.py` (append) + `docs/OPEN_WEIGHT.md` (new) ONLY. (`config.py` read-only — validation already accepts; do NOT touch.)
- coordinator: `README.md` hackathon section + `tests/test_docs_presentation.py` (append RED assertion) ONLY.

## Regression log

- Wave 1 start: baseline 1063 + 2 skipped (flake seen once under full-suite load, passes isolated/clean-tree).

- Wave 1+2 close-out: gate 1083 passed + 2 skipped, All checks passed (flake absent this run). Wave-2 commits: ceb5dad (driver), c350b19 (render), 8d8f0b3 (intake).
