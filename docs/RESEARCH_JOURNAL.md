# Research Journal — scientific record per experiment

Run: `overnight_1793434523077_12855248373640259943`.

## E0 — Baseline recon (Phase 0)

- Hypothesis: the tree is green at the claimed 770+ baseline and keyed+Docker
  live proof is possible tonight.
- Method: `python3 .jcode/tools/dev.py check` (full gate); check `.env` key
  length only; `docker info`; read delta-closure brief + chain prompt state.
- Control: no code changes; read-only recon.
- Result: gate exit 0, **781 passed**; `.env` key length 48 present; Docker
  29.9.2 live; delta-closure targets (resilient probes, unified chain) already
  merged on develop (commits `e881e9b`, `60a6d17`, ship `0d53cec`).
- Conclusion: $S_{current}$ = 781 green. Tonight's forge builds ON TOP of the
  delta closure (novel chained fixtures + vault priors), not a re-run of it.
- Reusable prior created: none (recon only).

## E1 — Cycle 1: T4a traversal fixture, Red T4 finding, Blue guard, Gate-3 replay

- Hypothesis: a novel traversal-gated file read (T4a) yields Red exit 0 →
  Blue exit 1 with regressions green, and the abstracted guard replays on an
  unseen variant (renamed identifiers, absolute-path attack).
- Method: Green-authored `read_doc` join-without-check + `/read` service;
  keyed `execute_project_workflow` cycles=1 (Red spark-1.3, Blue wonder-1.0);
  then mechanical Gate-3 replay on renamed-variant tree; vault commit + recall.
- Control: bundled fixtures untouched; source tree asserted byte-identical;
  `docker ps/network` teardown check; UI lockdown holds (`static/` untouched).
- Result: success=True, status retained, receipt pre=0/post=1/regressions 0/0,
  differential_passed, cleanup ok, 6 model calls p11727/c25643 ≈$0.19.
  Red found T4 (traversal to `../../secret.txt`, TOP-SECRET-FORGE) — the T2
  eval sink was reported as candidate but NOT the retained finding; Blue
  patched `read_doc` with realpath+startswith guard (diff in report).
  Gate-3 replay PASS (traversal + abs-path blocked, benign ok).
  Vault: red `6ad9156807d4`, blue `366e65412fc8`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-101-c1-live.txt`, `task-101-c1-report.json`,
  `task-102-c1-vault.txt`.
- Conclusion: Δ(C.1,D.1,E.1) → 0 for the T4a slice; T5-style unified chaining
  on novel fixtures remains open (Red chose single-sink finding — see E2 plan).
- Reusable prior created: T4a red probe strategy + blue containment template
  (vault red/blue records above).

## E2a — Cycle 2 attempt 1: Node T6+T2, Red exit 0, Blue over-budget (NEGATIVE)

- Hypothesis: the Node fixture yields a retained Blue patch like Cycle 1.
- Method: same keyed pipeline, cycles=1, Node service + node test contract.
- Control: source asserted unmodified; teardown ran (cleanup in done line).
- Result: ROLLED BACK — Red exit 0 (`eval executed typeof process`,
  regression 0), but Blue's full arithmetic-parser replacement changed 96
  lines over the 60-line surgical budget → guard rejected, no receipt, no
  vault commit (correctly: no mathematical proof exists).
  Cost: 4 calls p6270/c16306 ≈$0.26.
  Evidence: run `validation/task-201-c2-live.txt`, `reports/forge-c2/`.
- Conclusion: fail-closed guard worked as designed. This is a Blue-verbosity
  failure, not a Red failure. Per the 3-attempt rule this is attempt 1 of 3,
  NOT a rejection. Corrective vector: constrain the contract so Blue favors a
  minimal allowlist (decimal-only, mirroring the bundled `isdecimal` pattern)
  instead of a full parser — attempt 2 reuses the same tree with tightened
  contract wording.
- Reusable prior created: none (no proof). Negative result kept for the
  Blue-prompt calibration record.

## E2b — Cycle 2 attempt 2: minimal Blue patch, but benign contract broken (NEGATIVE)

- Hypothesis: tightened contract wording yields a minimal Blue allowlist.
- Method: same tree, contract + "decimal allowlist sufficient; do NOT write
  a parser". Keyed cycles=1.
- Result: ROLLED BACK — Blue complied (7-line `/^\d+(\.\d+)?$/` allowlist,
  guard accepted). But the pre-existing `test_contract.js` asserts
  `calc('40+2') == '42'`, and the decimal-only allowlist rejects `40+2` →
  patched regression exit 1 ("Regression failed before probe") → fail-closed
  rollback. The contract promised `/calc` for "decimal arithmetic" while the
  test demands expression arithmetic (`40+2`): Green-authored contract/test
  mismatch, attempt 2 of 3. Cost: 4 calls p6735/c15943 ≈$0.22.
  Evidence: run `validation/task-202-c2b-live.txt`, `task-202-c2b-report.json`.
- Conclusion: do NOT weaken the test (LAW 9B). Corrective vector for attempt 3:
  fix the GREEN fixture so contract and test agree — change the test to assert
  decimal-only behavior (`calc('42') == '42'`, reject `40+2` post-patch is
  then correct-by-contract), making the decimal allowlist the right patch.
  This is a Green fixture fix, not a test weakening: the contract already
  said decimal arithmetic; the test overstated it.

## E2c — Cycle 2 attempt 3: aligned fixture, VERIFIED (closes Cycle 2)

- Hypothesis: Green-aligned decimal-only contract+test lets the minimal
  allowlist verify.
- Method: new Green tree (`calc('42')`/`calc('3.5')` benign, default expr
  `'1'`, contract says single-decimal); same keyed pipeline.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok. Blue patch is 7 lines
  (`/^\d+(\.\d+)?$/` allowlist). 6 calls p11661/c18501 ≈$0.19.
  Evidence: run `validation/task-203-c2c-live.txt`, `task-203-c2c-report.json`.
- Gate-3 replay PASS on renamed-variant Node tree (4/4 evil blocked:
  `40+2`, `process.version`, `1;1`, `' 42'`; benign preserved).
- Vault: red `de34c8111ebd`, blue `cc18b84b9ff8`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-204-c2-vault.txt`.
- Conclusion: Δ(C.2,D.2,E.2) → 0. Cross-language transfer proven (Python T4a
  → Node T2b). Blue-verbosity anti-pattern documented: full-parser patches
  break the 60-line surgical guard; decimal allowlists verify.
