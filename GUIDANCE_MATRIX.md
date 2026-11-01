# GUIDANCE MATRIX — closed-loop state-differential ledger (brief 2026-11-01-closed-loop-guidance)

Live Δ tracker. A subsystem exists in $S_{current}$ **only** when its gate exits 0.
Status: `[ ]` UNVERIFIED | `[~]` IN_PROGRESS | `[x]` VERIFIED_ZERO_DELTA.

LAWs governing this task: 0, 1, 2, 8, 9, 10, 11. Branch: `feature/webui-v3-migration`.
Baseline (LAW 10A): gate green pre-change 06:30 UTC — 876 passed + All checks.

| ID | Subsystem | $S_{current}$ (measured) | $\Delta$ deviation | Corrective vector | Gate | Status |
|---|---|---|---|---|---|---|
| A | WebUI v3 asset migration + serving | `web/` holds v3 tree verbatim (6 pages, js/css/tools, AGENTS+README); `sync_assets.py --check` → `assets in sync`; `GET /web/*.html` → 200 + assets:begin; `/` still v2; `static/` untouched | 0 | none further | contract A-group 4/4 + sync --check | `[x]` |
| B | Telemetry data contract + payload mapping | `socket_emit` + `build_compression_event` + `build_ingest_event` carry server `ts`; health/targets keys already v3-complete; redacted result aliases (pre/post_exit_code, receipt.patch_sha256) already read by result-view; no calc logic touched (rubric matrix preserved) | 0 | none further | contract B-group + full suite | `[x]` |
| C | WS pipeline + state hydration | `{type:snapshot}` first frame (nodes/hud/chips/ts) on every accept; busy path still precedes snapshot (lock check first — verified in code); `TelemetryBatcher` 100–250 ms for telemetry bursts only; run path inline (loop unblocked); 15 pre-existing WS tests updated to snapshot-first via `tests/helpers.drain_snapshot` (no assertions weakened) | 0 | none further | contract C-group + Gate 2 live Docker 4/4 | `[x]` |
| D | Gates + docs + commit | Gate 1 green (885 passed + 1 skipped, All checks — 06:50 UTC; 876 baseline + 9 new contract tests); Gate 2 `offline_scan` 4/4 verified + cleanup (06:45 UTC); Gate 3 Firefox + Chrome v3 proof (6/6 pages, HUD/chips, snapshot, interpreter stages/verified); docs updated (web/INDEX, TRAPS, matrix); proof tool `.jcode/tools/v3_ui_proof.py` | 0 — Δ=0 across all subsystems | commit on feature branch (no merge/push unasked) | dev.py + scans + browser | `[x]` |

## Δ-recompute log

- 06:30 UTC: baseline green (876 passed + All checks) — S_current pinned.
- 06:35 UTC: RED tests written; 7 fail on functional absence, 2 pass.
- 06:36–06:37 UTC: A implemented (web/ copy + /web mount + page routes); B implemented (ts aliases); C implemented (snapshot + batcher). First regression caught: `test_disconnect_cancels...` expected hello-first → updated to snapshot-first (test strengthened to contract, impl unchanged — LAW 9B clean).
- 06:38–06:41 UTC: Gate 1 red (16 failures, all hello-first assumptions in w22/project/profile tests) → halted forward work, built `drain_snapshot` helper, routed 15 sites, tolerated snapshot in collect-loop, verified busy-precedes-snapshot ordering. Regression → 0. Second red: vendored `web/tools/*.py` upstream style trips repo ruff → `exclude = web/tools/*` in pyproject (vendored pipeline, never hand-edited). Third: 3 files needed ruff format.
- 06:45 UTC: Gate 2 green — `offline_scan` 4/4 verified pre=0 post=1 + cleanup, with snapshot active (loop unblocked).
- 06:46–06:48 UTC: Gate 3 green — Firefox + Chrome v3 proof: 6/6 pages 200 + assets_sync, snapshot {hud ×5, nodes 5, chips server/docker/key}, console render {hud/chips all true, stages sandbox/probe/patch, findings 1, verdict verified}. Floor: v2 `ui_scan` Firefox exit 0 (Boundary check passed card read). Trap recorded: console.html redirects without launch → proof seeds launch like prod-setup, then reloads (real user flow); /usr/bin/firefox is a snap wrapper → omit --binary unless ELF (same rule as ui_scan).
- Trap refinement (TRAPS.md): physical `web/` is safe (no root `web.py`); only `tui/` shadows. GG2 no-physical-dirs verdict narrowed to same-named modules.
