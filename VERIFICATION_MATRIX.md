# VERIFICATION MATRIX — 2-Layer Deterministic Sweep (100% Succeeded Truth)

> Directive: 100% coverage + 2-layer trap verification. L1 clean-green + L2
> mutation-must-fail = [ST]. Tooling: stdlib only (LAW 10F) —
> `.jcode/tools/verify_cov.py` (sys.monitoring line coverage, no pytest-cov).
> Feature inventory: 644 rows (551 functions + 86 classes + 7 misc) over
> library/ + main.py + tui.py + sms_cli.py + docker harnesses.

## Phase 0 baseline (2026-11-02, `feature/verification-sweep`)

- Gate: 1085 passed + 2 skipped (pre-sweep, from develop merge).
- Inventory: `/tmp/feature_inventory.json` (644 rows; partition counts below).
- Method per partition: (a) measure file coverage with `verify_cov.py` on the
  partition's test set; (b) write missing-behavior tests RED-first; (c) prove
  L1 green; (d) prove L2 trap-fail by reverting the fix in a scratch copy
  (never committing the mutation) — the RED run IS the L2 proof for new tests.

| Partition | Agent | Files | Funcs+Classes | Coverage % | L1 | L2 trap | 4-State | Action |
|---|---|---|---|---|---|---|---|---|
| P1 core (`library/core/`) | audit P1 | 13 | 79+23 | — | — | — | OPEN | dispatched |
| P2 workflows (`library/workflows/`) | audit P2 | 6 | 85+23 | — | — | — | OPEN | dispatched |
| P3 intel (`library/intel/`) | audit P3 | 5 | 71+6 | — | — | — | OPEN | dispatched |
| P4 shared (`library/shared/`) | audit P4 | 9 | 62+5 | — | — | — | OPEN | dispatched |
| P5 services (`library/services/`+tags) | audit P5 | 11 | 103+24 | — | — | — | OPEN | dispatched |
| P6 surfaces (main/tui/sms_cli/docker) | audit P6 | 5 | 100+6 | — | — | — | OPEN | dispatched |
| P7 web+scripts (JS, static) | — | ~66 | n/a (JS) | — | — | — | STATIC | `node --check` in gate; no line-cov |
| P8 targets+video-demo (fixtures, static) | — | ~25 | n/a | — | — | — | STATIC | fixture checks in gate; no line-cov |
