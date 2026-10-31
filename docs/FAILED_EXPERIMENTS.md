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

## F8 — Cycle 17 T4d design rejected at Gate 0 (2026-10-31)

- `basename($name)`-gated reads cannot traverse (6-shape Docker-PHP
  battery: always final component). NOT a vuln — keyed run would have been
  a guaranteed no-finding. First Gate-0 rejection; $0 spent. Rule pinned:
  LOCAL vuln-shape proof before EVERY keyed run.

## F9 — Cycle 19 attempts 1-2: closing-report schema faults, short contract wins (2026-10-31)

- Identical failure twice (closing `verification_report` schema-invalid)
  on the long-steering contract; 3-sentence contract verified. 3rd
  confirmation of the short-contract rule (C5, C17, C19). ≈$0.26 tuition.

## F10 — Cycle 23 attempt 1: transient closing-report fault (2026-10-31)

- Short contract did NOT immunize (already 2 sentences). Verbatim retry
  verified — transient, not systematic. Short contracts reduce frequency;
  only retries clear transients. ≈$0.12 tuition. Evidence: `task-2301-*`.

## F11 — Cycle 24 T2f Template design rejected at Gate 0 (2026-10-31)

- `string.Template.substitute` does not evaluate `${...}` — inert by
  design, no signal, no vuln. Rule: no evaluation = no injection sink.
  $0 spent. Gate-0 battery habit: 2 runs saved.

## F12 — Cycle 30: source-import probe dodges the gate link (PARTIAL, lesson)

- Red proved the T1e SINK via direct import, never touching `/claim` —
  the T9b PIN-gate link is unproven (not bypassed: unused). Chain proofs
  MUST be HTTP-level (Set-Cookie→Cookie round-trip) or gates are
  untestable. C4/C11 did HTTP; C30 is the counterexample. T1e closed,
  T9b-link open by record.

## F11 — C40 attempts 1-4: transient cluster + contract-detail lesson (2026-10-31)

- Attempts 1-3: Red exit-0 bottled each time; Blue-phase schema faults
  killed the cycle (strict extra=forbid sampling flake). Attempt 4:
  simplified contract → Red degraded (`not_confirmed`, no changes).
  Attempt 5 with the ORIGINAL contract → VERIFIED.
- Lesson (valuable): contract detail guides RED's proof structure.
  Simplifying the contract to dodge a BLUE-side flake degrades the RED
  side. Revert, don't thrash. Worst flake cluster yet (4 dead attempts)
  but bounded spend (~$1.2 total) and no fixture rewrite needed.

## F12 — C41 parked OPEN: T5c object-injection hotspot (2026-10-31, 9 attempts)

- Fixture: PHP unsigned serialized-Profile token (/issue oracle) + unserialize
  in /hello + __destruct echo gadget. Gate-0 Docker PASS (benign + forged
  HACKED both demonstrated).
- Attempt ledger: a1 inconclusive / a2 RED-EXIT-0 bottled (Blue fault after) /
  a3 RED-EXIT-0 + Blue-schema / a4 post-probe exit 2 ROLLBACK / a5 RED-EXIT-0
  + Blue-schema / a6 post-probe exit 2 ROLLBACK / a7 inconclusive (fixture v2:
  200-always /hello) / a8 over-budget ROLLBACK (HMAC rewrite) / a9 inconclusive.
- Root causes (fixture-design, GREEN side): (1) /hello returned HTTP 400 for
  bad tokens; naive probes using file_get_contents get FALSE on non-2xx and
  the probe errors to exit 2 -> rollback. Fixed in v2 (200-always, body-only
  discrimination). (2) Gadget echo fires on EVERY response incl. benign
  /issue, muddying probe discrimination. (3) Syntax slip in Blue-hint edit
  cost one attempt (quote escaping; always ast.parse driver edits).
- Parked OPEN (hotspot, not failure): Red signal is STRONG (4x exit-0 bottled,
  correct finding both links). Blue side needs either a coordinator-side
  probe-status fix or a fixture where blocked-vs-broken is a clean body
  token. REVISIT with: gadget gated behind a verify flag, or /hello returning
  distinct bodies for forged-vs-unsigned, or waiter probe template.
- Traps added: snapshot per-attempt report.json (attempt 5's rolled-back
  context was overwritten by attempt 6); ast-parse driver edits before spend.

## F13 — C42 parked OPEN: T6d proto-pollution harness-incompatible (2026-10-31, 2 attempts)

- Fixture: Node unguarded recursive merge (Link A) + `isAdmin` reading
  `{}.elevated` (Link B, prototype read). Gate-0 local PASS: hostile merge
  sets `({}).polluted === "YES"`; fresh-session `isAdmin` returns true.
- Attempt 1: baseline regression failed — `test_contract.js` hardcoded
  127.0.0.1; sandbox serves at `target-service:8080`. Trap: Node HTTP
  fixtures MUST use target-service-first/fallback hosts in contracts
  (Red probes already know; the FIXTURE contract must too).
- Attempt 2 (contract fixed, regression exit 0 via target-service):
  "cumulative snapshot failed the original regression". Root cause:
  PROTOTYPE POLLUTION IS PROCESS-GLOBAL. Any hostile probe permanently
  elevates the server process, so benign-after-hostile ordering breaks
  differential gates by design. Not a model failure — a FIXTURE-PHYSICS
  failure: global-state vulns are harness-incompatible with pre/post
  differential verification in one long-lived server process.
- Parked OPEN (hotspot): mechanism REAL (Gate-0 proven), needs either a
  per-request-fresh server (spawn per connection — unrealistic), a
  pollution-scoped read (kills the vuln), or a harness mode with server
  restart between probe and regression. REVISIT only with harness support.
- Cost: 2 attempts (~$0.3). Stopped early per stop-line discipline (C41
  lesson: cap R&D on resistant fixtures).
