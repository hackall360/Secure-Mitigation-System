# ZERO_DAY — Executive Architecture (9-wave swarm close)

Source blueprint: `ZERO_DAY_BLUEPRINT.md` (root, commit `cb79d4d`) — ten
inward verdicts (frog/goat/lion/wolf/horse/koala/llama/mouse/otter/panda),
no external research. Panda mandate verdicts (`ZERO_DAY_BLUEPRINT.md:77-81`):

- SHIP: probe loop, guards, differential, topping, freshness, fast lane.
- LABEL: property (opt-in), mutation (shape regress, not new exploits),
  templates (small safe diffs).
- CUT: frozen pool (digest hygiene), receipts (audit JSON), rationale
  (reject text), demo/greenhouse (synthetic toys), scanners+sidecars
  (latency, no synthesis), dashboard chrome. CUT/LABEL are documentation
  labels, not deletions — cut features stay tested.

## The 8 build items (Wave 8, all merged)

1. Rank applies freshness (goat): `_fast_lane_rank`
   (`modules/workflows/cve_workflow.py:135`) gates KEV/EPSS through
   `_source_fresh` (`cve_workflow.py:66`) so ordering agrees with
   `_queue_evidence` (`cve_workflow.py:101`). Stale-dated signals rank as
   absent, never boost.
2. Frozen-pool build-failure veto (wolf): combined-path exception sets
   BOTH `properties_ev` and `mutations_ev` to exit-2 evidence
   (`modules/workflows/project_workflow.py:699-708`); `None` mutations
   would pass the gate vacuously.
3. Exec-required liveness (wolf): post-probe liveness without exec against
   the same still-running target degrades to inconclusive exit 2, never a
   silent pass (`project_workflow.py:771-792`).
4. CycleReceipt ids + all-cycles export (koala): `CycleReceipt`
   (`project_workflow.py:263`) with cycle/pass ids via `build_cycle_receipt`
   (`:285`), exported per-cycle by `extract_cycle_receipts` (`main.py:844`).
5. GuardRationale non-empty + linkage (koala): `GuardRationale`
   (`project_workflow.py:207`); explicit empty reasons fail closed
   (`:236-237`), absent reasons default to naming the guard.
6. `stale` token in queue evidence (koala): `_signal_token`
   (`cve_workflow.py:86`) renders `stale:<YYYY-MM-DD>` so reviewers can
   separate expired intel from never-signalled (`absent`).
7. Repeat-stability net for arbitrary projects (horse):
   `repeat_stability_passed` (`project_workflow.py:160`) over the
   `repeat_regression` field (`:96`); mismatched exits poison regression
   to exit 2 (`:802-858`). Fixture paths leave repeat `None` so the gate skips.
8. Image digest pin (llama): `PINNED_PYTHON_BASE`
   (`modules/core/docker_manager.py:37-38`), enforced by
   `_assert_dockerfiles_pinned` (`:107`), bases pinned in
   `docker/Dockerfile.target:3` + `docker/Dockerfile.verifier:3` (apk
   `nodejs`/`php84` locked in target `:8`).

## Gate progression

`dev.py check`: dashboard-refresh baseline 394 passed -> current 479
passed, all checks green. Fail-first throughout: each item landed RED
then green (stale-rank test, combined-build veto test, exec-required
tests, receipt/rationale tests, repeat-net tests).

## Live proof

- `.jcode/tools/offline_scan.py`: 3/3 fixtures verified through real
  Docker (recorded in TODO S3).
- `.jcode/tools/project_scan.py`: 2/2 cycles retained, properties exit 0
  both cycles after the T1/T2 shape-split fix (recorded in TODO T2).
- Dashboard: browser-operated demo controls on `:18099` (own server,
  killed after; TODO L5).

## Honest gaps

- TUI is fixture-only: no demo mode, no project path (`tui.py` selects
  from `FIXTURE_ORDER` only); mutations/property nets never fire there.
- No WS CVE route: `main.py:557-565` exposes only
  `/ws/combat/{target_key}`, `/ws/project`, `/ws/demo`; the CVE fast lane
  (`execute_cve_scan`) is CLI-only.
- Dashboard `socketQuery` (`static/app.js:954`) omits `dependency-track`
  from the research-scanner allowlist the server accepts (server 5-set).
- Digest pins recorded-not-verified in-repo: the offline
  `docker inspect` RepoDigest check is asserted in a code comment
  (`docker_manager.py:34-36`), but no inspect-output artifact is
  committed, so a future rebuild cannot re-verify the vintage.

Up: [index](index.md) · Spec: [../SPEC.md](../SPEC.md) ·
Blueprint: `ZERO_DAY_BLUEPRINT.md` (repo root)
