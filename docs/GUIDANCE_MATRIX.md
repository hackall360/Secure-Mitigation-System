# Guidance Matrix — master Δ tracker (overnight research division & vault forge)

Run: `overnight_1793434523077_12855248373640259943`. Branch: `feature/overnight-forge`.
Baseline $S_{current}$: **781 passed** (`dev.py check` exit 0, 2026-10-31, evidence:
run `validation/task-000-baseline-gate.txt`).
UI lockdown acknowledged: `git diff --stat -- static/ templates/` MUST stay empty;
any non-empty diff is reverted immediately ($\Delta_{regression} > 0$).
Status legend: `[ ] UNVERIFIED` / `[/] IN_PROGRESS` / `[x] VERIFIED_ZERO_DELTA`.

| Subsystem | $S_{current}$ | $S_{target}$ ($\Delta$) | Corrective vector | Gate |
|---|---|---|---|---|
| A Orchestration (ledgers + roles) | no ledgers | 9 ledger files live, every delegation logged | Phase 0 init (this commit) | [/] IN_PROGRESS |
| B Taxonomy engine | fixtures only, no taxonomy file | `VULN_TAXONOMY.md` + `vuln_taxonomy.json` feeding prompts | Phase 0 seed, refine per cycle | [/] IN_PROGRESS |
| C Green synthesis | 5 bundled fixtures | ≥2 novel 2-class chained fixtures, Docker-proven | Cycle 1+2 synthesis | [ ] UNVERIFIED |
| D Red chaining | chain fixture exists | chained probe exit 0 on novel fixture, ≤3 adaptations | Cycle 1+2 keyed runs | [ ] UNVERIFIED |
| E Blue mitigation | workflow exists | minimal patch: Red→1, regression→0, suite→0, template abstracted | Cycle 1+2 keyed runs | [ ] UNVERIFIED |
| F External scout + CVE lab | WILD log only, no candidates file | `CVE_CANDIDATES.md` with evidence levels; private drafts only | Cycle 3 scout | [ ] UNVERIFIED |
| G Vault priors | vault infra exists, 0 forge priors | ≥1 committed prior + Gate-3 unseen-variant replay | post-Cycle 1 | [ ] UNVERIFIED |
| H Showcase/docs | ledgers pending | per-cycle updates, top-3 shortlists, judging narrative | every cycle | [/] IN_PROGRESS |

Recompute $\Delta$ from test/command output before and after every atomic task.
