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

## T3d note (backtick-subshell operator family)

- Subclass T3d (proven forge Cycle 23, PHP): `` `printf "%s" "$host"` ``
  executes `$(...)`/backtick payloads. Gate-0: `x$(echo PWNED23)` →
  `xPWNED23`. Fix shape: `escapeshellarg` OUTSIDE the double quotes
  (`` `printf "%s" $safeHost` ``) — the quoting inversion is the whole fix.
  Replay semantics: INERTNESS (literal echo + no side effects), not absence.
- Priors: red `67a3c0ac01e4`, blue `f0435a01ca62` (vault, forge-c23).

## T3e note (format-string template injection, CWE-74)

- Subclass T3e (proven forge Cycle 29, Python): user-controlled template
  passed to `str.format()` with a rich object in scope — `{1.__class__}`
  walks attributes. Fix doctrine: `string.Formatter().parse()` pre-pass
  (fields only `''`/`'0'`, no nested braces), then single-arg format;
  better, remove the rich object from scope entirely.
- Gate-0: Template-substitution (`string.Template`, C24) is INERT — no
  evaluation, no vuln. Evaluation is the necessary ingredient.
- Priors: red `9e21d63fd849`, blue `53bd3cb3bd28` (vault, forge-c29).

## T9c note (locker-combo gate + emulated concat lookup, Node)

- Subclass T9c (proven forge Cycle 34, Node): locker combination
  (`2468`→member badge cookie) gates a concat-shaped lookup. Gate-0:
  hostile label leaks all tiers. Blue: exact-match lookup + typeof
  guards (no predicate building at all).
- HTTP-proof rule 2/2 (C31, C34): chain contracts demand the cookie
  round-trip; scribe asserts the gate-link shape in the probe.
- Priors: red `b90493849e92`, blue `47932423850a` (vault, forge-c34).

## T7b note (hardware-key gate + lookup chain)

- Subclass T7b (proven forge Cycle 35, Python): hardware-key serial
  (`1337-2600`→member badge cookie) gates a concat lookup. HTTP-cookie
  proof (claim → Set-Cookie → replay → cross-tier leak) exits 0;
  both-slot parameterization → exit 1. HTTP-proof rule 3/3.
- Priors: red `5695f826a247`, blue `bdc3912b9d28` (vault, forge-c35).

## T3g note (exec-string sink, shell elimination doctrine)

- Subclass T3g (proven forge Cycle 37, Node): `exec('echo ' + host)`.
  Fix: hostname allowlist (RFC-ish, ≤253) + `execFile('echo', [host])` —
  eliminate the shell, don't escape it. Preferred T3 pattern (stronger
  than C5/C13/C23 escaping).
- Priors: red `a7fe96cb1c35`, blue `a16b36b9ab0c` (vault, forge-c37).

## T7c+T1h note (price-tamper cookie gate + price-keyed lookup chain)

- Subclasses T7c+T1h (proven forge Cycle 40, Python, 5 attempts):
  client price cookie (Link A, `price_tag` returns raw client_price,
  no check vs PRICES) chained to price-keyed order lookup (Link B,
  string-concat `WHERE price`, CWE-89). HTTP-cookie proof (claim /tag
  → Set-Cookie → replay hostile price → cross-row leak) exits 0.
- Blue: BOTH links hardened (defense in depth) — server-side gate
  (unknown-item reject + mismatch ValueError, return expected) AND
  parametrized `WHERE price = ?`. Gate-3 unseen 3/3: comment-inject
  lamp blocked at gate; tamper-to-1 blocked; direct hostile cookie
  (bypass /tag) → no such order via parametrization.
- Flake record: 3x transient Blue-schema faults (extra=forbid
  strict) + 1x degraded-Red (probe not confirmed) after contract
  simplification; original detailed contract won on attempt 5. Lesson:
  contract detail guides Red's proof structure; simplify only the
  Blue-facing half, or not at all.
- Vault recall NOVEL_SURFACE (fingerprint-exact: T7c+T1h pair new;
  distinct from T1d stored-nickname solo). Priors: red `15edd883f29a`,
  blue `d887aa3dee3` (vault, forge-c40).

## T9d note (XFF-spoof trust-management gate, CWE-291)

- Subclass T9d (proven forge Cycle 43, Python, 2 attempts: 1x transient
  Blue-schema, then VERIFIED): `client_ip` trusts the LAST X-Forwarded-For
  entry with no proxy stripping it; `admin_path` gates on IP allowlist.
  Any remote client sending `X-Forwarded-For: 127.0.0.1` reaches admin.
  Stateless pure functions — F13-clean by design.
