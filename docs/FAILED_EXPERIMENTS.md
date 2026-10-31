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
