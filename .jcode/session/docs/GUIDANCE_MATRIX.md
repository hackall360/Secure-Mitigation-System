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

## Frontier-Delta Phase 0 spot-check — measured $S_{current}$ (2026-10-31T18:14Z, directive close-frontier-delta)

Empirical re-verification, not ledger claims. Full report:
`~/.jcode/overnight/runs/overnight_1793434579887_18328835991007113135/phase0/spotcheck-report.md`;
replay trees in `phase0/work/<variant>/`.

- 10 priors sampled (seed 20261031, all receipt-PASS): each replayed in REAL Docker
  (`internal=True`, pinned base) on identifier-renamed variants + archived Red probe.
  Vuln-side 10/10 exit 0, patched-side 10/10 exit 1, benign 10/10 exit 0.
  3 variants labeled ORIENTED (C31/C40: archived tree missed `end_headers` on one 200
  branch — urllib-tolerant then, http.client-strict now; C14/C44: archived
  `compressed_text` truncations reconstructed from archived Blue patch). Vuln shapes
  unchanged in all cases; labels are in the report, nothing hidden.
- 5 chains sampled (C4/C7c/C11/C31/C34b): archived receipts all show Red 0 → Red 1 →
  Benign 0/0. 5/5.
- 76 dated meta rows: schema pass 76/76 (timestamp, known model ID, purpose, role,
  outcome); 10 sampled all cross-check against receipts (7 verified with per-call
  usage, 3 error receipts honestly logged as schema faults). 0 INVALID. Note: file
  holds 76 dated + 1 undated recon row; "78 entries" in JUDGING_EVIDENCE counts header
  frame — no material correction needed.
- Spot-check score 100% ≥ 80% threshold → Phase 1 PROCEEDS.
- Gate 0: full suite **798 passed**, UI diff empty, no orphaned containers/networks
  (only pre-existing scbx-*/katzu remain).

| Subsystem | Measured $S_{current}$ | $\Delta$ remaining | Gate |
|---|---|---|---|
| Prior replay (unseen variants) | 10/10 exit-0 + 10/10 exit-1 + 10/10 benign-0, live Docker | none | [x] VERIFIED_ZERO_DELTA |
| Chain re-verification | 5/5 Red 0 → Red 1 → Benign 0 | none | [x] VERIFIED_ZERO_DELTA |
| Meta-call provenance | 76/76 schema-valid, 10/10 receipt-cross-checked, 0 INVALID | none | [x] VERIFIED_ZERO_DELTA |