- Blue: ignore XFF entirely without a trusted proxy; use the direct
  connection IP (`headers["remote"]`). Textbook CWE-291 fix (4 lines).
  Gate-3 unseen 4/4: multi-hop spoof, spoof-only, ::1 spoof, padded spoof —
  all forbidden; benign local/remote intact.
- Vault: red `05ae3215c4df`, blue `b1b79b129b3c`; recall NOVEL_SURFACE.
  Fix doctrine: XFF is attacker input unless YOUR proxy strips it.

## T7e note (fallback-secret token forgery, CWE-798)

- Subclass T7e (proven forge Cycle 44, Python, FIRST-TRY): `mint`/`check`
  use `os.environ.get("FORGE_KEY", "default-secret")` — the fallback is
  public, so any client forges an admin token with zero server knowledge.
  Red: user token recorded, admin forged from the predictable fallback,
  /admin panel over HTTP. Stateless — F13-clean.
- Blue: `os.environ.get("FORGE_KEY") or secrets.token_hex(32)` — no
  predictable fallback; fail to per-process randomness. Documented
  tradeoff: restart invalidates outstanding tokens (fail-closed, correct
  for sessions; use a real secret manager for persistent tokens).
- Gate-3 unseen 4/4: fallback forgery, role-swap on valid sig, malformed
  tokens, cross-restart invalidation. Vault: red `1ae5d3597970`, blue
  `50d963c60c86`; NOVEL_SURFACE. Fix doctrine: NEVER a predictable
  fallback for a signing secret — crash or randomize, never default.

## T7f note (alg-none JWT bypass, hand-rolled verifier)

- Subclass T7f (proven forge Cycle 45, Python, 2 attempts: 1x transient
  Blue-schema, then VERIFIED): hand-rolled `verify` honors `alg=none`
  (returns claims with no signature); `admin_path` gates on role.
  Flip role claim, keep empty sig -> admin panel. Stateless.
- Mirror of C3 scout: the REAL PyJWT rejects `alg=none` (NEGATIVE) —
  the vuln lives in hand-rolled verifiers, not the library. Pair them
  in training: scout says what the ecosystem got right, forge shows
  what bespoke code gets wrong.
- Blue: `alg=none` -> None (fail-closed, 1 line). Mint path now issues
  unusable tokens — correct for a verifier with no HMAC path; a real
  fix would add HMAC mint+verify together (out of surgical scope).
- Gate-3 unseen 4/4: forged admin, HS256-empty-sig, case-smuggled algs,
  missing alg. Vault: red `bcff6f456366`, blue `b862da4e1750`; NOVEL.

## T1i note (LIKE-wildcard injection + F14 nested-quote lesson, CWE-89 family)

- Subclass T1i (proven forge Cycle 47, Python, 2 attempts: 1x token-budget
  transient, then VERIFIED): LIKE pattern interpolates raw input; `%`
  returns all rows, `_ob` reaches bob. Stateless (:memory: per call).
- F14 hypothesis CONFIRMED: C46 (nested-quote sink
  `'" + prefix + "%'"`) died 5x with Blue-schema faults; C47 (identical
  vuln, double-quoted sink, no nested-quote shapes in the model payload)
  cleared on attempt 2. The fragility is NESTED QUOTES in the sink line,
  not `%` itself. Fixture-authorship rule: sinks Blue must reproduce go
  in the LEAST-nested quoting available (double-quoted SQL, params
  outside the string).
- Blue: `ESCAPE '!'` neutralization (`!!`, `!%`, `!_`) + parametrized
  `LIKE ? ESCAPE '!'`. Exact-match preserved; wildcards dead; classic
  inject returns []. Gate-3 unseen 5/5.
- Vault: red `103e13616096`, blue `cdb6bb47452f`; NOVEL_SURFACE. Closes
  the C46 OPEN record (hotspot resolved, not merely parked).

## T6f note (response-splitting via Content-Disposition, CWE-113/93 family)

- Subclass T6f (proven forge Cycle 49, Python, FIRST-TRY): raw `name`
  flows into the `Content-Disposition` header; py3.14 stdlib
  `send_header` emits embedded CRLF unsplit-checked, so
  `x\r\nSet-Cookie: hacked=1` becomes a live forged header (proven at
  the byte level over a raw socket). Distinctive shape (download
  filename), deliberately non-canonical per F15.
- Blue: first line only + strip non-printable/DEL + empty-safe
  fallback (`report.txt`). Legit names (spaces) preserved; CRLF,
  lone-CR, DEL, ctrl all dead; empty attack falls back safely.
