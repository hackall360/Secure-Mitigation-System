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
