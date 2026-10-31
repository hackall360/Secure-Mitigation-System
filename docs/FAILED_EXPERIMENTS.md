# Failed Experiments — negative results (valuable research, never delete)

Run: `overnight_1793434523077_12855248373640259943`.

None yet. The 3-attempt `[REJECTED - UNPATCHABLE]` / `[REJECTED - UNEXPLOITABLE]`
rule applies: destroy container, log here, begin next cycle immediately.

## F1 — C2a: Blue 96-line parser over surgical budget (2026-10-31)

- Red exit 0 stood; Blue's full arithmetic evaluator changed 96 lines over
  the 60-line guard → rolled back, no proof, no vault commit. Lesson: steer
  Blue to allowlists, not parsers. Evidence: `task-201-c2-*`.

## F2 — C2b: contract/test mismatch on `40+2` (2026-10-31)

- Minimal Blue patch accepted by guard but broke the Green's own regression
  (`calc('40+2')` asserted while contract said decimal-only) → rolled back.
  Lesson: Green contract and test must agree before keyed spend. Evidence:
  `task-202-c2b-*`.

## F3 — Scout Cycle 3: PyJWT audit finds no hole (2026-10-31)

- All five attack shapes (unsigned opt-in, wrong-key forgery, alg confusion,
  JWKS scheme SSRF, redirect-to-metadata) already guarded at `16231abf`.
  Not a failure of method — the checklist is the reusable output. Next
  scout targets a less-audited class.

## F4 — Cycle 5 attempts 1-2: RedReport schema faults on PHP tree (2026-10-31)

- Two keyed runs died with "invalid JSON or unexpected response schema" —
  a1 in `verification_report`, a2 (verbatim retry) faster in
  `initial_report`. Systematic for the PHP-tree + 5-agent shape, not
  transient. Slimming agents 5→1 fixed it. Lesson: small trees get slim
  fan-out (cheaper + schema-reliable); 5-agent default is for large
  surfaces. Evidence: `task-501/502-c5*-error.json`.

## F5 — Scout Cycle 6: werkzeug traversal audit finds no hole (2026-10-31)

- 10-shape `safe_join` battery + 6-path end-to-end WSGI battery: all escapes
  404 at `2adaad1a`. Backslash/symlink edges are documented behavior.
  Reusable battery kept; next scout goes smaller (single-maintainer class).

## F6 — Cycle 7 attempts 1-2: true-SSRF fixtures unprovable in sandbox (2026-10-31)

- a1 (subdomain interpolation, external upstream): Red exit 2 — all SSRF
  shapes 502/timeout, Link B vuln confirmed but chain unprovable.
- a2 (self-fetch via own alias): normal check itself 502 — the target
  cannot dial its own `target-service` alias (no hairpin in isolated net).
- Lesson: in `network_mode=none`, provable SSRF = selector-injection over
  LOCAL resources (T8b). True egress-SSRF needs a cooperating in-net
  upstream, which the harness does not provide. Evidence: `task-701/702-c7*`.

## F7 — Scout Cycle 9: Flask-File-Upload audit finds no hole (2026-10-31)

- Double-closed traversal (secure_filename + safe_join); ext mismatch
  unconsumed; MIME unused; crash unreachable. Stale ≠ vulnerable.
  Battery kept for future upload targets.
