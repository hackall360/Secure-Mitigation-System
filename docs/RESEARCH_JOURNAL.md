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
