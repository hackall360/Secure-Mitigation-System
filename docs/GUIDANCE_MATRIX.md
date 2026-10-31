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
