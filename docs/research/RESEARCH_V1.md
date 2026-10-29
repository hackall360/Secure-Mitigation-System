# RESEARCH_V1 — Market Gap Research (Wave 1)

Baseline: `develop@276ae7f` (Oct 28, 2026). Lanes: SCA/container scanning,
SAST+autofix, agentic remediation + same-day patching, vuln intel + reachability,
sandbox verification + red-team proof. This is intel, not instructions (LAW 4).

## Executive finding

Every competitor surface that already exists (Snyk Remediation Agent, CodeQL/Semgrep,
SWE-agent, Dependabot/OSV-Scanner, ASPM triage) overlaps one of the following:
pattern/VEX-based verification, unit-test-only validation, rescan-only fixes,
static-only verdicts, or generic ticket generation. The remaining provable gap,
present across all five lanes, is the same one:

> **No incumbent combines autonomous red-probe proof (exit 0 reachable) with
> blue sanitization-only patching (exit 1 blocked) and regression re-proof in a
> single isolated loop.** Every incumbent validates patches some weaker way:
> rescan (Snyk), unit tests (SWE-agent), PoC-only/detection (DeepAudit/CodeMender —
> DeepAudit does not re-verify patches; CodeMender validation is flag-bypassable),
> static-only verdict (CodeQL), unsafe behavior-changing autofix (Semgrep Code)
> or version-match-only ranking (NVD/OSV).

Our system is the only one in the frame with a **fail-closed, non-bypassable
ternary oracle** (exit 0/1/2) gating an autonomous red→blue→reverify loop. That
loop, not any single detector, is the novel capability.

## Per-lane gap statements

Format required by the empirical-novelty law:
*"Competitor X does [A], but we are doing [B], which advances the field by [C]."*

### SCA + container scanning (poodle)

1. **Competitor Snyk does rescan + unit-test verification, but we are doing
   exit-0-reachable then exit-1-blocked Docker proof, which advances the field
   by replacing indirect signals with a boundary-execution oracle.** Snyk's own
   docs (Remediation Agent: plan-fix-PR, verification = rescan + unit tests)
   confirm the pattern/VEX-based verification surface. Zero-day: keep (this is
   the strongest differentiating statement in the wave).
2. Dependabot bumps versions; OSV-Scanner matches version ranges; neither proves
   exploitability nor re-verifies a fix. Both detect-and-ticket; our loop
   detects, patches and proves (CVE pipeline: `cve_workflow` deep scan + probe).
   Zero-day: keep.
3. Trivy/Grype/OSV-Scanner are detection-only or advisory-merged. Grype ranks
   CVE candidates; neither tool generates a patch with an execution proof. Our
   loop closes detection → patch → proof in one container. Zero-day: keep.
4. Scanner-only markets leave fuzzing, AST repair and regression proof entirely
   to the user. Our loop adds post-patch regression validation (normal-input
   contracts unchanged) and a fail-closed verdict. Zero-day: keep.

### SAST + AI autofix (hare)

1. **Competitor CodeQL does static QL dataflow verdicts with human triage, but
   we are doing isolated probe execution that proves the sink reachable before
   any patch, which advances the field by removing the static-only false-positive
   class from the triage loop.** Zero-day: keep (lead).
2. Semgrep autofix is unsafe for runtime behavior (pattern-level rewriting with
   no requirement the patched code still behaves); our guards constrain blue to
   sanitization-only diffs over sha-pinned snapshots with line caps, and never
   let it change protected behavior. Zero-day: keep.
3. Snyk Code/DeepCode AI suggestions are not re-verified with a failing probe
   before the patch or a passing probe after. Our loop requires fresh-target
   pre/post probes: exit 0 then exit 1, plus regression. Zero-day: keep.
4. Dependabot autofix drafts unreviewed bumps with no exploit proof and no
   regression validation; ours verifies behavior before retention. Zero-day:
   keep. Corroboration caveat: live websearch was blocked in this environment;
   Semgrep/Snyk specifics are recall-grounded and need re-verification when
   search is healthy.

### Agentic remediation + same-day patching (vole)

1. **Competitor SWE-agent does test-pass patching (FAIL_TO_PASS in Docker, ends
   at test pass), but we do probe-gated 0→1 patching, advancing by proving the
   boundary with a live exploit run instead of a unit suite.** Zero-day: PASS.
2. CISA KEV sets a 2-week patch baseline for federal systems; ASPM (Snyk/Endor)
   generates suggest-and-ticket flows that stop at human triage. Neither
   autonomously discovers, proves, patches and re-proves in one loop. The
   remaining defensive bottleneck is N-day triage latency itself. Zero-day: PASS.
