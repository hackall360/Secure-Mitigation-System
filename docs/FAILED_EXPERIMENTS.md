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

## F14 — C46 parked OPEN: T1i LIKE-wildcard 5x Blue-schema cluster (2026-10-31, 5 attempts)

- Fixture: Python LIKE-pattern interpolation + cross-user search, stateless.
  Gate-0 local PASS (benign ali; hostile % leaks all rows).
- All 5 attempts: Red bottled exit-0 proofs on search.py; Blue phase died
  with "invalid JSON or unexpected response schema" at the identical point.
  Worst Blue-flake cluster of the night (C40: 3x; C45: 1x; C46: 5x).
- Hypothesis (UNPROVEN, needs controlled test): the `%` wildcard + nested
  quote juggling (`'" + prefix + "%'"`) in the fixture context makes Blue's
  JSON payload unparseable — either via model-side escaping failure or via
  a `%`-format collision in the prompt chain. Controlled test for later:
  same fixture but pattern built as `prefix + chr(37)` (no literal % in
  source) vs literal %; if chr(37) clears, the hypothesis confirms and the
  fix is a fixture-authorship rule (no raw % in T1i fixtures).
- Parked OPEN (hotspot, stop-line at 5 per C41 discipline): Red signal 5/5
  exit-0, zero Blue outputs. Revisit with the chr(37) variant.
- Traps honored: per-attempt report snapshots saved (c46a-e); ast-parse
  drivers; no fixture thrash mid-cluster (contract kept byte-identical).

## F14b — C46 hypothesis test result (2026-10-31): CONFIRMED

- See E47. Refine F14: the trigger is nested-quote SHAPES in sink lines
  the model must reproduce (`'" + ... + "%'"`), not `%` per se (C47
  contains literal % and cleared). Token-exhaustion (C47a) is a second,
  rarer failure mode on the same shape — budget pressure, not schema.
- Standing rule: least-nested quoting in fixtures; snapshot per-attempt
  reports; stop-line 5.

## F15 — C48 root cause PROVEN: Red second-pass hallucination (2026-10-31, 6 attempts)

- Captured via new PURPLEBOX_LOG_RAW_RESPONSES debug dump (env-gated,
  zero-cost when unset): the faulting role is
  `project_red_verification_report`, NOT Blue. Red returned
  `outcome: no_finding` WITH a full `verification_script_python` ->
  `ValueError: A no-finding report must not include finding fields.`
  Evidence: validation/task-4806-c48f-redtruefault.txt.
- Worse than a schema slip: Red HALLUCINATED a hardened fixture
  ("next_url requires leading single /, rejects //, backslash, control
  chars and urlsplit scheme/netloc falling back to /login") — NONE of
  which exists in the supplied source — and reviewed THAT instead.
  It contradicted its own pass-1 exit-0 proof ("bottled a proof" x6).
- Mechanism hypothesis: canonical fixture shapes (login?next= redirect,
  LIKE-search) pattern-match training-dominant SECURE versions; the
  second-pass reviewer grades the remembered-secure variant. C47
  (rare ESCAPE shape) stayed grounded and cleared. So F14's
  nested-quote rule is DEMOTED to coincidence: C47's clear is better
  explained by shape-distinctiveness than by quoting.
- Mitigations (Green-side, no harness change): shape-distinctive
  fixtures (rare sink spellings, non-canonical route+param names);
  candidacy: response-splitting (stdlib emits raw CRLF, proven) as a
  rarer-in-training sibling of open-redirect. Parked at stop-line 6.
- Standing correction: Blue-schema clusters (C40 3x, C46 5x, C48 5x)
  were NEVER proven Blue-side; at least C48 is proven RED-side. All
  "transient Blue flake" attributions before this capture are
  SUSPECT — reclassify as unattributed model flake unless captured.

## F16 — C53 attempts 1-3: no-subprocess-in-target trap (2026-10-31)

- a1: contract assert bug (`split()[1]` IndexError on unexpected body).
  Trap: keep contract asserts total (startswith/endswith, never index).
- a2: `convert failed` — imgconv lost exec bit in snapshot. Fixed with
  chmod-after-copy in app.py. Trap: never rely on snapshot exec bits.
- a3: `convert failed` STILL with chmod fix — exec inside the target
  sandbox is unreliable (unidentified; possibly noexec mount or user
  policy). STOPPED debugging the sandbox; reshaped the sink to
  argv-only (no subprocess in target), write primitive kept in Gate-0
  evidence only. Attempt 4: VERIFIED.
- Standing rule: fixtures must not exec inside the target service.
  Gate-0 (local, root) proves the write primitive; the keyed loop
  proves the split. Split the proof across the trust boundary.

## F17 — C54v2: benign-executability failure (2026-10-31, 1 attempt)

- v2 drew a clean `no_findings` (success=True, zero cycles): Red found
  nothing because the benign `import("chart")` cannot execute in any
  browser (bare specifier without import maps). A fixture whose benign
  path is broken reads as a broken feature, not a vuln.
- v3 fixed it with a real served `/static/chart.js` + default to the
  full path: VERIFIED first-try. Standing rule: Gate-0 must prove the
  BENIGN path end-to-end in its real consumer, not just assert on
  response strings. (The string assert passed; executability failed.)

## F18 — Grounding demotion (2026-10-31, Cycle 59)

- C59 ran WITH the grounding quote and stalled identically (captured);
  the retry (same grounding) cleared. Combined with C55 (grounded
  stall then grounded clear): grounding is PRESENT in 2 stalls and 3
  clears. It is at best a weak signal, not the decisive factor.
- Demoted from RULE back to boilerplate. The decisive factor remains
  unidentified (streak-break is a description, not a mechanism).
  Standing practice: keep grounding (cheap), keep the debug var armed
  (proven 5x), retry stalls once before reshaping, reshape on
  identical-repeat, stop-line 5.
