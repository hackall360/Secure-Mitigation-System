# Wave 10 (migration): SPEC 14.9 Wave 5 delta

Novelty-bar items (SPEC 14.9 items 1-3, Lanes 2/4/5 citable only per
14.8 gating; Lanes 1/3/6 pending) wired as guards on the fast-lane and
verify loops. Follow-on to [WAVE9.md](WAVE9.md); SPEC anchor
`docs/SPEC.md` 14.9.

## Freshness stamping flow (item 1, Lane 5)

Stamp, enrich, gate, emit — four functions in two modules:

1. Stamp: `modules/intel/research.py` — `kev_lookup` stamps
   `extra["kev_date"]` from the catalog `dateAdded`; `epss_score` stamps
   `extra["epss_date"]` from the FIRST API `date` row. Both truncated to
   32 chars; empty when the API omits the date.
2. Enrich: `_enrich_reach_signals` (`modules/workflows/cve_workflow.py`)
   copies the stamps onto the OSV summary as `kev_date` / `epss_date`
   (first CVE alias only, at most 1 KEV + 1 EPSS lookup, never-raise).
3. Gate: `_source_fresh` (`cve_workflow.py`) — true unless the stamped
   date proves older than `_SOURCE_FRESH_DAYS = 1`. Missing or
   unparseable dates count as fresh (fetched live inline this scan);
   future dates count as fresh. Only a proven-old vintage drops.
4. Emit: `_queue_evidence` — stale-dated KEV/EPSS signals read as
   `absent` in the tie-break line while the enriched numeric fields stay
   untouched (ordering is fail-closed too). Never blocks the scan.

## EUVD exclusion rationale + assertion points

Rationale: EUVD has no verified keyless JSON endpoint (2026-10-29: site
200s, API returns SPA HTML), so the fast lane excludes it rather than
hallucinating coverage. Mechanism: `FAST_LANE_EXCLUDED_SOURCES =
frozenset({"euvd"})`, enforced by `assert_fast_lane_source_allowed`,
called at each fast-lane consultation site (`osv`, `kev`, `epss`). An
excluded source raises `AssertionError` (fails closed loudly); allowed
sources return `True` and never block. The exclusion is asserted, not
merely absent — a future EUVD wiring trips the assertion.

## Frozen-pool digest mechanism (item 2, Lane 2 keep)

Mutation ids stay frozen + seeded (`MUTATION_SEED = 20261029`,
`MUTATION_COUNT = 4`; `checks.py`). `_assert_frozen_pool` serializes
`mutation_pool_snapshot()` (canonical JSON, sorted keys) and compares
its SHA-256 against `FROZEN_MUTATION_POOL_SHA256`; any drift
(unseeded RNG, set ordering, time/uuid dependence) raises `ValueError`
fail-closed. An offline pool proposal path may exist only outside the
verify loop and must freeze + seed before use. Fail-first test: any
nondeterminism across runs fails (`tests/test_mutation_checks.py`).

## Template-in-budget acceptance shape (item 3, Lane 4 adoptable)

Template-shaped inputs (regex allowlists, strict casts, 400-reject
blocks) are accepted only inside the unchanged `EDIT_BUDGET_LINES = 60`
guard (`patches.py` — 14.9 never widens it). `is_solver_synthesized_shape`
rejects solver markers (`check-sat`, `declare-const/fun`,
`assert-valid`, `get-model`, `z3 import`, `semfix`, `directfix`) by
patch-text inspection only, never probe output (LAW 4). Fail-first on
guard rejection + rationale (`tests/test_guard_rationale.py`).

## Cuts list (per V5, SPEC 14.9)

Cut: live generative red loops, open-ended fuzz storms, chain agents,
solver synthesis, LLM-judged correctness, rescan-only validation, EUVD
in fast lane. Deferred: Lane 1 edge-variant closes + Lane 3 heuristics
until full texts land.
