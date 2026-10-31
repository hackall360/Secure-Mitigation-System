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

Cycle 1+ rows appended as they complete. Failure rows stay (rejected rule:
3 failed adaptations = `[REJECTED]`, container destroyed, next cycle).
