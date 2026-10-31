# Vulnerability Taxonomy (seed v0 — refined every forge cycle)

Machine-readable companion: `docs/vuln_taxonomy.json` (same classes, same ids).
These entries seed Green/Red/Blue prompt grounding. Each cycle must add a
subclass, refine a subclass with evidence, or prove a cross-language variant.

## T1 SQL string-concat sink (CWE-89)

- Subclass T1a: Python `sqlite3` f-string/`+` WHERE clause.
- Taint: HTTP query param → raw string → `db.execute("... " + raw)`.
- Red shape: `id=101` benign vs `id=101 OR 1=1`-family tautology; expect row-count change.
- Blue pattern: parameterize (`?` placeholder); never quote-wrap raw input.
- Priors: none yet.

## T2 Dynamic-expression eval sink (CWE-95)

- Subclass T2a: Python `eval(raw, {"__builtins__": {}}, {})` on query param.
- Taint: HTTP query param → `eval`.
- Red shape: arithmetic probe (`7*6` → `42`) proves code execution boundary.
- Blue pattern: strict allowlist (`isdecimal` → `int(raw)`); reject otherwise.
- Priors: none yet.

## T3 OS-command argument sink (CWE-78)

- Subclass T3a: PHP host argument into local diagnostic command.
- Taint: CLI/request arg → shell string → command run.
- Red shape: `;`/`&&`/backtick metacharacter reflection in command output.
- Blue pattern: exact allowlist of hosts / `escapeshellarg`; reject metachars.
- Priors: none yet.
- Subclass T3c (proven forge Cycle 13, 2026-10-31, PHP): archive name into
  `tar tzf` shell listing. Red `backup.tgz; echo MARKER` marker in listing
  JSON; Blue archive allowlist-regex + `escapeshellarg` full path (plus
  co-present T4 containment).
- Priors (T3c): red `d6387a003a23`, blue `bf98fd13ec7b` (vault, forge-c13).

## T4 Path traversal read (CWE-22)

- Subclass T4a (planned Cycle 1): Python file-serve endpoint joining unsanitized
  `name` param; `../` escapes docroot to a planted secret file.
- Taint: query param → `os.path.join(docroot, name)` → file read.
- Red shape: benign `name=welcome.txt` vs `name=../../secret.txt`.
- Blue pattern: resolve + constrain under docroot (`commonpath` check); reject escapes.
- Subclass T4b (proven forge Cycle 8, Node): `readDoc` join-without-check.
- Subclass T4c (proven forge Cycle 17, Node): lambda-fixture containment.
- Subclass T4e (proven forge Cycle 19, PHP): check-then-read SPLIT (TOCTOU)
  — containment checked on the unresolved `$joined` string (passes for
  `../secret.txt`), the READ resolves via `realpath` (leaks outside).
  Fix doctrine: resolve FIRST, then containment-check, then read.
- Priors: T4a red `6ad9156807d4`/blue `366e65412fc8`; T4e red `3de754d6ef13`/blue `f2d0692014af`.

## T5 Logic-abuse gate → sink chain (CWE-285 + CWE-95)

- Subclass T5a: role-grant endpoint (Link A) gates dynamic query (Link B);
  single-step probe exits 1, chained single-payload probe exits 0.
- Proven by: `targets/node_chain_link` (Wave 14, gate 725).
- Subclass T5b (proven forge Cycle 14, 2026-10-31, Node): promo-code gate
  (`PRO-2026`→pro badge cookie) + template-string eval projection
  (`(${base}) * (1 + ${growth} / 100)`). ONE unified Red script exits 0;
  Blue dual decimal allowlist + `Number` arithmetic (eval eliminated) →
  exit 1, regressions 0.
- Priors (T5b): red `1f9cdccfa4b4`, blue `3f2a9723607d` (vault, forge-c14).
- Red shape: unified payload fusing both weaknesses in ONE script (Wave-28 rule).
- Blue pattern: server-side authorization on Link B independent of client role claim.

## T6 Reflected XSS sink (CWE-79)

- Subclass T6b (proven forge Cycle 10, 2026-10-31, PHP): raw reflection.
  Runtime: is_string + htmlspecialchars(ENT_QUOTES).
