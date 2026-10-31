# Guidance Matrix — master Δ tracker (overnight research division & vault forge)

Run: `overnight_1793434523077_12855248373640259943`. Branch: `feature/overnight-forge`.
Baseline $S_{current}$: **781 passed** (`dev.py check` exit 0, 2026-10-31, evidence:
run `validation/task-000-baseline-gate.txt`).
UI lockdown acknowledged: `git diff --stat -- static/ templates/` MUST stay empty;
any non-empty diff is reverted immediately ($\Delta_{regression} > 0$).
Status legend: `[ ] UNVERIFIED` / `[/] IN_PROGRESS` / `[x] VERIFIED_ZERO_DELTA`.

| Subsystem | $S_{current}$ ($S_{target}$ met?) | $\Delta$ remaining | Corrective vector | Gate |
|---|---|---|---|---|
| A Orchestration (ledgers + roles) | 9 ledgers live, every keyed call logged | self-review cadence (every 5 cycles; at cycle 4: T7 once, no repeat >40%) | Cycle 5 diversity check | [/] IN_PROGRESS |
| B Taxonomy engine | v1 JSON valid (T1-T7, priors linked) + md | next: Cycle-5 subclass or cross-lang proof | Cycle 5 | [/] IN_PROGRESS |
| C Green synthesis | 3 novel chained fixtures (C1 Python, C2 Node, C4 Python) | continue Cycle 5 (new family) | Cycle 5 | [/] IN_PROGRESS |
| D Red chaining | 3 Docker exit-0 proofs (2 single-sink, 1 unified A→B) | unified-chain on second family | Cycle 5 | [/] IN_PROGRESS |
| E Blue mitigation | 3 minimal patches (guard, allowlist, parameterize) | continue template abstraction | Cycle 5 | [/] IN_PROGRESS |
| F External scout + CVE lab | PyJWT audit negative-valuable, checklist kept | next scout Cycle 6 (smaller target) | Cycle 6 | [/] IN_PROGRESS |
| G Vault priors | 6 records (red+blue T4a/T2b/T7a), 3 Gate-3 replays PASS | continue per-cycle | Cycle 5 | [/] IN_PROGRESS |
| H Showcase/docs | ledgers current through Cycle 4; TRAPS appended | top-3 shortlists done; keep current | Cycle 5 | [/] IN_PROGRESS |

Recompute $\Delta$ from test/command output before and after every atomic task.

## Morning consolidation — measured $S_{current}$ (2026-10-31T16:27Z, run `...3579887`)

Empirical re-verification, not ledger claims. Evidence:
`validation/phase0-gate-rerun.txt` in run `...3579887`.

- Full gate re-run from clean tree: **791 passed, 1 warning** (third-party
  Starlette only) — matches claimed 791. Zero regressions vs baseline.
  UI lockdown: `git diff --stat main...HEAD -- static/ templates/` EMPTY.
- Branch: `feature/overnight-forge`, 69 commits ahead of main (64 sibling
  forge + 5 own). Own: 7c11f6a (debug fail-loud), 3cd70d3 (fingerprint
  vacuous-tag), 448d92f (tamper fail-closed), 7fab037 (ARCHITECTURE docs),
  b0fb476 (atomic commit). Touched files: modules/core/agents.py (also
  touched by sibling e25d724 — adjacent debug block, no hunk overlap),
  modules/intel/sms_vault.py (own-only), docs/ARCHITECTURE.md (sibling
  last touched W1-W3 era — no overlap), 4 new test files (own-only).
  No duplicate commits; no conflicting vault/taxonomy edits (own commits
  touch neither taxonomy nor DISC*/ledger files).
- Docker hygiene: 1 running container (`loving_goldwasser`,
  purplebox-target-base, `--network none`, bind `/tmp/h61`) is MY OWN
  leftover from the C61 scout battery — flagged for teardown below.
  Pre-existing exited `scbx-*` sandboxes and third-party `*_default`
  networks belong to other projects — untouched. No vault-named volumes.
- Vault integrity: `vault_stats()` reads clean; the 3 new fail-closed
  behaviors (missing-dir, tamper-scan, atomic commit) are covered by
  8 new RED tests, all green. No secrets in any diff (only
  `unit-test-key-*` placeholders). `/tmp` writes: operator-scoped
  mkstemp debug dir + sibling `imgconv` extraction — both 0600-scoped,
  tracked, cleaned.
- Residual risk: the stray `loving_goldwasser` container (mine) must be
  removed; recorded as action item.

| Subsystem | Measured $S_{current}$ | $\Delta$ remaining | Gate |
|---|---|---|---|
| Gate suite | 791 passed, 0 failed (re-run 16:26Z) | none | [x] VERIFIED_ZERO_DELTA |
| UI lockdown | empty diff | none | [x] VERIFIED_ZERO_DELTA |
| Branch integrity | 69 commits, 5 own cleanly separated | merge decision (human) | [/] IN_PROGRESS |
| Docker hygiene | 0 running containers (own stray `loving_goldwasser` stopped+removed 16:27Z; /tmp fixture debris swept, fixture sources retained) | none | [x] VERIFIED_ZERO_DELTA |
| Vault integrity | stats clean, 8 new RED tests green | none | [x] VERIFIED_ZERO_DELTA |