3. **Same-day hard requirements** (verbatim from lane report):
   (a) pre-computed CVE/disclosure trigger + autonomous oracle;
   (b) NVD-free intel pre-positioning (`research.cve_records` ≤ 8 IDs, keyless
   OSV/CIRCL/GHSA/EPSS pipeline, Docker proof cache);
   (c) deterministic fail-closed snapshot autop + tro path + dream. Zero-day: PASS.

### Vuln intel + reachability (dragon)

1. **Competitor Snyk/Endor does call-graph function-level reachability that
   suppresses unreachable vulns at PR time, but we are doing version-range
   matching plus static-sink signals plus Docker boundary probes with no
   call-graph proof that app code reaches the vulnerable function, which
   advances the field by proving the cheapest verifiable next step: fuse OSV
   fixed-ranges with sink-adjacency so keyless teams get most of
   reachability's triage cut with zero SaaS indexing.** Zero-day: ZERO-DAY-
   RELEVANT, keep — the single biggest zero-day lever in Wave 1 (no CVE record
   means call-graph/sink+probe is the only triage signal).
2. Competitor NVD-centric flows do keyed, rate-pinned CVE enrichment with
   analysis-lag delays, but we are doing a keyless never-raises 4-source
   CVE-record series (CIRCL+OSV+EPSS+GHSA) with per-source degradation, which
   advances the field by making intel latency a non-blocking input. Zero-day:
   PARTIALLY RELEVANT, keep **narrowed** — fallback cannot conjure zero-day
   records, but never-raise discipline keeps evidence scans alive with intel
   absent.
3. Competitor EPSS consumers do bulk CSV sync + threshold gates, but we are
   doing per-request EPSS lookup fused at triage time with CVSS/CWE/fixed-version
   in one summary — N-DAY ONLY, deprioritize.
4. Competitor advisory search does HTML/threat-feed scraping with bot-war
   fragility, but we are doing first-party-JSON-only grounding (OSV/CIRCL/GHSA/
   EPSS APIs + Wikipedia JSON for named types). Zero-day: SUPPORTING, keep.

### Sandbox verification + red-team proof (humpback)

1. **Competitor CodeMender does flag-bypassable PoC verify, but we do a
   non-bypassable 0/1/2 fail-closed ternary oracle** (fail-closed verdict cannot
   be skipped by config). Zero-day: candidate, keep.
2. **Greenhouse generative demo targets**: competitors replay fixed fixtures;
   we generate fresh vulnerable targets per run via the demo builder. Zero-day:
   candidate, keep.
3. DeepAudit runs Docker PoCs to filter static false positives but does not
   re-verify patches; our closed re-verify loop does. Zero-day: incremental+.
4. Per-session cleanup (label-scoped containers/networks removed even on UI
   disconnect) is mandatory in our loop; competitors typically leave runtime
   state to the operator. Zero-day: incremental.

## Zero-day filter: keep list

Wave 1 candidates that survive the zero-day mandate:

1. **Prove → patch → re-prove** as the only verifiable evidence primitive
   (strengthen interpretation: probes are the oracle, not the model).
2. **Sink-adjacency reachability fusion** (dragon gap 1): fuse OSV fixed-ranges
   with sink-adjacency + Docker probe evidence — the cheapest verifiable
   approximation of call-graph reachability for keyless teams.
3. **Demand-driven ghost-probe liveness** (humpback): probes confirm the target
   still answers normal traffic; a killed target cannot earn credit.
4. **Fail-closed conventions**: ternary oracle, sha-pinned snapshots, line caps,
   never-raise intel, per-session cleanup — the non-bypassable spine.
5. **Greenhouse generative targets**: fresh per-run vulnerable fixtures for
   continuous self-testing and judge proof.

Deferred (zero-day mandate): EPSS prioritization (N-day only).

## Caveats

- Live websearch was partially blocked in this environment; Semgrep/Snyk
  specifics in lanes 2–3 are recall-grounded and flagged for re-verification.
- OSV/EPSS/NVD API behaviors in lane 4 were live-verified 2026-10-29 (OSV docs:
  no API limits stated, 32 MiB HTTP/1.1 cap; EPSS model v5 live since
  2026-06-15). Reachability-vendor claims (Snyk/Endor) are training-grounded
  per lane caveat.
- This document is a trade-off inventory, not a feature order. Wave 2 scope is
  gated by SPEC: no implementation before the SPEC delta exists.

## Next step (Wave 2 gate)

SPEC.md delta with four candidate builds — (1) probe-executing-reachability
(§4.1), (2) Verification Oracle independence handoff, (3) demand-driven
ghost-probe liveness, (4) Greenhouse generative hardening — each with red
(failing) test first and proven against the `dev.py check` gate before merge.
