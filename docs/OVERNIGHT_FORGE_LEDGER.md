# Overnight Forge Ledger — every forge cycle

Run: `overnight_1793434523077_12855248373640259943`. Branch: `feature/overnight-forge`.
Columns: time (UTC) | cycle | models | tokens | chain (classes+lang) | Red | Blue | regression | outcome.

| time | cycle | models | tokens | chain | Red | Blue | regr | outcome |
|---|---|---|---|---|---|---|---|---|
| — | 0 | — | 0 | baseline recon | — | — | 781 passed | $S_{current}$ = 781 green |
| 2026-10-31T08:23Z | 1 | spark-1.3 (red) + wonder-1.0 (blue) | p11727/c25643 ≈$0.19 | T4 traversal + T2 eval, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED: retained, vault red+blue T4a, Gate-3 replay PASS |
| 2026-10-31T08:33Z | 2 | spark-1.3 + wonder-1.0 (3 attempts) | ≈$0.67 total | T6 reflect + T2 eval, Node | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 3: a1 over-budget rollback, a2 contract/test mismatch rollback, a3 retained; vault red+blue T2b; Gate-3 replay PASS |
| 2026-10-31T08:36Z | 3 (scout) | none (local code reading + loopback) | 0 | PyJWT JWKS/alg, Python | n/a | n/a | n/a | NEGATIVE (valuable): 5/5 guards hold, no candidate, checklist prior kept |
| 2026-10-31T08:41Z | 4 | spark-1.3 + wonder-1.0 | p14157/c27695 ≈$0.28 | T7 role-gate + T1 SQLi, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: unified A→B script, 1-line parameterize; vault T7+T1; Gate-3 PASS |
| 2026-10-31T08:53Z | 5 | spark-1.3 + wonder-1.0 (3 attempts) | ≈$0.30 total | T3 cmd-arg, PHP | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 3 (slim agents=1): a1+a2 RedReport schema faults, a3 escapeshellarg; vault T3a; Gate-3 PASS |
| 2026-10-31T09:04Z | 6 (scout) | none (local reading + in-process WSGI) | 0 | werkzeug safe_join traversal, Python | n/a | n/a | n/a | NEGATIVE (valuable): 10+6 battery, all 404, no candidate; battery kept |
| 2026-10-31T09:13Z | 7 | spark-1.3 + wonder-1.0 (3 attempts) | ≈$0.47 total | T8 selector + T2 eval, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 3 (7c): a1 true-SSRF exit-2, a2 self-dial 502, a3 selector chain; vault T8b+T2c; Gate-3 PASS |
| 2026-10-31T09:18Z | 8 | spark-1.3 + wonder-1.0 (slim) | p10018/c20771 ≈$0.21 | T4b + T2d, Node (x-lang) | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: dual guard; T4a prior spans languages; vault T4b+T2d; Gate-3 PASS |

Cycle 1+ rows appended as they complete. Failure rows stay (rejected rule:
3 failed adaptations = `[REJECTED]`, container destroyed, next cycle).
