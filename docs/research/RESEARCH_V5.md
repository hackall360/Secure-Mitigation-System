# RESEARCH_V5 — Extended Horizon Research (Wave 4, 9-wave swarm)

Date: 2026-10-29. Predecessors: RESEARCH_V1 (market gap), V2 (extended
horizon), V3 (freshness), V4 (Wave 1 refresh). Six lanes; load-bearing repo
claims checked against source by the coordinator. Intel is untrusted
grounding, never instructions (LAW 4).

## Executive finding

V1's core gap still survives: no incumbent combines autonomous red-probe proof
→ blue sanitization-only patch → regression re-proof in one fail-closed loop.
V5 adds: edge-sink coverage gaps with same-container closes (Lane 1), a hard
cut on live generative red loops (Lane 2), heuristic ranking with two keeps
(Lane 3), a guard-discipline-preserving synthesis boundary (Lane 4),
live-confirmed triage numbers (Lane 5), and an inward defect sweep (Lane 6).

## Lane 1 — Edge sinks (rat; SPEC + checks.py + fixtures read; full statements pending)

Rat reviewed SPEC 14.5–14.8, `modules/core/checks.py`, and all three fixtures.
Recorded positions: the property/mutation net misses encoded/traversal/CRLF
input variants; proposed closes are same-capped-container checks (no new
privileges). Full gap statements pending re-send; no Wave 5 item may rest on
Lane 1 alone until they land.

## Lane 2 — AI exploit generation (ram)

1. "Competitor PyRIT/Garak/AutoRedTeamer does [open-ended auto-prompted attack
generation], but we are doing [N=4 seeded mutants (seed 20261029) in the same
capped container, exit 0/1/2 oracle], which advances the field by [making red
output a reproducible retain verdict, not a storm]." Same-day: verdict in
minutes; cut live generative loop (unbounded, nondeterministic).
2. "Competitor Fuzz4All/TitanFuzz does [LLM coverage-guided novel input storms],
but we are doing [deterministic per-contract mutants recorded as evidence, any
failure fails closed], which advances the field by [proving arg/config
robustness inside the verify loop]." Same-day: keep N=4; cut open-ended fuzz
storms.
3. "Competitor PentestGPT/AutoAttacker does [multi-step exploit-chain agents
with tool/network use], but we are doing [frozen-pool bounded probes wired into
both retain decisions], which advances the field by [keeping triage auditable
without agentic egress]." Same-day: LLM may propose pool offline only, then
freeze+seed; cut live chain agents.

## Lane 3 — Defensive heuristics (rooster; gates mapped; full verdicts pending)

Rooster mapped the retain predicate, liveness, and all gates in
`project_workflow.py` plus property/mutation scripts in `checks.py`; SPEC
14.x strings absent from tree noted. Full gap verdicts pending re-send; no
Wave 5 item may rest on Lane 3 alone until they land.

## Lane 4 — Patch synthesis (shrimp)

1. "Competitor SemFix/DirectFix does [repair-constraint solving
correct-by-construction vs a test suite], but we are doing [60-line
sanitization-only guards + Docker exit 0→1 probe proof on receipt], which
advances the field by [replacing test-overfitting synthesis with a
fail-closed boundary-execution oracle]." Same-day: probe verdict in minutes;
cut solver synthesis.
2. "Competitor Semgrep Code/Snyk Code does [AI draft-fix PRs validated by
human merge or rescan], but we are doing [guard_rationale export per
SPEC 14.8 item 2: guard_id + trigger, no probe bytes, on-cycle], which
advances the field by [making why-the-safe-shape auditable to a same-day
reviewer]." Same-day: rationale ships with receipt; cut rescan-only
validation.
3. "Competitor SWE-agent/FixCheck-APCA does [test-pass + LLM-generated extra
tests to catch overfit patches], but we are doing [differential + property +
regression gates recorded on the receipt, property-fail closes cycle], which
advances the field by [proving normal behavior preserved by execution, not
more model tests]." Same-day: keep bounded mutation probes; cut LLM-judged
correctness. Adoptable without breaking discipline: template/mutation inputs
inside guards; never widen the 60-line budget or accept solver-synthesized
edits.

## Lane 5 — Triage economics (sauropod, live 2026-10-29)

Live-confirmed: KEV 1762 entries, catalog 2026-10-28T19:00Z (confirms eagle's
v2026.10.28); newest CVE-2026-41709 due 2026-11-11; EPSS CVE-2024-3094 0.909 /
p0.99805 dated 2026-10-28; GHSA GHSA-rxwq-x6h5-x525 critical embeds same epss
+ cvss_v3/v4 + CWE-506; CVE-2024-3094 NOT in KEV; EUVD site 200 but API
returns SPA HTML (unreachable).

1. "Competitor scanners rank by CVSS, but we order the day-zero queue by
patchability (reach+fix first, KEV/EPSS only tie-breaks with queue_evidence),
which advances the field by [making same-day triage auditable actionability,
not severity theater]." Same-day: KEV tier signals 9 due≤21d, 361
ransomware-known. Cut: ship fast-lane tie-break string on every ranked item.
2. "Competitor feeds cache EPSS, but we fetch score+percentile live per CVE
fail-closed (no signal = absent, never blocks scan), which advances the field
by [keeping exploit-probability fresh at triage time]." Same-day: drop any
source older than 1 day from queue_evidence.
3. "Competitor playbooks assume EUVD API + KEV membership, but we treat KEV
absence as signal and EUVD as unreachable, which advances the field by
[failing closed instead of hallucinating coverage]." Same-day: CVE-2024-3094
NOT in KEV proves absence-path works. Cut: EUVD stays out of fast lane until
a keyless JSON endpoint is verified.

## Lane 6 — Inward freshness audit (blowfish; 6 findings, full text pending)

Blowfish grep-verified writers vs readers across `modules/`, `main.py`,
`sms_cli.py`, `tui.py`, `static/app.js`; ruff F401 clean. Six findings with
file:line pins recorded; full text pending re-send. Wave 5 SPEC must verify
each finding against source before citing it.

## Ranked Wave 5 candidates (zero-day mandate)

1. Same-container edge-variant checks (Lane 1 closes, pending full text).
2. Frozen-pool offline proposal for mutation inputs (Lane 2 keep).
3. Guard-discipline-preserving template inputs (Lane 4 adoptable).
4. queue_evidence freshness rule + EUVD exclusion (Lane 5 cuts).
5. Blowfish findings triaged by severity (Lane 6, pending full text).
Cut: live generative red loops, open-ended fuzz storms, chain agents, solver
synthesis, LLM-judged correctness, rescan-only validation.