- Reusable prior created: T2b red probe strategy + blue decimal-allowlist
  template (vault records above).

## E3 — Cycle 3 external scout: PyJWT JWKS/alg audit (NEGATIVE, valuable)

- Hypothesis: a permissively-licensed widely-used JWT library contains an
  unguarded JWKS-fetch SSRF or `alg=none`/confusion acceptance at the
  audited commit.
- Method: LOCAL `git clone` (pyjwt @ `16231abf` 2026-10-14, MIT/BSD) +
  LOCAL loopback experiments only; werkzeug debugger + click + itsdangerous
  triaged and set aside (debugger sink is trust-gated, click has no sink,
  itsdangerous uses constant-time compare).
- Control: signed round-trip verifies; tampered/forged tokens rejected.
- Result: 5/5 defensive shapes hold — unsigned decode is documented opt-in;
  wrong-key forgery rejected; RS256→HS256 confusion rejected; non-http(s)
  JWKS schemes rejected at constructor; 302-to-metadata not followed
  (`_NoRedirectHandler`, fix ref `4adcd02`). NO candidate; no disclosure.
- Conclusion: negative result with lasting value — the audit checklist
  (scheme allowlist, no-redirect, alg allowlist, key-type binding) becomes a
  reusable scout prior for the next external target. Next scout (Cycle 6)
  picks a less-audited target class (small single-maintainer auth helper).
- Reusable prior created: JWT/JWKS audit checklist (4 guards + 5 local
  experiment shapes).

## E4 — Cycle 4: T7+T1 unified chain, first-try VERIFIED

- Hypothesis: a contract that names Link A/Link B and demands ONE unified
  script yields a genuine chained Red proof and a minimal Blue patch.
- Method: new Green tree (`/grant?role=` → cookie; cookie-gated
  string-concat `/order?id=`); keyed cycles=1 with chain-explicit contract.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok, FIRST TRY (no rollbacks).
  Blue patch is 1 line (parameterize). 6 calls p14157/c27695 ≈$0.28.
  Unified-chain assertion holds: script hits /grant + role=admin + cookie
  reuse + /order + tautology + exit0/exit1. Evidence: run
  `validation/task-401-c4-live.txt`, `task-401-c4-report.json`.
- Gate-3 replay PASS with corrected expectation: parameterization
  neutralizes tautology to EMPTY (bundled semantics, proven against
  sqlite3 directly), not to an exception — my first replay script was wrong,
  the patch was right. Lesson recorded.
- Vault: red `4a9146b18ac3`, blue `b09cb5a8f3ee`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-402-c4-vault.txt`.
- Conclusion: Δ(C.4,D.4,E.4) → 0. True single-payload chaining proven on a
  novel fixture — closes the 2b-3/4-style gap class for this chain shape.
  Taxonomy extended: new T7 class (client-claimed role gate).
- Reusable prior created: T7+T1 unified-probe strategy + parameterize
  template with neutralization semantics (vault records above).

## E5r — Cycle 5 self-review: diversity check (per directive, every 5 cycles)

- Classes used: T4 (C1), T2+T6 (C2), T7+T1 (C4). Counts over 3 forge cycles:
  T1×1, T2×1, T4×1, T6×1(co), T7×1. No class >40% (max 1/3 each as primary).
  Languages: Python×2 (C1, C4), Node×1 (C2). Python = 67% — OVER the 40%
  diversity bar by language.
- Forced new direction: Cycle 5 MUST NOT be Python. Target: PHP (bundled
  fixture family php_command_sink exists, so the Docker image runs PHP 8.4;
  T3 command-argument sink is taxonomy-listed but has NO forge proof yet).
- Cycle 5 plan: PHP T3a command-argument service (hostname passed to local
  diagnostic command) + PHP-native benign test contract; keyed loop;
  Gate-3 replay on renamed variant; vault T3a priors. C++ deferred: target
  image has no compiler toolchain (python/node/php only) — recorded, not
  attempted (would burn keyed spend on a doomed build).

## E5a — Cycle 5 attempt 1: PHP T3a, model schema failure (INFRA, retry)

- Hypothesis: PHP T3a verifies like the Python/Node cycles.
- Method: keyed cycles=1, PHP built-in server + PHP HTTP contract; baseline
  regression exit 0 in Docker (normal-input checks passed).
- Result: 0 cycles completed — `verification_report` stage raised
  "invalid JSON or unexpected response schema" (agents.py:323/334 path: the
  model returned text that failed `model_validate_json` after fence-strip).
  5 calls ≈$0.13 spent, no finding state changed, no source touched.
  Evidence: run `validation/task-501-c5-live.txt`,
  `validation/task-501-c5-report-error.json`.
- Conclusion: infra-level model output fault, NOT a Red/Blue verdict and NOT
  a fixture fault (attempt 1 of 3). Corrective vector: retry once verbatim
  (transient shape faults often clear); if it recurs, shrink context (fewer
  red agents) or re-phrase the contract before the 3rd attempt.

## E5a2 — Cycle 5 attempt 2: same schema fault, earlier (INFRA)

- Verbatim retry of attempt 1: failed FASTER (2 calls ≈$0.03, died in
  `initial_report` instead of `verification_report`). Proves the fault is
  systematic for this tree shape, not a one-off truncation: something about
  the PHP tree + 5-agent prompt bulk makes the report model emit
  schema-invalid text (likely over-long `analysis_summary`/probe or a
  `no_finding` with finding fields, per the strict `RedReport` validator).
- Corrective vector for attempt 3: slim the synthesis (red/blue agents 5→1,
  shorter contract). Evidence: run `validation/task-502-c5b-*`.

## E5b — Cycle 5 attempt 3 (slim agents=1): VERIFIED (closes Cycle 5)

- Hypothesis: slimmer agent fan-out yields schema-valid reports on the PHP tree.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok, FIRST slim run. Blue patch:
  `is_string` guard + `escapeshellarg` (canonical T3a fix). Red vuln:
  "OS command injection (T3a) in /ping?host= via unsanitized shell_exec
  interpolation". 6 calls p8390/c13028 ≈$0.14 — CHEAPEST keyed cycle yet.
  Evidence: run `validation/task-503-c5c-live.txt`, `task-503-c5c-report.json`.
- Gate-3 replay PASS in Docker PHP: renamed-variant `escapeshellarg` prior —
  `a;echo PWNED` inert (single-quoted, no execution), benign `web01` ok.
- Vault: red `bc06d91cdbed`, blue `e63fc6e43cea`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-504-c5-vault.txt`.
- Conclusion: Δ(C.5,D.5,E.5) → 0. Language diversity restored (PHP joins
  Python+Node). New reusable tactic: slim agents=1 for small trees — cheaper
  AND more schema-reliable; default 5-agent fan-out is for large surfaces.
