# Demo Pack — 3-minute video artifacts (2026-10-31T18:24Z, frontier-delta directive)

## Demo 1 — Best chained attack + patch live (C14 T5b promo-gate → eval, Node)
- Why: cheapest chain of the night (6 calls ≈$0.19, FIRST TRY), two-link unified
  probe (grant → tier cookie → eval), eval ELIMINATED (not filtered) by Blue.
- Live commands (from today's Phase-0 oriented variant, sandbox-proven exit 0):
  ```
  cd phase0/work/c14-orig-check   # oriented variant (identifier-renamed, vuln shape intact)
  # serve: node /workspace/app.js  |  probe: archived Red script from task-1401-c14-report.json
  # expect: normal ok → exploit s=200 body='1v22.23.41' → "VULN chained LinkA+LinkB leaked"
  # patched: write archived Blue replacement (decimal guard + Number arithmetic) → same probe → exit 1 "blocked: injection sanitized"
  ```
  Receipt reference: `task-1401-c14-report.json` (pre 0 / post 1 / benign 0/0);
  today's live replays: `phase0/spotcheck-report.md` §C14.
- Fallback (no Docker): play the archived `task-1401-c14-live.txt` scrollback.

## Demo 2 — Fastest prior replay speedup (C34b T9c HTTP-cookie combo-gate)
- Why: the HTTP-proof rule promotion (holds 2/2: C31, C34) — a vault prior
  (exact-match lookup + typeof guard) replayed on a renamed schema for the cost of
  ONE retry cycle (6 calls p11886/c17416 ≈$0.21) instead of a fresh Red investigation
  (~2× tokens: fresh-chain average ≈$0.25-0.48 on faulted first attempts).
  Before: C34a died on the closing-report schema fault (≈$0.14, no verdict).
  After: verbatim retry VERIFIED first-try — the prior did the work, not the model.
- Live commands:
  ```
  # replay archived Blue template (exact-match lookup) onto renamed C34 schema;
  # archived Red probe from task-3402-c34b-report.json → exit 0 vuln → exit 1 patched
  ```
  Receipt: `task-3402-c34b-report.json` (pre 0 / post 1). Vault: red `b90493849e92`.
- Fallback: `task-3402-c34b-live.txt` scrollback + Gate-3 `task-3403-c34-vault.txt`.

## Demo 3 — This CVE candidate at its highest proven level (validator.js case bug)
- Level: `READY_FOR_RESPONSIBLE_DISCLOSURE` (local evidence only — NOT sent).
- Live commands (sandbox-proven today, exits recorded):
  ```
  cd phase0/work/validator-repro      # pinned 9ff34247 (MIT), unpatched tree
  node /workspace/battery_validator_case.mjs   # → exit 0 "VULNERABLE: 3 case-sensitivity bypass(es)"
  cd ../validator-patched             # same tree + isurl-host-case.patch
  node /workspace/battery_validator_case.mjs   # → exit 1 "blocked: string host lists are case-insensitive"
  node /workspace/benign_check.mjs             # → exit 0 "benign checks passed"
  ```
  Logs: `phase0/validator-repro-log.txt` (exit 0), `phase0/validator-patched-log.txt` (exit 1).
  Patch: `docs/disclosures/validator-isurl-host-case/isurl-host-case.patch`.
  Novelty: `.../novelty_search.md` (no NVD/OSV/GHSA/issue match; CVE-2025-56200 + #887 distinguished).
  Draft: `.../DISCLOSURE_DRAFT.md` (PRIVATE — show the file, do NOT send).
- Fallback: `cat` the two log tails + `git diff` the patch (all local, no network).

## What Meta models did here that a basic API integration would not
The forge's 76 logged Meta calls (muse-spark-1.3 Red + muse-wonder-1.0 Blue, per-call
prompt/completion tokens in every receipt's `usage` block — e.g. C22: 6 calls
p1946/c7370→p3273/c1492) were not "ask for a probe, get a probe". The judging-relevant
behaviors, each tied to a log entry: (1) UNIFIED CHAIN SYNTHESIS — one probe script
asserting a two-link gate→sink flow end-to-end (E14: `/grant` + `Set-Cookie` + `Cookie`
+ exit0/exit1 in a single script; E34b journal: "chain contracts MUST demand the HTTP
round-trip"); a basic integration returns per-sink snippets, never a stateful
multi-request chain. (2) ENVIRONMENT-RESILIENT RE-PROOF — 5 hallucination captures
(C51/C54/C55/C59 + C56 ground-truth dispute) where Red's exit-0 proof STOOD while its
closing report misdescribed the fix, and the retry loop distinguished proof-truth
from report-truth (E59: "the model wrote the fix while denying the vuln; retry cleared").
(3) ABSTRACTED TEMPLATE REPLAY — Blue patches committed as vault priors with
applicability/invariants/CWE fields (67 red + 66 blue records, 133 archetypes,
~266k tokens saved) and replayed on RENAMED variants (Gate-3), including today's
Phase-0 proof that 10 archived probes still exit 0 on unseen trees. A basic wrapper
has no memory across runs; the vault is the memory, and the spot-check is its audit.
