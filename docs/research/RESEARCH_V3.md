# RESEARCH_V3: Freshness audit of shipped Wave 5, frontier intel, and the next proof upgrade

Date: 2026-10-29. Predecessor: `RESEARCH_V2.md`. Three read-only lanes;
load-bearing code claims re-verified by the coordinator against source.

## Lane A: code audit of the Wave 5 merges (coordinator-verified)

| Sev | Finding | Evidence |
|---|---|---|
| MED | `deep_scan.py:359/363` KEV/EPSS tie-breaks are **dead in production**: `summarize_osv_vuln` (deep_scan.py:250) never sets `kev_listed` or `epss_percentile`, so `reachability_score` always reads the defaults. Wave 5 O2 tests stubbed the summary dict directly, so the gap was invisible. | grep: `kev_listed` appears only at the consumer; producer dict has no such keys. |
| MED | `research.py:357` `kev_lookup` refetches the full 1.82 MB KEV catalog per CVE id; `cve_records` fans out over up to 8 ids. No cache. | source read. |
| LOW | `deep_scan.py` `min(score, 30)` cap is vacuous (max reachable without fix/sink is 20); evidence strings can claim tie-breaks that never fire until the MED above is fixed. | arithmetic read. |
| LOW | `research.py:118` OSV/CIRCL direct CVE fetch uses the 1 MiB default cap vs 4 MiB elsewhere; large OSV records degrade silently. | source read. |
| LOW | `cve_workflow.py:236` fast-lane sort ignores severity/KEV beyond score. | source read. |
| LOW | `intel_search.py:130` `osv_lookup_by_cve` skips CVE shape validation. | source read. |
| INFO | `research.py:319` `epss_score` uses `strip().upper()` not `sanitize_cve_id`. | source read. |
| NONE | Sweep: no callers pass CVE ids to package-shaped endpoints (`ghsa_search`/`osv_query_package`) after O1. | caller grep. |

Novelty framing for the fix: competitors' scoring pipelines (scanner
prioritization in Trivy/Grype) compute scores inside one tool where producer
and consumer share a struct. SMS fuses intel across four keyless feeds, so
the producer/consumer field contract is the risk. Wiring the fields **through
the real summary producer** and testing that path (not the stubbed dict) is
the discipline item: it converts a dead tie-break into a live one.

## Lane B: frontier intel (live-verified, 2026-10-29)

- KEV catalog `2026.10.28`, 1762 entries, adds `forensicTriage: Yes/No` and
  `cwes: []`; `requiredAction` cites BOD 26-04.
  https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
- EPSS API v1 keyless, unchanged shape. https://api.first.org/data/v1/epss
- GHSA REST now exposes `epss_percentage`/percentile fields, `cvss_v4`,
  `credits[]`. https://docs.github.com/en/rest/security-advisories/global-advisories
- OSV schema v1.9.2 (2026-10-13): strict `id` regex, `credits[]`.
  https://ossf.github.io/osv-schema/
- CIRCL CVE 5.2 records carry CISA SSVC 2.0.3 in `containers.adp`.
  https://cve.circl.lu/api/cve/CVE-2024-3094
- CISA SSVC tree unchanged (Track/Track*/Attend/Act).

Implications: KEV `forensicTriage=Yes` is a candidate extra tier signal
(recall-shaped, needs live check at implementation time); GHSA can now
supply EPSS so the FIRST call could be dropped later (not urgent; both are
keyless and cached behavior matters more, see Lane A MED 2).

## Lane C: next proof upgrade

Current: `differential_passed` = baseline regression exit 0 and patched
regression exit 0 (fail-closed on None). Candidates ranked:

1. **Property/metamorphic checks on normal contracts (S, best air-gap fit).**
   Deterministic in-container properties (id commutativity, 404 for random
   ids, config idempotence) catch overfit sanitization that fixed equality
   asserts miss. Novelty: scanners assert vuln-absence; per-cycle
   behavior-preservation properties are rare in harness output.
2. **Coverage-guided probe mutation counts (M).** N mutated payloads must
   stay blocked; quantifies boundary strength; cost-gated by container caps.
3. VEX emission (S, parity) and SARIF export (S, parity): interop only, no
   new proof. Defer until a consumer exists.

## Verdict for Wave 7/8

- Wave 7 (correctness): wire `kev_listed`/`epss_percentile` through
  `summarize_osv_vuln` enrichment in `cve_workflow` (bounded lookups per
  CVE alias, never-raises), tested through the real producer path; KEV
  catalog per-process cache in `research.kev_lookup`.
- Wave 8 (proof + hardening): property/metamorphic normal-contract checks;
  LOW bundle (cap consistency, sanitize reuse, CVE shape check).
- Wave 9: docs + one adventure item only if Waves 7-8 land clean.

No Wave 7 item rests on recall alone: Lane A is source-verified, Lane B is
live-verified with URLs, Lane C is design analysis labelled as such.
