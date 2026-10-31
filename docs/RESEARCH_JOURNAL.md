# Research Journal — scientific record per experiment

Run: `overnight_1793434523077_12855248373640259943`.

## E0 — Baseline recon (Phase 0)

- Hypothesis: the tree is green at the claimed 770+ baseline and keyed+Docker
  live proof is possible tonight.
- Method: `python3 .jcode/tools/dev.py check` (full gate); check `.env` key
  length only; `docker info`; read delta-closure brief + chain prompt state.
- Control: no code changes; read-only recon.
- Result: gate exit 0, **781 passed**; `.env` key length 48 present; Docker
  29.9.2 live; delta-closure targets (resilient probes, unified chain) already
  merged on develop (commits `e881e9b`, `60a6d17`, ship `0d53cec`).
- Conclusion: $S_{current}$ = 781 green. Tonight's forge builds ON TOP of the
  delta closure (novel chained fixtures + vault priors), not a re-run of it.
- Reusable prior created: none (recon only).

## E1 — Cycle 1: T4a traversal fixture, Red T4 finding, Blue guard, Gate-3 replay

- Hypothesis: a novel traversal-gated file read (T4a) yields Red exit 0 →
  Blue exit 1 with regressions green, and the abstracted guard replays on an
  unseen variant (renamed identifiers, absolute-path attack).
- Method: Green-authored `read_doc` join-without-check + `/read` service;
  keyed `execute_project_workflow` cycles=1 (Red spark-1.3, Blue wonder-1.0);
  then mechanical Gate-3 replay on renamed-variant tree; vault commit + recall.
- Control: bundled fixtures untouched; source tree asserted byte-identical;
  `docker ps/network` teardown check; UI lockdown holds (`static/` untouched).
- Result: success=True, status retained, receipt pre=0/post=1/regressions 0/0,
  differential_passed, cleanup ok, 6 model calls p11727/c25643 ≈$0.19.
  Red found T4 (traversal to `../../secret.txt`, TOP-SECRET-FORGE) — the T2
  eval sink was reported as candidate but NOT the retained finding; Blue
  patched `read_doc` with realpath+startswith guard (diff in report).
  Gate-3 replay PASS (traversal + abs-path blocked, benign ok).
  Vault: red `6ad9156807d4`, blue `366e65412fc8`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-101-c1-live.txt`, `task-101-c1-report.json`,
  `task-102-c1-vault.txt`.
- Conclusion: Δ(C.1,D.1,E.1) → 0 for the T4a slice; T5-style unified chaining
  on novel fixtures remains open (Red chose single-sink finding — see E2 plan).
- Reusable prior created: T4a red probe strategy + blue containment template
  (vault red/blue records above).
