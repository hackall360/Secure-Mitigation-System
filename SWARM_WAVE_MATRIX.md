# SWARM WAVE MATRIX — Closed-Loop Rubric Maximization (S_current 7.06 → S_target 9.50+)

> Guidance Axiom: Δ = S_target − S_current drives corrective waves until Δ = 0.
> Directive bans: NEVER execute final .mp4 render. Monotonic gate: Δscore ≥ 0 per sub-criterion.
> Branch: `feature/rubric-max-wave1` (Wave 1). Baseline: gate 1063 passed + 2 skipped (one load flake observed).

| Wave ID | Target Subsystem | Where It Is (S_current) | Where It Isn't (Δ) | Assigned Agent | Gate Status |
|---|---|---|---|---|---|
| 1.1 | `tests/test_project_entrypoints.py:118` flake | 2 s wall-clock `cleaned.wait(2)` races portal-thread cancel under load → intermittent `CancelledError` | Deterministic event-bound wait (generous bound, no sleeps); 50× isolated + full gate green | slice/flake-fix | OPEN |
| 1.2 | Narration (beat file + replay captions) | Beats exist only as prose in DEMO_PACK; no machine-readable beat file; TTS unwired | `beats` data + timed captions in replay path; TTS-ready stems hook (no audio render) | slice/beat-script | OPEN |
| 1.3 | Open-weight proof (`config.py`, `pricing.py`) | ID regex + env comments only; `pricing.py` lacks spark-open entry (runtime cost crash); no verification doc | spark-open priced + validated + mocked-transport smoke test + `docs/OPEN_WEIGHT.md` | slice/open-weight | OPEN |
| 1.4 | `docs/DEMO_SCRIPT.md` 180 s beats | README 3-min guide prose only; no timed beat doc | Dedicated beat doc, cumulative ≤ 180.0 s, test-enforced | slice/beat-script | OPEN |
| 2.1 | Real intake clone | F-01/F-02 honest refusals | `git clone`/local ingest into isolated workspaces (Wave 2 branch) | — | DEFERRED |
| 2.2 | AI demo driver | No playback driver | `scripts/demo_driver.py` beat-file auto-advance (Wave 2) | — | DEFERRED |
| 2.3 | `render_demo.sh` | No script | Deterministic provision script, `bash -n` + static proof, NEVER executed (Wave 2) | — | DEFERRED |
| 3.x | Assets + load table + README | No hackathon section; no load table; `/ws/system` stub | README section (coordinator direct), load table, system-scope decision (Wave 3) | coordinator | OPEN (README) |

## Wave 1 slice isolation (non-overlapping file scopes)

- slice/flake-fix: `tests/test_project_entrypoints.py` ONLY.
- slice/beat-script: `docs/DEMO_SCRIPT.md` (new) + `web/js/stream/scenario.js` (BEATS data only) + `tests/test_demo_beats_red.py` (new) ONLY.
- slice/open-weight: `library/core/pricing.py` + `tests/test_config_agents.py` (append) + `docs/OPEN_WEIGHT.md` (new) ONLY. (`config.py` read-only — validation already accepts; do NOT touch.)
- coordinator: `README.md` hackathon section + `tests/test_docs_presentation.py` (append RED assertion) ONLY.

## Regression log

- Wave 1 start: baseline 1063 + 2 skipped (flake seen once under full-suite load, passes isolated/clean-tree).
