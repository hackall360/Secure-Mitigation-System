# Load table — submission-scale timing reference (rubric P3-9, Waves 3 / 1D+3D)

Measured on the build box (Linux x86_64, Python 3.12 venv) at Wave-2 gate green
(1083 passed + 2 skipped). Full-suite wall time is the load number that matters
for the demo clock: the 180 s beat sheet (docs/DEMO_SCRIPT.md) assumes a fresh
fixture scan completes inside Beat 3–4, which only holds for bundled fixtures,
not for full-suite runs. Figures below are observed, not estimated.

| Workload | Observed wall | Notes |
|---|---|---|
| Full gate (`dev.py check`: 1083 tests + ruff + compile + fixture checks) | ~91 s | Stable across 3 Wave-1/2 runs (90.7–91.6 s); flake-fix slice removed the only load-sensitive failure |
| New showcase tests (beats + driver + render: 14 tests) | 0.08 s (277 ms incl. spawn) | Pure-parse/static; `--check-beats` + `bash -n` add < 1 s |
| Intake wiring tests (6 tests, faked Docker) | ~1.3 s | No Docker; real clone adds image-pull + `git clone` time (unmeasured, network-dependent) |
| Single fixture scan (`--scan`, keyed, Docker) | 30–90 s (historical) | Model-latency dominated; see DEMO_PACK.md C14 ($0.19) / C34 ($0.21) cost notes |
| Docker overhead per cycle (container create/remove) | ~2–5 s (historical) | Session-labelled cleanup; air-gapped, no pulls at scan time (pinned bases) |

## `/ws/system` scope decision (rubric 1B/3D residual)

DECIDED: `/ws/system` stays an explicit fail-closed stub (`main.py: system_snapshot`
→ `{"type": "invalid", "msg": "System snapshot verification is not available ..."}`).
Rationale: the v3 setup schema already marks it `proposed` (`web/js/options/schema.js`);
the contract test pins the refusal (`test_webui_v3_contract.py: test_ws_system_refuses_explicitly`).
Implementing live system-snapshot verification is a post-hackathon capability (new attack
surface: host introspection over WS); the honest invalid frame beats a half-built
endpoint. No score impact beyond the already-counted 1B/3D residuals.