- Subclass T6c (proven forge Cycle 16, 2026-10-31, PHP): STORED XSS —
  `/sign?author=` persists raw to a store, `/wall` renders unescaped.
  Two-step Red probe (sign marker → read wall) exits 0. Blue doctrine:
  RENDER-time escaping (coerce scalar + htmlspecialchars
  ENT_QUOTES|ENT_SUBSTITUTE), store stays raw — never mangle at rest.
  Fixture-state rule: stores live under `/tmp` (runtime is read-only).
- Priors (T6c): red `e82ce135d029`, blue `8d071b865442` (vault, forge-c16).
- Red shape: marker reflection unescaped in response body.
- Blue pattern: contextual escaping + allowlist; verify marker neutralized.

## T7 Client-claimed role gate → SQLi sink chain (CWE-639 + CWE-89)

- Subclass T7a (proven forge Cycle 4, 2026-10-31): `/grant?role=` Link A sets
  a client-controlled role cookie; cookie-gated `/order?id=` Link B runs
  string-concat SQL. ONE unified Red script (grant admin, reuse cookie,
  tautology) exits 0 pre-patch; Blue parameterizes Link B (`?` placeholder)
  → Red exit 1, regressions 0.
- Taint: query param → cookie → string-concat `db.execute`.
- Red shape: `role=admin` grant + `id=1 OR 1=1` tautology → all rows leak.
- Blue pattern: parameterize Link B sink (tautology neutralizes to empty);
  server-side Link A authorization is follow-up hardening.
- Priors: red `4a9146b18ac3`, blue `b09cb5a8f3ee` (vault, forge-c4).

## T8 SSRF-shaped selector → sink chain (CWE-918 family / CWE-73)

- Subclass T8a (attempted forge Cycle 7, 2026-10-31): true egress-SSRF
  (`http://<user>.internal/`, self-fetch via own alias). UNPROVABLE in
  `network_mode=none` — external DNS/egress dead, target cannot dial its
  own alias (502). Red correctly exits 2. Lesson, not a prior.
- Subclass T8b (proven forge Cycle 7c): profile-name selector over a LOCAL
  store (`profiles/<user>.json`) chained with eval (T2c). ONE unified Red
  script (traversal to `../../secret.json` + arithmetic eval) exits 0;
  Blue dual patch (regex allowlist + realpath/commonpath; decimal-regex)
  → exit 1, regressions 0.
- Taint: query param → local-store path; query param → eval.
- Red shape: `user=../../secret` + `spec=7*6` in one script.
- Blue pattern: allowlist-regex fullmatch + realpath/commonpath containment
  (Link A); decimal-regex allowlist (Link B).
- Priors (T8b): red `256ab8c3e090`, blue `95a4d221b4c2` (vault, forge-c7).

## T9 Invite/badge gate → store-traversal chain (CWE-639 + CWE-22)

- Subclass T9a (proven forge Cycle 11, 2026-10-31, Node): `/redeem?code=`
  Link A mints a member badge cookie from a static invite set; cookie-gated
  note store Link B joins unsanitized names. ONE unified Red script
  (redeem badge, reuse cookie, `../../secret.txt`) exits 0; Blue strict
  containment (`resolve` + `target!==base && !startsWith(base+sep)` →
  EINVAL→400) → exit 1, regressions 0.
- Taint: query param → badge cookie → `path.join` read.
- Red shape: `code=WELCOME-123` redeem + `note=../../secret.txt`.
- Blue pattern: non-empty check + resolve + strict containment; Link A
  hardening is follow-up.
- Priors: red `26245a5fb2af`, blue `8af210c7fd86` (vault, forge-c11).

## T2e supplemental note (Function-constructor sink)

- T2e (Gate-0 proven Cycle 17, OPEN by record): `new Function('x', 'return '
  + expr)` computes attacker expressions (`process.version` leaks). The
  C17 Blue patch closed only the T4 link; the T2e-only follow-up fixture
  (no traversal competition) is queued. Do NOT mark T2e closed.

## T1c note (identifier-position injection)

- Subclass T1c (proven forge Cycle 22, Python): `ORDER BY <sort> <dir>
  LIMIT <limit>` string-concat. Boolean CASE-flip (`1=1` vs `1=2` changes
  row order) + LIMIT arithmetic (`1-1` empties) are the deterministic
  signals. Fix doctrine: identifiers can NEVER be `?`-bound — allowlist
  `sort_by`/`direction` against tuples + `int(limit)` + `LIMIT ?`.
- Priors: red `08f8e7c97a65`, blue `a6598cd153a6` (vault, forge-c22).