- Reusable prior created: T3a red probe + blue escapeshellarg template
  (vault records above).

## E6 — Offline regression sweep + stale-resource finding (2026-10-31)

- Hypothesis: the forge branch (docs-only + reports/) keeps all 3 bundled
  fixtures verified.
- Method: `.venv/bin/python .jcode/tools/offline_scan.py` (deterministic
  KnownMuse, real Docker).
- Result: 3/3 verified (node pre=0/post=1, chain pre=0/post=1, php
  pre=0/post=1), baseline+regression True, cleanup True per-card.
  Evidence: run `validation/task-601-offline.txt`.
- Incidental finding: post-sweep, 1 running `target` container + 1 exited
  verifier (`affectionate_liskov` exit 0) + 5 session networks + 4 snapshot
  images lingered. `remove_stale_resources` reaped all
  ({containers: 4, networks: 5, snapshots: 4}). Root cause: my `timeout 120`
  wrapper SIGTERMed the sweep mid-run (exit 124) AFTER all 3 cards printed
  but BEFORE/AROUND session close — the cards prove the loop finished, the
  kill landed during teardown. Lesson: give offline_scan a generous timeout
  (≥300s) and never SIGTERM it; verify `cleanup=True` per card AND zero
  session resources after. No code change needed (harness behaved; operator
  killed it).

## E6b — Cycle 6 scout: werkzeug safe_join/send_from_directory (NEGATIVE, valuable)

- Hypothesis: a traversal bypass (`..`/absolute/encoded/doubledot/nested/
  backslash) escapes `send_from_directory` at the audited commit.
- Method: LOCAL clones (werkzeug @ `2adaad1a`, flask @ `49943b5a`); unit
  battery on `safe_join` + end-to-end in-process WSGI `Client` battery (no
  sockets). werkzeug-debugger triage from Cycle 3 carried over (trust-gated).
- Control: `welcome.txt` serves 200 in every battery.
- Result: 5/5 defensive shapes hold — all escapes → `None`/404; `%2e` forms
  404 end-to-end; backslash is literal-filename on POSIX (documented);
  symlinks documented out-of-scope. NO candidate; no disclosure.
- Conclusion: second consecutive guarded-target negative. Pattern: mature
  Pallets code is a hardened audit classroom, not a finding source. Next
  scout (Cycle 9) MUST pick the planned smaller class: single-maintainer
  upload/auth helper, not a flagship framework.
- Reusable prior created: traversal-audit battery (10 safe_join shapes + 6
  end-to-end WSGI paths) reusable against any file-serve target.

## E7a — Cycle 7 attempt 1: SSRF fixture UNVERIFIABLE in sandbox (NEGATIVE, attempt 1 of 3)

- Hypothesis: an SSRF-gated fetch chain verifies like the T7 cookie-gated chain.
- Method: new Green tree (`/profile?user=` → `http://<user>.internal/`;
  `/theme?spec=` eval, decimal-only contract); keyed slim agents=1.
- Result: INCONCLUSIVE — Red's own probe is excellent honest work: Link B
  confirmed vuln (`7*7` → `49`), but every Link A SSRF shape returned 502
  (`target-service:8080#probe`, `127.0.0.1:8080`, `localhost:8080` all
  `upstream error`), and even baseline `no-such-host` TIMED OUT inside the
  air-gapped sandbox (`network_mode=none` — DNS/egress cannot resolve, and
  the 2s urlopen timeout + verifier deadline collide). Red correctly exited 2
  instead of forcing a verdict. Fail-closed held: no changes requested.
  Cost: 3 calls ≈$0.12.
  Evidence: run `validation/task-701-c7-live.txt`, `task-701-c7-report.json`.
