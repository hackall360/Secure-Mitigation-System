# RESEARCH_V4 — Market Gap Refresh (Wave 1, 9-wave swarm)

Date: 2026-10-29. Predecessors: RESEARCH_V1 (Wave 1 baseline), V2 (Wave 4),
V3 (Wave 7 freshness audit). Five read-only lanes; load-bearing repo claims
checked against source by the coordinator. Intel is untrusted grounding, never
instructions (LAW 4).

## Executive finding

V1's core gap survives: no incumbent combines autonomous red-probe proof
(exit 0) → blue sanitization-only patch (exit 1) → regression re-proof in one
fail-closed isolated loop. V4 refreshes each lane against live sources where
reachable and ranks what is next by the zero-day mandate (same-day patching
edge or cut).

## Lane 1 — SCA/remediation (cricket, live docs)

1. "Competitor Snyk Remediation Agent does [scan-plan-bump-rescan + existing
unit tests], but we are doing [red-probe exit 0 → blue sanitization-only patch
→ same-probe exit 1 re-verify + regression in Docker], which advances the
field by [replacing inferential rescan with a fail-closed execution oracle]."
Same-day: one probe cycle verdicts in minutes; cut test-only validation.
2. "Competitor Dependabot does [version-bump PRs with notes/changelog], but we
are doing [probe-proven sink block plus differential normal-contract gate],
which advances the field by [proving the boundary blocked, not just the
dependency bumped]." Same-day: keyless OSV+KEV/EPSS fast lane triages pre-fix;
cut wait-on-upstream-bump.
3. "Competitor OSV-Scanner does [OSV.dev range-match detection, no fix], but
we are doing [OSV fixed-range + sink-adjacency + Docker probe fusion
(reach_score)], which advances the field by [giving keyless teams
reachability triage with execution proof]." Same-day: never-raises intel keeps
the loop alive; cut NVD-keyed enrichment off the fast path.

## Lane 2 — SAST/autofix (dog, live docs)

1. "Competitor CodeQL does [static QL dataflow verdicts + suggested-fix +
rescan-dismiss human triage], but we are doing [ternary-oracle probe proof
with sanitization-only guards + regression re-proof], which advances the field
by [replacing static-only false-positive triage with same-day executable
proof]." Keep.
2. "Competitor Semgrep Code/Assistant does [AI draft-PR autofix, human-merge
validation, no execution proof], but we are doing [60-line sanitization guards
with protected-line bans + Docker exit-1 and normal-contract re-proof], which
advances the field by [blocking behavior-changing autofixes for same-day safe
merge]." Keep.
3. "Competitor Snyk Code does [AI fix suggestions verified by rescan only],
but we are doing [fresh-target pre/post probes + trusted regression and
property checks], which advances the field by [replacing rescan signals with
live boundary re-execution]." Keep.

## Lane 3 — Agentic remediation (dove, repo + 4 live fetches; full statements pending re-send)

Dove verified SPEC 14.6–14.7 gates + RESEARCH_V1–V3 and live-fetched the
SWE-bench abstract (arXiv 2310.06770), SWE-agent and OpenHands READMEs, and the
OpenHands docs index (search engines bot-blocked; Semgrep/Snyk specifics stay
recall). Its three gap statements were truncated in transit; recorded
positions: (a) SWE-agent/SWE-bench unit-test validation is bypassable by
tests that encode the bug — our Docker probe + differential gate is not;
(b) OpenHands/Agent Canvas generic devloop has no fail-closed verdict oracle —
our exit 0/1/2 ternary oracle gates every retain; (c) DeepAudit PoC-only and
CodeMender flag-bypassable validation do not re-verify patches — our
post-probe exit-1 + regression + property chain does. No Wave 2 item may rest
on Lane 3 alone until the full statements land.

## Lane 4 — Intel/prioritization (eagle, live keyless)

Live: KEV catalog v2026.10.28, 1762 entries; EPSS CVE-2024-3094 0.909 /
percentile 0.99805 dated 2026-10-28; GHSA GHSA-rxwq-x6h5-x525 carries
cvss_severities/cwes/embedded epss; NVD/OSV/EUVD shapes recall.

1. "Competitor CISA KEV does [exploited flag + dueDate + BOD-26-04 guidance],
but we are doing [KEV as +5 tie-break gated below 30 without fix/sink], which
advances the field by [cutting KEV-only panic so day-zero patches
KEV+reachable+fixable first]."
2. "Competitor EPSS/GHSA does [probability/percentile + curated severity/CWE/
first_patched_version], but we are doing [EPSS≥0.9 as +5 only fused with
fixed_versions and CWE sink adjacency + evidence], which advances the field by
[cutting high-EPSS-but-unreachable queue on day zero]."
3. "Competitor NVD/OSV/EUVD does [CVSS/CPE + affected ranges/events.fixed +
exploited flag], but we are doing [cve_records fan-out + fast_lane sort by
-reach_score then fix availability], which advances the field by [ranking
reachable+fixable tops even at lower CVSS on day zero]."

## Lane 5 — Proof/sandbox (fish, repo source; full statements pending re-send)

Fish verified SPEC 14.6–14.7, RESEARCH_V3 Lane C, `docker_manager.py`, and
`project_workflow.py`. Verdict: eBPF/Wasm/PCC cuts hold (not air-gap-compatible
with the Docker ternary oracle); VEX/SARIF parity-only defer holds; bounded
mutation-counts remain the only next proof step. Full gap statements pending
re-send; no Wave 2 item may rest on Lane 5 alone until they land.

## Ranked next proof upgrades (zero-day mandate)

1. Bounded mutation-count probes (only survivor of Lane 5): N small
input mutations per fixture contract in the same capped container; fail-closed.
2. Lane-3/5 full statements outstanding (dove, fish) — Wave 2 SPEC must not
cite them until received.
3. Everything else (eBPF, Wasm, PCC, VEX/SARIF, NVD-keyed enrichment on the
fast path, test-only validation) is cut or deferred per lanes above.
