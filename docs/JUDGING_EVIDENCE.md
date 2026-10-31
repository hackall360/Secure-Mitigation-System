# Judging Evidence — rolling map to rubric

Run: `overnight_1793434523077_12855248373640259943`.

## Impact (30%)

- Cycles 1+2+4 VERIFIED: three novel chained fixtures proven in Docker
  (Red 0 → Blue 1 → regressions 0) + 6 vault priors with 3 Gate-3 replays.
  Cycle 3 scout: PyJWT audit, no hole, reusable checklist.
- Per-cycle keyed spend ≈$0.19-0.28; two fail-closed rollbacks + one
  contract fix demonstrate the guard rails working, not failing.

## Use of Meta AI Tooling (25%)

- Phase 0: no model calls (recon only). Cycles use Red `muse-spark-1.3` +
  Blue `muse-wonder-1.0` with token accounting in `META_TOOLING_LOG.md`.
- Novel capability to demonstrate: chained two-weakness synthesis in ONE
  unified probe payload, environment-resilient probes on unseen trees,
  abstracted patch templates replayed on unseen variants (Gate 3).

## Technical Depth (20%)

- Baseline 781 green; fail-closed ternary oracle; air-gapped sandbox;
  encrypted vault with Gate-3 reusability replay.

## Demo (25%)

- No video tonight (user-gated). Demo-ready shortlist:
  - Top chains: (1) C4 T7+T1 unified A→B single-script SQLi-behind-cookie-gate;
    (2) C2 T6+T2 Node eval sink with decimal-allowlist fix; (3) C1 T4a
    traversal-to-secret with realpath containment.
  - Top priors: T7+T1 parameterize+neutralization semantics; T2b decimal
    allowlist; T4a realpath containment. All Gate-3 replayed.
  - Top CVE candidates: none (PyJWT scout refuted; checklist kept).

## Push The Frontier + Agentic bonus

- Cycle 3 external scout (permissive repos, local clone, sandboxed analysis,
  evidence-leveled candidates, private disclosure drafts only).

## Research Delta Audit — morning consolidation (2026-10-31T16:28Z, run `...3579887`)

Computed $\Delta = S_{target} - S_{current}$ against the Research Division
mission (Push The Frontier + Agentic bonus + Meta Tooling 25%). Measured
from repo state, not ledger claims. Evidence: taxonomy v43 JSON, ledger
rows, vault stats, META_TOOLING_LOG.md, CVE_CANDIDATES.md.

| Item | Measured count | Evidence | Verdict |
|---|---|---|---|
| New taxonomy subclasses (target-family breadth) | 53 subclasses across T1–T9 (T1x6 T2x6 T3x8 T4x8 T5x5 T6x6 T7x5 T8x4 T9x5) | `docs/vuln_taxonomy.json` v43 | [x] VERIFIED |
| Chained fixtures Red 0 → Blue 1 → Regression 0 | 45 VERIFIED rows in ledger (3 partials closed by follow-ups) | `docs/OVERNIGHT_FORGE_LEDGER.md`, per-cycle receipts in run validation/ | [x] VERIFIED |
| Priors committed to vault | 133 known_archetypes (67 red + 66 blue), `vault_stats()` live | agent run at 16:27Z | [x] VERIFIED |
| Priors passing Reusability Replay on unseen variants | 44 Gate-3 replays logged PASS (last: C63 8/8) | ledger Gate-3 column | [x] VERIFIED |
| External GitHub repos tested locally | 11 scout cycles (PyJWT, werkzeug, FFU, sabre, hapi/shot, he, validator.js, escape-string-regexp, shell-quote + 2 asymmetry probes) | `docs/RESEARCH_JOURNAL.md` E-sc [#]outs, CVE_CANDIDATES scout sections | [x] VERIFIED |
| CVE Candidates HYPOTHESIS | 14 hypothesis mentions, all refuted or open-negative (PyJWT SSRF/alg-none refuted; validator confusion open; he/ent-codec negative) | `docs/CVE_CANDIDATES.md` | [x] VERIFIED (as negatives) |
| CVE Candidates REPRODUCED_LOCALLY | 1 — validator.js isURL host-list case bug, sandbox exit 0 (3 bypasses), pinned 9ff34247 MIT | `docs/disclosures/validator-isurl-host-case/`, run `phase0/validator-repro-log.txt` | [x] VERIFIED |
| CVE Candidates PATCH_VERIFIED | 1 — `host.toLowerCase()` before both `checkHost` calls; sandbox exit 1 + benign 0 | `docs/disclosures/validator-isurl-host-case/isurl-host-case.patch`, run `phase0/validator-patched-log.txt` | [x] VERIFIED |
| CVE Candidates NOVELTY_CHECKED | 1 — NVD/OSV/GHSA/repo-issues searched, no match; CVE-2025-56200 + #887 distinguished | `docs/disclosures/validator-isurl-host-case/novelty_search.md` | [x] VERIFIED |
| Responsible-disclosure drafts | 1 — PRIVATE draft (summary, commit, repro, impact, patch, mitigation, timeline placeholder); NOTHING sent | `docs/disclosures/validator-isurl-host-case/DISCLOSURE_DRAFT.md` | [x] VERIFIED (as local draft; send is human-only) |
| Meta model calls logged | 78 entries (spark-1.3 + wonder-1.0, per-cycle costs) | `docs/META_TOOLING_LOG.md` (86 lines) | [x] VERIFIED |

$\Delta$ remaining (honest): the forge loop is a closed-world machine —
45 self-made fixtures verified against self-made patches. The Push The
Frontier gap CLOSED 2026-10-31 (directive ...frontier-delta): one third-party
reproduction (validator.js case bug, sandbox exit 0), one verified upstream patch
(battery exit 1 + benign 0), one novelty-checked finding (keyless-scope log, no
match), one private disclosure draft (NOT sent — human-only). Remaining risk,
stated honestly: keyless-novelty scope (no commercial feeds), packaged
`validators.test.js` not re-run here (no babel — maintainer action), severity SMALL
in isolation (boundary-relies-on-string-lists + attacker-influences-case). Scout cadence (11 runs) proves the
pipeline reaches outward, but every outward result was NEGATIVE by design
(guarded libraries hold). The missing capability is a confirmed-vulnerable
third-party target, not more self-fixtures. Hotspots C41/C42/C48 (3 OPEN)
are fixture-side stalls, not frontier evidence.