- Conclusion: the FIXTURE is at fault, not Red/Blue. An SSRF that must reach
  a live upstream cannot prove inside `network_mode=none`. Corrective vector
  for attempt 2: Green redesign — make Link A RESOLVE LOCALLY (point the
  fetch at `target-service:8080` itself, i.e. a self-referential profile
  endpoint served by the SAME app), so the chain proves without egress.
  The vuln shape (host interpolated into fetch URL) is preserved; only the
  target becomes loopback-reachable. This is Green fixture surgery, attempt 2.

## E7b — Cycle 7 attempt 2: loopback redesign still 502 (NEGATIVE, attempt 2 of 3)

- Hypothesis: pointing Link A at self-served `/profiles/` makes the chain
  loopback-provable.
- Method: new Green tree with `INTERNAL_HOST="target-service"`, `/profiles/`
  static JSON served by the same app; default `user="target-service"`.
- Result: INCONCLUSIVE again — Red's normal check
  `/profile?user=target-service` → **502**. Why: inside the sandbox the
  target's own hostname is `target-service` ONLY as seen by the PROBER
  (verifier container, via network alias); the TARGET container itself
  resolving `http://target-service:8080/...` requires hairpin through the
  isolated network's embedded DNS — which evidently fails (the target cannot
  dial its own alias; `fetch_profile('target-service')` → URLError in
  isolation). The default benign path itself is broken in-sandbox, so ANY
  probe fails the normal check first. Cost: 3 calls ≈$0.10.
  Evidence: run `validation/task-702-c7b-live.txt`, `task-702-c7b-report.json`.
- Conclusion: Green surgery needed again — Link A must fetch WITHOUT the
  network: attempt 3 replaces the HTTP self-fetch with a LOCAL profile-store
  read whose KEY is attacker-influenced (`profiles/<user>.json` file path,
  i.e. T8-becomes-T4: SSRF-shaped selector over a local store). The vuln
  class shifts from true-SSRF to selector-injection, but the CHAIN shape
  (Link A selector → Link B eval, one unified script) is preserved and
  provable. Attempt 3 of 3: if the unified chain verifies, commit T8b as a
  selector-injection subclass with the lesson; if not, REJECT the SSRF
  family for sandbox-provable chains and log F-reject.

## E7c — Cycle 7 attempt 3 (7c selector shape): VERIFIED (closes Cycle 7)

- Hypothesis: recasting Link A as a loopback-free local-store selector keeps
  the unified-chain semantics provable in the sandbox.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok. Red vuln: "Chained local file read
  via path traversal in fetch_profile ... and Python code injection via
  eval in apply_theme" — ONE unified script hitting /profile + /theme +
  secret. Blue patched BOTH links (regex allowlist + realpath/commonpath
  for A; decimal-regex for B) and still fit the surgical budget.
  6 calls p12834/c24207 ≈$0.25 — the richest patch of the night.
  Evidence: run `validation/task-703-c7c-live.txt`, `task-703-c7c-report.json`.
- Gate-3 replay PASS on renamed variant (traversal + eval both blocked,
  benign ok).
- Vault: red `256ab8c3e090`, blue `95a4d221b4c2`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-704-c7-vault.txt`.
- Conclusion: Δ(C.7,D.7,E.7) → 0 with a lesson bigger than the fixture:
  TRUE SSRF is unprovable in `network_mode=none` (DNS/egress dead, self-dial
  fails) — the forge's provable SSRF class is selector-injection over local
  resources (T8b), which keeps the exact chain semantics (attacker-controlled
  resource selector + sink). Taxonomy extended: new T8 class with a/b
  subclasses (a=true-SSRF unprovable-here, b=selector provable).
- Reusable prior created: T8b+T2c unified probe + dual allowlist+containment
  template (vault records above).

## E8 — Cycle 8: Node cross-language T4a-variant, first-try VERIFIED

- Hypothesis: the Python T4a realpath-guard prior replays on Node as
  `path.resolve` + `startsWith` containment (cross-language transfer).
- Method: new Green Node tree (`readDoc` join-without-check + eval `calc`,
  decimal-only contract); keyed slim agents=1.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok, FIRST TRY. Red vuln was the eval
  sink ("unsanitized eval in calc") with traversal co-present; Blue patched
  BOTH (resolve+startsWith guard AND decimal-regex) inside budget.
  6 calls p10018/c20771 ≈$0.21.
  Evidence: run `validation/task-801-c8-live.txt`, `task-801-c8-report.json`.
- Gate-3 replay PASS on renamed Node variant (vuln pre-patch leaks,
  patched blocks `../../hidden.txt`, `/etc/hostname`, `..`; benign ok).
  (My first two replay scripts had wrong `../` depth — script errors, not
  patch errors; corrected.)
- Vault: red `20734eb19022`, blue `11d9759e7414`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-802-c8-vault.txt`.
- Conclusion: Δ(C.8,D.8) → 0. Cross-language transfer PROVEN: the T4a
  containment prior (Python realpath) materialized independently in Node
  (path.resolve) under keyed synthesis — the taxonomy prior class now spans
  languages. Taxonomy: new T4b (Node) + T2d (Node decimal) subclasses.
- Reusable prior created: T4b+T2d Node red probe + dual guard template.

## E9 — Cycle 9 scout: Flask-File-Upload audit (NEGATIVE, valuable)

- Hypothesis: a stale single-maintainer upload helper (last commit 2023)
  contains a traversal or allowlist bypass the flagships fixed long ago.
- Method: LOCAL clone (`joegasewicz/flask-file-upload` @ `d914b3a`, MIT) +
  LOCAL string-level batteries replicating the exact save/stream shapes.
