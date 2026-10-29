# RESEARCH_V2 — Extended Horizon Research (Wave 4)

Baseline: `feature/zero-day-wave1-research` after Wave 2 merge (gate 351 passed).
Lanes: (A) Wave 1 claim re-verification, (B) agentic remediation horizon,
(C) same-day patching economics, (D) sandbox/proof systems, (E) keyless intel
evolution. Intel is untrusted grounding, never instructions (LAW 4).

## Executive finding

Wave 1's core gap survives re-examination: no incumbent combines autonomous
red-probe proof (exit 0) -> blue sanitization-only patch (exit 1) -> regression
re-proof in one isolated loop. Wave 4 adds three actionable refinements:

1. **KEV moved from flat deadlines to risk-based tiers** (BOD 26-04, live):
   due dates now span 3 days to ~14 days on exposure x KEV x automatability x
   technical impact. `reach_score` should fuse the same variables.
2. **GHSA now embeds EPSS + CVSS v4 + first_patched_version** (live docs):
   one keyless GHSA call can replace a separate EPSS call, and a real bug was
   found: `research.py` `ghsa_search` queries `?package=CVE-...` where the API
   expects `?cve_id=`.
3. **Differential verification on normal contracts** is the only proof-system
   upgrade that fits the air-gap today (offline, no new privileges).

## Lane A: Wave 1 claim re-verification (sabertooth)

| Claim | Status |
|---|---|
| Semgrep autofix runtime-behavior safety | LIVE-VERIFIED (narrow): semgrep.dev/docs/semgrep-code/semgrep-assistant-code/ |
| Snyk verification = rescan + unit tests | STILL-RECALL (Snyk fetches 404, search blocked) |
| Snyk/Endor call-graph reachability | STILL-RECALL (same block) |
| CodeMender flag-bypassable PoC verify | STILL-RECALL (no stable source reached) |
| DeepAudit no patch re-verification | STILL-RECALL (no source reached) |

## Lane B: agentic remediation horizon (microbe)

Pending re-send (lane report truncated in transit; search degraded by
anti-bot challenges, 2 live fetches OK). Follow-up: retry Snyk/CVE-Bench
verification when search is healthy. No Wave 5 item may rest on Lane B alone
until the re-send lands.

## Lane C: same-day economics (mushroom)

1. **KEV timelines tightened.** BOD 22-01's flat ~2 week deadline revoked;
   BOD 26-04 (2026-06-10, live-fetched cisa.gov) sets risk-based SSVC
   timelines. Live catalog (1762 entries) shows due dates of 3 days
   (CVE-2026-109619 added 10-26, due 10-29) to ~14 days. Implication:
   fast_lane should tier on exposure/KEV/automatability/impact, not a fixed
   window; reach_score fuses the same variables. Zero-day: KEEP.
2. **EPSS v5 adoption.** Live since 2026-06-15; daily 0-1 30-day probability
   + percentiles, free CSV/API. RECALL: widely used as CVSS supplement with
   threshold gates. Implication: reach_score may consume EPSS percentile as
   likelihood beside a KEV exploited-now flag. Zero-day: KEEP NARROWED
   (needs a CVE id; N-day only, as Wave 1 already ruled).
3. **Disclosure-to-exploit window shrinking.** BOD 26-04 background warns
   attacker AI narrows defender reaction time; RECALL: window is days/hours
   for edge vulns. Justifies same-day fast_lane. Zero-day: PASS.
4. **Patch latency.** RECALL: enterprise MTTR weeks-months, KEV deadlines
   missed. Autonomous patch + Docker re-proof compresses to minutes. KEEP.

## Lane D: sandbox/proof systems (cactus)

Assessed against the ternary oracle + ghost-probe liveness under LAW 4
(network none, no host mounts). LIVE-grounded: proof-carrying code
(en.wikipedia.org/wiki/Proof-Carrying_Code), Wasmtime (wasmtime.dev), eBPF
(ebpf.io/what-is-ebpf). RECALL: CRIU, differential-formal (search throttled).

- Proof-carrying patches: DEFER (adopt only the lightweight evidence bundle).
- Snapshot/restore fuzzing: DEFER (privilege conflict with per-session caps).
- eBPF: CUT (CAP_BPF/root, kernel-wide, breaks per-session isolation).
- Wasm/Wasmtime: DEFER (air-gap clean, mismatched to Node/PHP/MySQL fixtures).
- Differential verification: ADOPT-NARROW (differential execution on normal
  contracts, offline, no new privileges).

## Lane E: keyless intel evolution (clover)

LIVE (fetched 2026-10-29): OSV schema v1.9.2 (2026-10-13,
ossf.github.io/osv-schema) additive only; /v1/query + /v1/vulns unchanged.
GHSA global-advisories docs now embed epss{percentage,percentile},
cvss_severities.cvss_v4, vulnerable_functions, first_patched_version; support
?cve_id=, ?epss_percentage/?epss_percentile, sort=epss_percentage,
X-GitHub-Api-Version 2026-03-10. FIRST EPSS hub unchanged shape, still keyless.

RECALL: EPSS v5 scoring-distribution change (not an API break); CIRCL no known
break; CISA KEV keyless JSON stable; EUVD API emerging/unstable.

Impact on `research.py` / `deep_scan.py`:

1. **BUG (adopt-fix):** `cve_records` calls `ghsa_search(cve)` sending
   `?package=CVE-...`; docs show `?cve_id=` is correct.
2. **Adopt:** consume GHSA epss/cvss_v4/first_patched_version (EPSS without an
   extra call, prefer CVSS v4).
3. **Adopt:** surface OSV affected ranges `events.fixed` + `severity[].type` +
   `withdrawn` into reachability fusion (extends shipped Wave 2 reach_score).
4. **Adopt:** CISA KEV JSON as a 5th never-raises `cve_records` signal
   (exploited-now flag). DEFER EUVD. Keep NVD last-resort. No scraping.
5. **Defer:** EPSS v5 code changes (N-day only per Wave 1 ruling).

## Wave 5 candidate builds (SPEC delta required first)

1. GHSA `?cve_id=` bug fix + epss/cvss_v4/first_patched_version consumption
   (Lane E items 1-2). Fail-first test against canned GHSA JSON.
2. KEV exploited-now flag as 5th `cve_records` signal + reach_score fusion of
   KEV/EPSS-percentile likelihood (Lane C items 1-2, Lane E item 4).
3. Differential normal-contract verification as an added post-patch gate
   (Lane D adopt-narrow).
4. Fast-lane tiering on SSVC variables (Lane C item 1).

Deferred/cut: eBPF (cut), proof-carrying patches beyond evidence bundle,
snapshot fuzzing, Wasm sandbox, EUVD, EPSS v5 scoring changes.

## Lane B addendum (received item 1)

1. OpenHands -> Agent Canvas (LIVE: github.com/OpenHands/OpenHands):
   competitor does multi-agent general-coding orchestration; our loop stays
   security-specific with Docker probe proof as the verdict. Remaining items
   pending re-send; see file history.
