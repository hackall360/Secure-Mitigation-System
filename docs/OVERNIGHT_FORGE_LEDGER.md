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
| 2026-10-31T09:21Z | 9 (scout) | none (local reading + batteries) | 0 | Flask-File-Upload upload audit, Python | n/a | n/a | n/a | NEGATIVE (valuable): double-closed traversal, ext-wart unconsumed; no candidate |
| 2026-10-31T09:22Z | 10r | none (ledger analysis) | 0 | self-review: Python 50% | n/a | n/a | n/a | direction: Cycle 10 = PHP T6 end-to-end |
| 2026-10-31T09:25Z | 10 | spark-1.3 + wonder-1.0 (slim) | p8232/c12191 ≈$0.16 | T6b XSS, PHP | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: htmlspecialchars; T6 end-to-end (was co-only); vault T6b; Gate-3 PASS |
| 2026-10-31T09:31Z | 11 | spark-1.3 + wonder-1.0 (slim) | p13896/c31458 ≈$0.27 | T9 invite-gate + T4, Node | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: unified redeem→traverse script; strict containment; vault T9+T4; Gate-3 PASS |
| 2026-10-31T09:34Z | 12 (scout) | none (local reading + Docker-PHP PCRE) | 0 | sabre/vobject+xml audit, PHP | n/a | n/a | n/a | NEGATIVE (valuable): no sinks, entity-loader gated, no ReDoS; no candidate |
| 2026-10-31T09:41Z | 13 | spark-1.3 + wonder-1.0 (slim) | p10236/c17206 ≈$0.21 | T3c tar-sink + T4, PHP | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: allowlist+escape; T4 co-hardened; vault T3c; Gate-3 PASS |
| 2026-10-31T09:43Z | 15r | none (ledger analysis) | 0 | self-review: 3/3/3 balance | n/a | n/a | n/a | direction: Cycles 14-16 = T5-novel + Node scout/pause |
| 2026-10-31T09:46Z | 14 | spark-1.3 + wonder-1.0 (slim) | p11942/c22781 ≈$0.19 | T5b promo-gate + eval, Node | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: dual-decimal, eval eliminated; cheapest chain; vault T5b; Gate-3 PASS |
| 2026-10-31T09:48Z | 15 (scout) | none (local reading + static only) | 0 | @hapi/shot inject helper, Node | n/a | n/a | n/a | INCONCLUSIVE (first): no sinks; __proto__ static-only, deps absent; HYPOTHESIS-open |
| 2026-10-31T09:53Z | 16 | spark-1.3 + wonder-1.0 (slim, 2 attempts) | p9542/c13549 ≈$0.16 | T6c stored-XSS, PHP | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 2 (/tmp store): a1 read-only baseline fail; a2 render-time escape; vault T6c; Gate-3 PASS |
| 2026-10-31T09:55Z | 20r | none (ledger analysis) | 0 | self-review: 3/4/4 balance | n/a | n/a | n/a | direction: T4d-reject, T5-novel, Node scout |
| 2026-10-31T09:55Z | 17a | none (Docker-PHP battery) | 0 | T4d basename design | n/a | n/a | n/a | REJECTED at Gate 0: basename kills traversal; $0 spent; rule pinned |
| 2026-10-31T10:02Z | 17 | spark-1.3 + wonder-1.0 (slim, 2 attempts) | ≈$0.48 total | T4c+T2e, Node | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 2 (transient fault cleared): T4 retained+CLOSED; T2e OPEN by record (follow-up); vault T4c+T2e; Gate-3 PASS |
| 2026-10-31T10:08Z | 18 | spark-1.3 + wonder-1.0 (slim) | p9743/c28984 ≈$0.27 | T2e-only box, Node | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: CLOSES C17 OPEN record; char-class (ctor retained, residual noted); vault T2e-closed; 5-shape battery |
| 2026-10-31T10:17Z | 19 | spark-1.3 + wonder-1.0 (slim, 3 attempts) | ≈$0.46 total | T4e check-split, PHP | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 3 (short contract): a1+a2 closing-report faults, a3 resolve-FIRST; vault T4e; Gate-3 PASS |
| 2026-10-31T10:19Z | 30r | none (ledger analysis) | 0 | self-review: 3/6/4 balance | n/a | n/a | n/a | direction: PHP/Python depth; Cycle 21 zero-dep exotic |
| 2026-10-31T10:20Z | 21 (scout) | none (local reading + node ESM) | 0 | he entity codec, JS zero-dep | n/a | n/a | n/a | NEGATIVE (valuable): encode neutralizes all T6; strict throws closed; cross-validates htmlspecialchars; no candidate |
| 2026-10-31T10:22Z | 22 | none (local battery) | 0 | T1c Gate-0 | n/a | n/a | n/a | PASS: CASE-flip + limit-arithmetic signals confirmed; proceed |
| 2026-10-31T10:24Z | 22 | spark-1.3 + wonder-1.0 (slim, short) | p12958/c23376 ≈$0.21 | T1c ORDER-BY/LIMIT, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: boolean-flip signal; allowlist+LIMIT-?; vault T1c; Gate-3 PASS |
| 2026-10-31T10:32Z | 23 | spark-1.3 + wonder-1.0 (slim, short, 2 attempts) | ≈$0.30 total | T3d backtick, PHP | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 2 (transient): escape-outside-quotes; inertness replay; vault T3d; Gate-3 PASS |
| 2026-10-31T10:37Z | 24 | spark-1.3 + wonder-1.0 (slim, short) | p12526/c19587 ≈$0.18 | T4f + T1d-open, Python | pre 0 | post 1 | 0/0 + diff-pass | PARTIAL (C17 pattern): T4 retained+CLOSED; T1d Gate-0-proven but MISSED by Red; solo queued; vault T4f; Gate-3 PASS |
| 2026-10-31T10:42Z | 25 | spark-1.3 + wonder-1.0 (slim, short) | p11290/c16122 ≈$0.14 | T1d SOLO, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: CLOSES C24 OPEN; ONE-sink rule validated; vault T1d-closed; Gate-3 PASS |
| 2026-10-31T10:46Z | 26 | spark-1.3 + wonder-1.0 (slim, short) | p9209/c17823 ≈$0.16 | T4g prefix-strip, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: strip-bypass; normalize-after-strip; vault T4g; Gate-3 PASS |
| 2026-10-31T10:51Z | 27a | none (node battery) | 0 | T2f setTimeout-string | n/a | n/a | n/a | REJECTED at Gate 0: dead in Node22 (ERR_INVALID_ARG_TYPE); pivot wins |
| 2026-10-31T10:54Z | 27 | spark-1.3 + wonder-1.0 (slim, short) | p10525/c16768 ≈$0.17 | T2f2 vm-leaky, Node | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: de-leak + digit-requirement; escape unspellable; vault T2f2; Gate-3 PASS |
| 2026-10-31T10:59Z | 28 | spark-1.3 + wonder-1.0 (slim, short) | p9193/c11628 ≈$0.12 | T3dd include-LFI, PHP | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: allowlist-or-404; twin-plant provability; vault T3dd; Gate-3 PASS |
| 2026-10-31T11:04Z | 29 | spark-1.3 + wonder-1.0 (slim, short) | p11350/c25525 ≈$0.24 | T3e format-template, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: parse-then-format gate; new sink family (CWE-74); vault T3e; Gate-3 PASS |
| 2026-10-31T11:09Z | 30 | spark-1.3 + wonder-1.0 (slim, short) | p11577/c22277 ≈$0.23 | T1e solo + T9b-open, Python | pre 0 | post 1 | 0/0 + diff-pass | PARTIAL (import-probe dodges gate): T1e sink CLOSED; T9b-link OPEN by record; HTTP-proof rule; vault T1e+T9b; Gate-3 PASS |
| 2026-10-31T11:14Z | 31 | spark-1.3 + wonder-1.0 (slim, short) | p13991/c21632 ≈$0.18 | T9b HTTP-cookie chain, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: CLOSES C30 OPEN; cookie round-trip enforced+honored; HTTP-proof rule validated; vault T9b-closed; Gate-3 PASS |
| 2026-10-31T11:19Z | 32 | spark-1.3 + wonder-1.0 (slim, short) | p11994/c24285 ≈$0.33 | T3f triple-stash, Node | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED first-try: normalize + remove-raw-branch; 3rd CWE-74 member; vault T3f; Gate-3 PASS |
| 2026-10-31T11:22Z | 33 (scout) | none (local reading only) | 0 | validator.js isURL/escape | n/a | n/a | n/a | INCONCLUSIVE (build-blocked): static leans guarded; zero-build rule refined |
| 2026-10-31T11:29Z | 34 | spark-1.3 + wonder-1.0 (slim, short, 2 attempts) | ≈$0.35 total | T9c+T1f chain, Node | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 2 (transient): HTTP round-trip honored; exact-match lookup; HTTP-proof 2/2; vault T9c; Gate-3 PASS |
| 2026-10-31T11:31Z | 35r | none (ledger analysis) | 0 | self-review: 9/9/8 balance | n/a | n/a | n/a | direction: T7/T8-family gate chains + zero-dep scout |
| 2026-10-31T11:36Z | 35 | spark-1.3 + wonder-1.0 (slim, short, 2 attempts) | ≈$0.29 total | T7b hw-key chain, Python | pre 0 | post 1 | 0/0 + diff-pass | VERIFIED attempt 2 (transient): HTTP round-trip honored; HTTP-proof 3/3; vault T7b; Gate-3 PASS |

Cycle 1+ rows appended as they complete. Failure rows stay (rejected rule:
3 failed adaptations = `[REJECTED]`, container destroyed, next cycle).