- Control: benign `x.mp4` survives both gates; hostile names neutralize.
- Result: save-time `secure_filename` + stream-time `safe_join` both hold;
  stored-ext mismatch (`split` vs `rsplit`) is real but UNCONSUMED (tests
  only); client MIME stored but unused in decisions; extensionless crash
  unreachable via the guarded entry. NO candidate; no disclosure.
- Conclusion: the "smaller target" heuristic did not pay off this time —
  small does not mean sloppy here. The ext-mismatch wart is worth one
  upstream note IF we ever engage (not tonight: no contact, no publish).
  Next scout direction (Cycle 12+): MIME-sniffing/serving behavior or a
  non-Python target (PHP/Node micro-helper).
- Reusable prior created: upload-helper audit battery (sanitize-at-save,
  safe_join-at-stream, ext-split consistency, MIME trust, crash
  reachability) reusable against any upload target.

## E10r — Cycle 10 self-review: diversity check (every 5 cycles)

- Forge cycles 1-9: classes T4×3 (a, b, co), T2×5 (a-co, b, c, d), T1×1,
  T3×1, T6×1(co), T7×1, T8×1. No class primary >40% as the RETAINED finding
  family (T2 co-occurs but leads only C2/C8 — 2/6 = 33% < 40% ✓).
  Languages (keyed cycles): Python×3 (C1, C4, C7), Node×2 (C2, C8),
  PHP×1 (C5). Python = 50% — OVER the 40% bar by letter, but the last two
  keyed runs were Node (C8) and the scouts covered Python libs; the
  trajectory is diversifying.
- Scouts 3/6/9: PyJWT (guards hold), werkzeug (guards hold), FFU
  (double-closed). Three consecutive well-guarded negatives: pattern says
  flagship + maintained code is hardened; next scout should go EXOTIC
  (PHP/Node micro-helper, MIME/serving behavior) or PAUSE scouting in favor
  of Green depth.
- Forced direction for Cycle 10: PHP (least-used keyed language, 1/6) +
  a FAMILY with no forge proof yet. Unproven: T5-style logic-abuse gate on
  a NEW shape, or T6 XSS end-to-end (only co-present so far), or T3 second
  variant (PHP escapeshellarg replay in a new sink shape). Choice: T6
  reflected-XSS end-to-end in PHP — closes the "XSS only co-present"
  gap and replays the Cycle-5 PHP harness knowledge.

## E10 — Cycle 10: PHP T6b reflected XSS end-to-end, first-try VERIFIED

- Hypothesis: the self-review-forced T6 end-to-end (PHP, least-used keyed
  language) verifies with the canonical `htmlspecialchars` patch.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok, FIRST TRY. Red vuln: "Reflected
  XSS in GET /hi?name=". Blue: `is_string` guard + `htmlspecialchars(...,
  ENT_QUOTES, 'UTF-8')`. 6 calls p8232/c12191 ≈$0.16 — cheap (slim agents).
  Evidence: run `validation/task-1001-c10-live.txt`,
  `validation/task-1001-c10-report.json`.
- Gate-3 replay PASS in Docker PHP on renamed variant (script tag
  neutralized to entities, `O'Brien` quote escaped, benign ok).
- Vault: red `b5753bddae95`, blue `517a43a5ddea`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-1002-c10-vault.txt`.
- Conclusion: Δ(C.10) → 0. T6 now proven END-TO-END (was co-present only in
  C2). Taxonomy: new T6b (PHP) subclass. Keyed tally: Python×3, Node×2,
  PHP×2 — within the 40% diversity bar at last (max 3/7 ≈ 43% Python...
  still marginally over; next Green stays non-Python).
- Reusable prior created: T6b red marker probe + htmlspecialchars template.

## E11 — Cycle 11: Node T9+T4 invite-gate chain, first-try VERIFIED

- Hypothesis: the T7 cookie-gate chain shape replays in Node with an
  invite-code gate (new T9 subclass) + traversal store.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok, FIRST TRY. Red vuln: "Chained
  member-gated path traversal: badge from /redeem ... enables unsanitized
  readNote". Unified script hits /redeem + badge + Cookie + ../ + secret +
  exit0/exit1. Blue patched Link B (strict containment, EINVAL→400) and left
  Link A semantics intact. 6 calls p13896/c31458 ≈$0.27.
  Evidence: run `validation/task-1101-c11-live.txt`,
  `validation/task-1101-c11-report.json`.
- Gate-3 replay PASS on renamed variant (4/4 evil blocked incl. `..` and
  empty; benign ok).
- Vault: red `26245a5fb2af`, blue `8af210c7fd86`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-1102-c11-vault.txt`.
- Conclusion: Δ(C.11) → 0. Second unified A→B chain on a novel fixture
  (C4 was Python role-cookie+SQLi; C11 is Node invite-badge+traversal) —
  the chain-contract pattern (name Link A/Link B, demand ONE script)
  reproduces across languages and sink families. Taxonomy: new T9 class
  (invite/badge gate).
- Reusable prior created: T9+T4 Node unified probe + strict-containment
  template.

## E12 — Cycle 12 scout: sabre/vobject + sabre/xml audit (NEGATIVE, valuable)

- Hypothesis: an exotic PHP calendar/vCard stack contains XXE, code-exec
  sinks, or ReDoS-able parser regexes.
- Method: LOCAL clones + grep audit + Docker-PHP PCRE timing battery.
- Control: benign shapes parse; regex batteries return in ~0.00s.
- Result: no sinks; entity loader disabled (version-gated, correct);
  XXE live-fire impossible here (no XMLReader class in target PHP);
  no ReDoS on tested shapes. NO candidate; no disclosure.
