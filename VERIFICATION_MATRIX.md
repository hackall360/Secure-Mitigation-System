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
| P1 core (`library/core/`) | audit P1 | 13 | 79+23 | gap-file green | 7/7 | RED pre-write | ST | MERGED `test_verify_core_gap_red.py` (6e3de1d2) |
| P2 workflows (`library/workflows/`) | audit P2 | 6 | 85+23 | gap-file green | 14/14 | RED pre-write | ST | MERGED `test_verify_workflows_gap_red.py` (0e04d861) |
| P3 intel (`library/intel/`) | audit P3 | 5 | 71+6 | gap-file green | 14/14 | RED 2-fail pre-fix | ST | MERGED `test_verify_intel_gap_red.py` (f498117b) |
| P4 shared (`library/shared/`) | audit P4 | 9 | 62+5 | gap-file green | 41/41 | RED 37-pass/1-fail pre-fix | ST | MERGED `test_verify_shared_gap_red.py` (aa27c857) |
| P5 services (`library/services/`+tags) | audit P5 | 11 | 103+24 | gap-file green | 36/36 | RED 17-fail pre-triage | ST | MERGED `test_verify_services_gap_red.py` (3a2b0794) |
| P6 surfaces (main/tui/sms_cli/docker) | audit P6 | 5 | 100+6 | gap-file green | 19/19 | RED arithmetic pre-fix | ST | MERGED `test_verify_surfaces_gap_red.py` (89b19c13) |
| P7 web+scripts (JS, static) | — | ~66 | n/a (JS) | STATIC | gate | n/a | STATIC | `node --check` in gate; no line-cov |
| P8 targets+video-demo (fixtures, static) | — | ~25 | n/a | STATIC | gate | n/a | STATIC | fixture checks in gate; no line-cov |
| R1-coord (pricing/budget/profile) | coordinator | 3 | — | targeted | 6/6 | mutant `cached=0`→2fail | ST | MERGED `test_verify_gap_coordinator_red.py` (385ab145) |
| R1-deadknobs (config env knobs) | audit P1b | 1 | — | targeted | 18/18 | RED pre-green | ST | MERGED `test_config_dead_knobs_red.py` (8b11c16a) |
| R2-redact (redact/chatter/personas) | audit R2A | 3 | — | gap-file green | 24/24 | RED pre-write + mutant | ST | MERGED `test_verify_r2_redact_red.py` (aa7c88a3) |
| R2-parse (compress/scanparse/scanners) | audit R2B | 3 | — | gap-file green | 21/21 | L2 dedup-mutant 5-fail | ST* | MERGED `test_verify_r2_parse_red.py` (114f1c67) — *first run 19/19 pass, no RED; credited on mutant-fail only (SL noted, not hidden) |
| R2-vault (vault/budget/records) | audit R2C | 3 | — | gap-file green | 16/16 | RED `count=1` revert-fail | ST | MERGED `test_verify_r2_vault_red.py` (1e16f5cc) |
| R2-svc (mcp/intake/projects/binary) | audit R2D | 4 | — | gap-file green | 20/20 | RED 5-fail/15 pre-fix | ST | MERGED `test_verify_r2_svc_red.py` (86e11290) |

## Close-out (2026-11-03, `feature/verification-sweep`)

- **Gate: 1303 passed + 2 skipped, All checks passed** (was 1085 pre-sweep; +218 from 236 new gap tests net of formatted churn… precisely: 1085 + 236 new − 18 pre-existing file-test deltas = 1303).
- **236 new tests, all L1 green; L2 trap-fail proven per file** (mutant reverts: pricing `cached=0`→2fail, dedup→5fail, vault `count=1`→RED, per-file RED runs; hamster R2-parse exception logged above).
- **Remediation log (Phase 2):** services 17 [FL] (wrong expectations vs real contracts — pydantic list validation, `_binding_live` root semantics…), shared 1 [FL] (coordinator's own short-circuit misread, corrected on record), R2-parse cross-file bleed = stale `.pyc` from coordinator L2 mutant (TRAPS entry, purged, 236/236 after), toolchain ruff 0.16.7→0.17.3 format drift on 2 pre-existing files (whitespace-only sync, tests green).
- **Coverage honesty:** per-file line-coverage measured with stdlib tracer (see `verify_cov.py` output in-session); live Muse/Docker/browser paths stay gate-verified (offline_scan/project_scan/ui_scan), NOT line-covered. No 100.00%-everywhere claim — the ledger reports what was measured.
- **Artifacts:** `.jcode/tools/verify_cov.py` (stdlib coverage tracer, header-commented, reused across 12 files); `docs/TRAPS.md` stale-pyc entry; all worktrees removed at ship.
