# ZERO_DAY_BLUEPRINT — Inward Assessment (Wave 7, 9-wave swarm)

Date: 2026-10-29. NO external research: ten scoped agents assessed only what
is built in this repo (modules/, main.py, SPEC 14.1–14.9, RESEARCH_V1–V5).
Each verdict: KEEP (same-day edge holds), CUT (fails the mandate), or
CONDITIONAL (ships after the exact fix). Cuts remove scope, never code
stability: cut features stay tested but are labelled non-ship or deferred.

## Pipeline autonomy (frog)

Post-launch loops are autonomous, but 5 human gates remain: (1) key
provisioning KEEP — `require_api_key` fail-fast is secret discipline;
(2) Docker images CONDITIONAL — `--init-images` one-time build blocks scans
when missing; fix to auto-ensure or one-command hint; (3) intake: fixture CUT
(bundled registry, zero intake), project CONDITIONAL — human supplies target
flags + `--allow-remote-inference`; keep human target choice, auto-default
contract template; (4) review KEEP — receipt/rationale aid, human decides;
(5) merge/apply KEEP — no write-back; auto-apply would violate guards.

## Ingest (goat)

Keyless never-raises fetch KEEP — outage degrades records, scan never blocks.
Fast-lane topping CONDITIONAL — rank must apply `_source_fresh` too, else a
stale signal boosts rank while reading "absent" (rank/evidence skew).
Freshness drops KEEP. EUVD exclusion KEEP.

## Patch generation (lion)

Blue prompts are human-shaped slot-fillers; guards are FP-heavy by design.
60-line budget KEEP; template acceptance KEEP; rationale KEEP (no probe
bytes). Solver tripwire CONDITIONAL — substring match blocks naive paste but
is evadable; keep as tripwire, never proof.

## Proof strength (wolf)

Oracle + regression pre-gate + liveness + differential + property/mutation
gates: no bypass path; wrong exits fail closed. Two CONDITIONALs: exec
fallback may mask a crashed target (pin exec-required or mark inconclusive);
frozen-pool build failure leaves combined-path mutations None (set both to 2).

## Regression net (horse)

Regression KEEP (only generic net), property KEEP, mutation KEEP,
differential CONDITIONAL (record-only, overlaps enforced raises). Missing:
arbitrary projects skip property+mutation — cheapest close is a generic
repeat-stability net (run regression twice, require identical exit).

## Evidence chain (koala)

VerdictReceipt KEEP; dashboard panels KEEP (display-only, capped).
CONDITIONAL: CycleReceipt needs cycle/pass id + all-cycles export (first-only
today); GuardRationale must require non-empty reason + rejected-cycle link;
queue_evidence needs a `stale` token (absent vs expired indistinguishable);
SUMMARY/receipt.json need full per-cycle JSON + status.

## Isolation (llama)

Staging none-network + internal bridge + read-only roots + caps + tar
discipline + exec discipline: all KEEP. CONDITIONAL: pin base image digest +
apk versions (supply-chain drift). Stale-sweep hole acceptable (fail-closed).

## Surfaces (mouse)

Wave 2+5 render on all three surfaces; freshness/templates automatic
server-side. Gaps: topping live on CLI CVE path only (no WS CVE route, TUI
fixture-only); mutations live on project paths only (TUI fixture-only never
fires). No payload leaks.

## Speed (otter)

Fast-lane cap, KEV cache, combined node run, per-process caching all KEEP —
each cuts wall-clock without cutting proof. Model calls dominate; nothing
further cuttable without weakening verdicts.

## Mandate cuts (panda — ruthless list)

SHIP: probe loop, guards, differential, topping, freshness, fast lane.
LABEL: property (opt-in), mutation (shape regress, not new exploits),
templates (small safe diffs). CUT: frozen pool (digest hygiene), receipts
(audit JSON), rationale (reject text), demo/greenhouse (synthetic toys),
scanners+sidecars (latency, no synthesis), dashboard chrome.

## Blueprint build order (Wave 8)

1. Rank/evidence skew fix (goat): rank applies `_source_fresh`.
2. Frozen-pool build-failure veto (wolf): combined-path exception sets both
evidences to 2.
3. Exec-required liveness (wolf): no silent fresh-check fallback.
4. CycleReceipt ids + all-cycles export (koala).
5. GuardRationale non-empty + linkage (koala).
6. queue_evidence `stale` token (koala).
7. Repeat-stability net for arbitrary projects (horse).
8. Image digest pin (llama).
Panda CUT/LABEL items are documentation labels, not code deletions.