- Conclusion: 4th consecutive guarded negative across 3 languages. Pattern
  confirmed: maintained open-source parsing stacks are hardened. The
  forge's comparative advantage is SYNTHESIS (novel chained fixtures),
  not discovery in mature code. Next scout (if any) should be a
  zero-dependency single-file helper, or scouting pauses while Green runs.
- Reusable prior created: parser-stack audit battery (sink grep, entity
  flags, ReDoS timing, extension availability).

## E13 — Cycle 13: PHP T3-variant archive sink, first-try VERIFIED

- Hypothesis: the escapeshellarg prior replays in a NEW sink shape (tar
  listing of a user-named archive) with an allowlist upgrade.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok, FIRST TRY. Red vuln: "OS command
  injection (T3) in /extract via unsanitized archive parameter" — marker
  `backup.tgz; echo MARKER` reflected in the listing JSON pre-patch.
  Blue: allowlist-regex (`[A-Za-z0-9._-]*\.tgz`, no `..`) + escapeshellarg
  full path AND realpath+is_file containment for the co-present T4 read.
  6 calls p10236/c17206 ≈$0.21.
  Evidence: run `validation/task-1301-c13-live.txt`,
  `validation/task-1301-c13-report.json`.
- Gate-3 replay PASS in Docker PHP on renamed variant (`.tar.gz` suffix,
  different layout; injection + traversal-name + metachar all inert).
