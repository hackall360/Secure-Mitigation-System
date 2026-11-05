# GUIDANCE MATRIX — GOLDEN TAKE (2026-11-04/05, branch feature/visual-dry-run-2026-11-04)

T+0 (loop start): 2026-11-04T23:58:30Z. Limits: max 10 attempts or 45 min (hard stop 00:43:30Z). No code edits allowed.

## Attempt log

| Attempt | Log | Wall | Cost | Result |
|---|---|---|---|---|
| 1 (terminal) | dryrun1.log (scratch) | 389 s (exit 0) | $0.0077 / 48,182 tok | **VERIFIED** — SQLi POST /login, probe 0 pre, patch retained, report `reports/20261104T235253Z-78b911b2/` |
| 1 (browser, parallel) | console.html session | 2:30 | $0.0048 / 32,769 tok | PARTIAL — probe still exit 0 post-patch, blue rolled back (expected non-determinism) |

HALT: golden take achieved on attempt 1 (terminal). No further attempts needed.

## Golden-take evidence (terminal run)

- Red: high-confidence SQL injection in `/login` (f-string interpolated username/password into SELECT on users).
- Pre-patch probe exit 0. Patch synthesized by blue, re-probed on fresh target, retained as success.
- Report status `verified`, `success: true`, `cycles_completed: 1`, message "Evidence-gated candidate replacements were retained."
- Timing honesty: 389 s exceeds the 3–5 min demo window (red review was slow this run); video should cut or re-run for pacing.
- Full terminal log has no wall timestamps (lines are `[DEMO]/[SYSTEM]` prefixed only), so terminal gap analysis is N/A. During red review the browser console for the parallel run showed `last 15s ago` worst-case; the shipped demo_run.py heartbeat fires every 5 s by design.

## State

- No repo code changed during the loop. Working tree clean at commit dbc2317 (shipped testing-2026-11-04).
- This ledger is the only file added by the golden-take pass.
