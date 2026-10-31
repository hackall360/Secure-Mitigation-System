# CVE Candidates — strict evidence levels (NEVER claim an assigned CVE)

Run: `overnight_1793434523077_12855248373640259943`.

Levels: `HYPOTHESIS` → `REPRODUCED_LOCALLY` (deterministic exit 0 in sandbox
+ logs) → `PATCH_VERIFIED` (Blue patch → exit 1 + regressions exit 0) →
`NOVELTY_CHECKED` (searched existing CVE/Advisory refs, documented why novel)
→ `READY_FOR_RESPONSIBLE_DISCLOSURE` (PRIVATE draft in `docs/disclosures/`,
never published).

No candidates yet. Scout runs every 3rd cycle (first: Cycle 3).