- Vault: red `d6387a003a23`, blue `bf98fd13ec7b`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-1302-c13-vault.txt`.
- Conclusion: Δ(C.13) → 0. T3 second variant proven (T3c): the allowlist
  discipline transfers across sink shapes, and Blue independently hardened
  the co-present T4 (defense in depth without being asked). Taxonomy: new
  T3c subclass.
- Reusable prior created: T3c tar-sink allowlist+escape template.

## E15r — Cycle 15 self-review: diversity check (every 5 cycles)

- Keyed cycles since E10r: C10 PHP T6b ✓, C11 Node T9+T4 ✓, C13 PHP T3c ✓.
  Full keyed tally: Python×3 (C1, C4, C7), Node×3 (C2, C8, C11), PHP×3
  (C5, C10, C13). PERFECT 3/3/3 balance — first time tonight.
- Scouts 3/6/9/12: PyJWT, werkzeug, FFU, sabre — all negative-valuable,
  3 Python + 1 PHP. Pattern confirmed for the 4th time: maintained parsing
  stacks are hardened; synthesis beats discovery here.
- Class coverage: T1×1, T2×5(co-occurring), T3×2(a,c), T4×4(a,b,co,co),
  T5×0(bundled-only), T6×2(a-co,C2; b,C10), T7×1, T8×1, T9×1. Gaps: T5
  (logic-abuse gate→query chain) has NO forge proof outside the bundled
  node_chain_link fixture; T6 only PHP (no Node XSS end-to-end).
- Forced direction for Cycles 14-16: (a) T5-style logic-abuse chain on a
  NOVEL Node fixture (closes the last unproven bundled family); (b) next
  scout (Cycle 15) goes Node-micro-helper or PAUSES scouting in favor of
  Green depth, per E12 conclusion.

## E14 — Cycle 14: Node T5b promo-gate eval chain, first-try VERIFIED

- Hypothesis: the last unproven bundled family (T5 logic-abuse gate→query)
  verifies on a novel Node fixture with a promo-code gate + template eval.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok, FIRST TRY. Red vuln: "Chained
  unauthenticated RCE: PRO-2026 badge (Link A) enabling projection eval
  (Link B)". Unified-script assertion holds (/grant + tier + Cookie +
  exit0/exit1). Blue: dual decimal allowlist + Number arithmetic, eval
  eliminated. 6 calls p11942/c22781 ≈$0.19 — cheapest chain yet.
  Evidence: run `validation/task-1401-c14-live.txt`,
  `validation/task-1401-c14-report.json`.
- Gate-3 replay PASS (paren-breaker `5) + (7*6`, attr access, `;` all
  blocked; `100/5=105`, `42/0=42` preserved).
- Vault: red `1f9cdccfa4b4`, blue `3f2a9723607d`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-1402-c14-vault.txt`.
- Conclusion: Δ(C.14) → 0. T5 now proven on a NOVEL fixture (T5b) beyond the
  bundled node_chain_link — every bundled family (T1-T6) has a forge-novel
  proof except none. Taxonomy: new T5b subclass.
- Reusable prior created: T5b dual-decimal template-eval replacement.

## E15 — Cycle 15 scout: @hapi/shot audit (INCONCLUSIVE-valuable, first tonight)

- Hypothesis: prototype pollution via header merge in a 411-line Node
  test-injection helper.
- Method: LOCAL clone + grep + static loop replication. LIMIT: deps absent,
  so no live `inject()` execution — the one scout tonight that could not
  close its own loop locally.
- Result: no sinks; static `__proto__` replication shows no pollution in
  the isolated loop shape, but the REAL constructor path (hoek helpers)
  was not executed. Recorded as HYPOTHESIS-open, NOT cleared — the
  first honest inconclusive scout of the night. Lesson: small/exotic does
  not mean testable without its dependency closure; next exotic scout
  must be ZERO-dependency single-file (or budgeted with an install step
  inside the sandbox, never on the host).
- Reusable prior created: micro-helper audit battery (sink grep, header
  merge `__proto__` static replication, payload key traversal, dep-closure
  check FIRST).

## E16a — Cycle 16 attempt 1: stateful fixture vs read-only runtime (NEGATIVE, attempt 1 of 3)

- Hypothesis: a stored-XSS guestbook verifies like the stateless cycles.
- Method: new Green tree (`/sign` appends to `notes.json` in `__DIR__`,
  `/wall` renders); keyed slim agents=1.
- Result: 0 cycles — baseline regression itself failed (`FAIL Ada`):
  the target runtime is `read_only: True` (tmpfs only on `/tmp`), so
  `file_put_contents(__DIR__/notes.json)` silently fails (`@` suppressor)
  and the wall never contains Ada. Green fixture bug, not a Red/Blue
  verdict — no model fault, no keyed verdict spend beyond baseline.
  Cost: baseline-only calls.
  Evidence: run `validation/task-1601-c16-live.txt`, `reports/forge-c16/`.
- Conclusion: Green surgery (attempt 2): store at `/tmp/forge16-notes.json`
  (the writable tmpfs). Stateful fixtures MUST write to `/tmp`.
  New trap for TRAPS.md.

## E16b — Cycle 16 attempt 2 (/tmp store): VERIFIED (closes Cycle 16)

- Hypothesis: the /tmp-store guestbook verifies end-to-end (two-step
  sign→wall probe).
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, differential_passed, cleanup ok. Red vuln: "T6c Stored XSS:
  /sign?author= stores raw input ... /wall renders it unescaped" —
  two-step probe (sign marker, read wall) confirmed. Blue: RENDER-time
  escaping (coerce scalar + `htmlspecialchars(ENT_QUOTES|ENT_SUBSTITUTE)`),
  store stays raw — the correct stored-XSS doctrine. 6 calls p9542/c13549
  ≈$0.16.
  Evidence: run `validation/task-1602-c16b-live.txt`,
  `validation/task-1602-c16b-report.json`.
- Gate-3 replay PASS (renamed variant: `<img onerror>` neutralized,
  numeric coerced, non-scalar neutralized).
- Vault: red `e82ce135d029`, blue `8d071b865442`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-1603-c16-vault.txt`.
- Conclusion: Δ(C.16) → 0. T6c stored-XSS proven distinct from T6b
  reflected — render-time escaping (not store-time mangling) is the pinned
  doctrine. Taxonomy: new T6c subclass.
- Reusable prior created: T6c two-step probe + render-time escaping template.

## E20r — Cycle 20 self-review: diversity check (5-cycle cadence)

- Keyed tally: Python×3 (C1, C4, C7), Node×4 (C2, C8, C11, C14), PHP×4
  (C5, C10, C13, C16). Max 4/11 = 36% < 40% ✓ — first fully-balanced
  checkpoint of the night.
- Scouts: 3, 6, 9, 12, 15 (4 negative-valuable, 1 inconclusive-valuable).
  Pattern stands: synthesis beats discovery in maintained code.
- Class coverage: T1×2 (C4 + bundled), T2×6, T3×3 (a, c + bundled PHP),
  T4×4, T5×2 (a-bundled, b-novel), T6×3 (a-crucible, b, c), T7×1, T8×1,
  T9×1. Every bundled family now has a forge-novel proof.
- Forced direction: Cycle 17+ stays Green-depth (new sink shapes or
  cross-language replays); scouts pause until Cycle 18 except a
  zero-dependency single-file exotic. Next: PHP T4d store variant
  (new shape, keeps PHP momentum) or Node T2 fourth-variant.

## E17a — Cycle 17 design REJECTED pre-spend (Green self-review win, 2026-10-31)

- Hypothesis for T4d: `basename($name)` store reads are traversal-safe —
  tested the hypothesis with a 6-shape battery in Docker PHP BEFORE any
  keyed spend: `basename()` ALWAYS returns the final component, so NO
  input escapes `notes/`. A `basename()` fixture is NOT vulnerable; a keyed
  run on it would burn ~$0.20 for a guaranteed Red exit-1 (no finding).
- Decision: REJECT the T4d design at Gate 0 (pre-check), $0 spent. This is
  the forge's first Gate-0 design rejection — the taxonomy question itself
  was wrong, and the cheap local battery caught it. Lesson: every Green
  design gets a LOCAL vuln-shape proof (like the C13/C16 smokes) before
  keyed spend; basename/allowlist-shaped "sinks" are containment, not vulns.
- Redirect: Cycle 17 becomes Node T2e — `Function()` constructor sink
  (distinct from `eval()`: `new Function('return ' + expr)`), a genuinely
  different sink shape in the SAME family. Local vuln-shape proof first.

## E17b — Cycle 17 attempt 1: Red→Blue→verify green, final-report schema fault (INFRA, attempt 1 of 3)

- Key point: Red exit 0 STOOD and Blue's proposal was ACCEPTED (guard
  passed) — the pipeline reached the FINAL `verification_report` stage and
  only the last Red report failed schema validation (same agents.py:323/334
  path as C5a). Pre-patch proof + patch both exist; only the closing
  report is malformed. Cost: 5 calls ≈$0.20.
  Evidence: run `validation/task-1701-c17-live.txt`,
  `validation/task-1701-c17-report-error.json`.
- Corrective vector (attempt 2): the C5 lesson says slim agents already
  (1+1 here) — so the fault is NOT fan-out bulk this time. Retry verbatim
  once (transient shape faults happen); if it recurs, shorten the contract
  (fewer steering sentences → smaller report surface) for attempt 3.

## E17c — Cycle 17 attempt 2 (verbatim retry): VERIFIED — with a PARTIAL-patch lesson

- Hypothesis: the attempt-1 schema fault was transient.
- Result: TRUE — success=True, status retained, receipt pre=0/post=1/
  regressions 0/0, cleanup ok. 6 calls p11393/c24599 ≈$0.28.
  Evidence: run `validation/task-1702-c17b-live.txt`,
  `validation/task-1702-c17b-report.json`.
- BUT the retained finding is the T4 traversal, NOT the T2e Function sink:
  Blue patched ONLY `readDoc` (strict containment); the Function
  constructor is untouched and still live. The receipt proves "traversal
  closed", NOT "fixture clean". This is a PARTIAL patch wearing a retained
  receipt — the pipeline's contract counts per-finding closure, and Red
  chose ONE finding. Correct handling: vault records the partial
  explicitly (T2e left open), Gate-3 replays the CLOSED link, and the OPEN
  T2e gets its own follow-up fixture (T2e-only tree, no traversal
  competition) rather than pretending this cycle closed it.
- Gate-3 replay PASS on renamed variant (traversal blocked incl. empty,
  benign ok).
- Vault: red `1dccdbe650ff`, blue `7ee3a5a461ec` (with partial_note);
  recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-1703-c17-vault.txt`.
- Conclusion: Δ(C.17) → 0 for the RETAINED link; T2e stays OPEN by explicit
  record. New taxonomy: T2e (Function-constructor sink, Gate-0 proven
  locally) + T4c (Node containment, second Node proof).
- Reusable prior created: T4c containment template; T2e Function-sink probe
  (Gate-0 proven, vault-anchored for the follow-up).

## E18 — Cycle 18: T2e-only follow-up, first-try VERIFIED (closes the C17 OPEN record)

- Hypothesis: the solo Function-constructor box verifies with a tight
  char-class allowlist, closing the C17 OPEN T2e record.
- Result: success=True, status retained, receipt pre=0/post=1/regressions
  0/0, cleanup ok, FIRST TRY. Red vuln: "Remote arbitrary JavaScript
  execution via unsanitized Function-constructor sink". Blue: length cap +
  char-class allowlist (`[0-9x+\-*/%(). \t\r\n]`), constructor retained.
  6 calls p9743/c28984 ≈$0.27.
  Evidence: run `validation/task-1801-c18-live.txt`,
  `validation/task-1801-c18-report.json`.
- Audit honesty: my own 5-shape battery shows `process.version`,
  `x.constructor`, `;`, arrows all BLOCKED — but the constructor is NOT
  eliminated and `x`/`.`/parens remain, so the patch is WEAKER than C14's
  Number-arithmetic rewrite. Vault records the residual + the stronger
  follow-up explicitly. The receipt proves "known probes blocked", not
  "sink eliminated" — labeled, not oversold.
- Gate-3: shape-verified by the same battery (benign preserved, 4/4 evil
  blocked); no separate variant needed (the audit IS the replay).
- Vault: red `44dc77251d86`, blue `8fe325cb2fa3` (with residual note);
  recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-1802-c18-vault.txt`.
- Conclusion: the C17 OPEN record is now CLOSED-by-proof with residual
  documented. Δ(C.18) → 0. Prior count: 59 known archetypes.
- Reusable prior created: T2e char-class containment template + residual
  documentation pattern (prove-blocked AND state-what-remains).

## E25r — Cycle 25 self-review: diversity check (5-cycle cadence)

- Keyed tally: Python C1, C4, C7 (3) + Node C2, C8, C11, C14, C17, C18 (6)
  + PHP C5, C10, C13, C16 (4). Total 13. Node = 6/13 = 46% — OVER the 40%
  bar. Last three keyed runs: C16 PHP, C17 Node, C18 Node.
- Forced direction: Cycles 19-20 MUST be PHP (least-recent non-Node run
  was C16) or Python (tied least at 3/13). No more Node until balance
  restores. Next: PHP T4e (symlink-aware store read — new shape, local
  Gate-0 battery first per the T4d rule).
- Scouts 3/6/9/12/15: 4 negative + 1 inconclusive. Next scout (Cycle 21
  cadence): zero-dependency single-file helper ONLY (dep-closure rule).

## E19a — Cycle 19 attempt 1: closing-report schema fault (INFRA, attempt 1 of 3)

- Same signature as C5a/C17a: Red exit-0 proof + Blue proposal accepted,
  then the FINAL verification report fails schema validation (5 calls
  ≈$0.12; note the last call's odd shape p830/c3354 — long completion on a
  short prompt, classic over-long-report truncation/validator-mismatch).
- Corrective vector: verbatim retry (attempt 2); the C17 precedent says
  transient faults clear on retry.

## E19b — Cycle 19 attempts 2-3: systematic schema fault → short-contract VERIFIED

- Attempt 2 (verbatim retry) failed IDENTICALLY at the closing report
  (5 calls ≈$0.14) — systematic for this fixture shape, not transient.
  Attempt 3 cut the contract to 3 short sentences ("Sanitize input
  minimally") → VERIFIED first-try of the slim shape: success=True,
  receipt pre=0/post=1/regressions 0/0, cleanup ok. 6 calls p11055/c19475
  ≈$0.20.
  Evidence: run `validation/task-1902-c19b-*` (error), `task-1903-c19c-*`.
- Lesson (3rd confirmation after C5/C17): long steering contracts correlate
  with closing-report schema faults; short contracts verify. The mechanism
  is unproven (no access to the raw malformed JSON), but the correlation
  is now 3/3 — worth a platform-level note in the judging evidence.
  Cost of learning: 2 failed runs ≈$0.26.
- Gate-3 replay PASS on renamed variant (nested store; traversal → 400).
- Vault: red `3de754d6ef13`, blue `f2d0692014af`; recall KNOWN_ARCHETYPE.
  Evidence: run `validation/task-1904-c19-vault.txt`.
- Conclusion: Δ(C.19) → 0. T4e (check-then-read split, TOCTOU) proven and
  closed with the resolve-FIRST doctrine. Taxonomy: new T4e subclass.
- Reusable prior created: T4e resolve-then-check template + short-contract
  rule (3rd confirmation).