- Gate-3 unseen 5/5. Vault: red `bfaf17580b2e`, blue `d641d25b8956`;
  NOVEL_SURFACE. First-try clear on a fresh rare shape SUPPORTS the
  F15 mechanism (no training-dominant secure variant to hallucinate).

## T5d note (config section-name injection + hallucination-starvation)

- Subclass T5d (proven forge Cycle 51, Python, v2 fixture VERIFIED
  first-try): `render(section)` passes the user deck name into
  `cp.get` with a `db_password` fallback read; `deck=secrets`
  discloses the credential. Stateless, no interpolation anywhere.
- Blue: section allowlist (public-only, ValueError otherwise).
  Gate-3 unseen 5/5 (direct, DEFAULT, case, empty, traversal).
- F15 doctrine refined — HALLUCINATION STARVATION: v1 (identically
  severe `${secrets:db_password}` interpolation) deterministically
  provoked Red's `$$`-escaping confabulation twice (captured); v2
  (same breach, zero `$` characters) starved that exact vocabulary
  and cleared first-try. When a fixture stalls on second-pass
  contradiction, reshape to REMOVE the confabulated fix's vocabulary
  rather than re-running blind.
- Vault: red `f9475d1d9c08`, blue `524f3d596eaa`; NOVEL_SURFACE.

## T5e note (extract-overwrite variable injection + PHP8 negative)

- Subclass T5e (proven forge Cycle 52, PHP, FIRST-TRY): bare
  `extract($query)` (EXTR_OVERWRITE default) overwrites `$role`;
  crafted role param reaches the admin panel. Rare fix vocabulary;
  no hallucination, no faults.
- Blue: REMOVE extract() + explicit role read + deny-rule
  (`admin` from untrusted input forced to guest). Gate composition
  verified: `admin `, `ADMIN`, `admin\0` all forbidden at the exact
  gate. Fail-closed for literal-`admin` usernames (correct).
- NEGATIVE battery (valuable): PHP 8 REMOVED single-arg `parse_str`
  (ArgumentCountError) — the classic register-globals primitive is
  extinct; `extract()` is its living heir. Recorded so future Green
  never wastes Gate-0 on it.
- Vault: red `68b8699c2fa5`, blue `7a284ccbc042`; NOVEL_SURFACE.

## T3h note (CWE-88 argument injection without shell)

- Subclass T3h (proven forge Cycle 53, Python, 4 attempts: 3x BASELINE
  fails, then VERIFIED): command STRING built with raw `fmt`, then
  `shlex.split` — a space becomes a new argv element, so
  `png --output=/tmp/evil` hijacks the destination. No shell anywhere
  (distinct from T3a/c/d/dd/f/g shell family). Signal: the `wrote`
  path / split argv observable over HTTP.
- Attempt ledger: a1 contract IndexError (my assert bug), a2 exec-bit
  (snapshot strips it; chmod-after-copy fix), a3 `convert failed`
  STILL — root cause: exec-ing inside the target sandbox is
  unreliable. Fix: drop the subprocess from the TARGET; keep the
  write primitive in Gate-0 evidence, assert the argv split over HTTP.
- Blue: strict `[A-Za-z0-9]+` allowlist on fmt (spaces impossible).
  Gate-3 unseen 5/5. Vault: red `16e319585da8`, blue `c7d063cc33e7`.

## T6g note (dynamic-import specifier hijack + benign-executability rule)

- Subclass T6g (proven forge Cycle 54, Python, v3 VERIFIED): widget path
  flows raw into `import("...")` on a loader page; an attacker URL
  hijacks the script source. Stateless.
- Episode ledger: v1 (JSONP callback) provoked the `_CALLBACK_RE`
  hallucination twice (captured, archived task-5401/5402-redtruefault);
  v2 (bare-scheme import) drew a clean `no_findings` — the benign path
  was NOT browser-executable (bare specifier, no import map), so Red
  dismissed the fixture as broken, not vulnerable. v3 (benign
  `/static/chart.js` is a REAL served module): VERIFIED first-try.
- NEW RULE — benign-executability: the benign path must be genuinely
  functional in its real consumer (browser, CLI, DB), or Red reads a
  broken feature instead of a vuln. Gate-0 must check the BENIGN path
  end-to-end, not just string-shapes.
- Blue: prefix + suffix + traversal + metachar allowlist with safe
  fallback (`/static/chart.js`). Gate-3 unseen 8/8 (off-site,
  traversal, double-slash, backslash, quote-break, query/hash
  smuggle, parens). Vault: red `92f4fc36d931`, blue `7e83df77e34f`.
