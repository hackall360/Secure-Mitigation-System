# GUIDANCE MATRIX v2 — closed-loop state-differential ledger (brief 2026-11-02-closed-loop-guidance-v2)

Live Δ tracker. A subsystem exists in $S_{current}$ **only** when its verification gate exits 0.
Status: `[ ]` UNVERIFIED | `[~]` IN_PROGRESS | `[x]` VERIFIED_ZERO_DELTA.

LAWs governing this task: 0, 1, 2, 8, 9, 10, 11. Branch: `feature/closed-loop-guidance-v2`.
Baseline (LAW 10A): 1041 passed + 1 skipped on `develop@70150e2` (post v3-only cutover ZZ), tree clean, no worktrees.

Prior ledger `GUIDANCE_MATRIX.md` (2026-11-01) closed at Δ=0 for the v3 migration; this v2 ledger tracks the
armed directive's three subsystems against the NEW baseline (v3-only tree: no `static/`, no `/v2/`, no `/static`).

| ID | Subsystem | $S_{current}$ (measured 08:16 UTC) | $\Delta$ deviation | Corrective vector | Gate | Status |
|---|---|---|---|---|---|---|
| A | Legacy retirement (v1/v2) | No `static/` dir; no `/v2/` route; no `/static` mount (main.py:684-707 serves `/`→307, `/web/*.html`, `/web` mount only); `test_v2_dashboard_gone_after_cutover` asserts 404s. DOC DRIFT: `docs/web/INDEX.md` still describes `static/` pinned + `GET /static/*` smoke; `docs/mcp/INDEX.md` maps MCP dashboard to `static/`; `AGENTS.md:59,95` + `docs/HOW_IT_WORKS.md:53,60` + `docs/ARCHITECTURE.md:271` + `docs/REFACTOR_PLAN.md:32-37` + `docs/TAGS.md:19` + `docs/reference/MODULES.md:34-35` reference deleted v2 files; `web/README.md:167` + `web/js/stream/link.js:3` mention v1/v2 relatively | Doc Δ: live docs describe a deleted surface; code Δ = 0 | Rewrite `docs/web/INDEX.md` v2 section → v3-only; fix `docs/mcp/INDEX.md` dashboard row; update `AGENTS.md`, `HOW_IT_WORKS.md`, `ARCHITECTURE.md`, `REFACTOR_PLAN.md`, `TAGS.md`, `MODULES.md` static refs; keep TODO/TRAPS/SESSION_LESSONS history verbatim (historical record, not live contract) + `test_v2_dashboard_gone...` 404 pins | Gate 1: suite green, no static refs in live docs | `[~]` |
| B | v3 backend integration + live ingestion | Demo `demo.js:100-116`: live → `new SMS.link.Session(path, body)`; fake → scripted `Replay`. Console `console.js:141-157`: kind=fake → `Replay`, else live `Session`. Setup gates Launch on `link.ready` (setup-prod.js:286-288; demo source defaults to live when ready, setup-demo.js:159). `v3_live_e2e.py` 4/4 PASS history (Firefox+Chrome × prod+demo, KnownMuse, live verdict + counters). Server WS executors `combat/project_combat/demo_build/binary_combat` + snapshot hydration live | Verify Δ=0 live: Gate 2 re-run offline_scan + v3_live_e2e 4/4 on THIS branch (prior proof was pre-branch ZZ tree) | Re-run Gate 2: `offline_scan` + `v3_live_e2e` 4/4 | Gate 2: live Docker verdicts + zero leftovers | `[ ]` |
| C | Dynamic UI/UX — every mode/option/switch functional | 7 source modes (fixture/build/project/snippet/binary/ingest/system, prod-setup.html:84-91) → `O.compile` per `SOURCES`; run schema in `schema.js` (scan_profile, sweep_passes, research, compression?, vault?); console tabs/filters/maptools/result downloads; demo speed/pause/director. `ui_scan.py` rewritten for v3 (setup→fixture→Launch→console poll). Coverage unknown on this tree: every mode × browser matrix not yet run | Enumerate every control → operate each in headless Firefox+Chrome (Gate 3), fix gaps in v3 code | Per-mode Gate 3 runs + fixes | Gate 3: operated (not loaded) matrix green | `[ ]` |

## Δ-recompute log

- 08:14 UTC: baseline pinned — 1041 passed + 1 skipped, tree clean, branch created.
- 08:16 UTC: recon — code Δ(A)=0 (no static/, no /v2/, 404 test pins); doc Δ(A)≠0 (8 live docs stale); B/C need live proof on this branch.
