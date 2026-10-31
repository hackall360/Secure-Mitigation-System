# CVE Candidates — strict evidence levels (NEVER claim an assigned CVE)

Run: `overnight_1793434523077_12855248373640259943`.

Levels: `HYPOTHESIS` → `REPRODUCED_LOCALLY` (deterministic exit 0 in sandbox
+ logs) → `PATCH_VERIFIED` (Blue patch → exit 1 + regressions exit 0) →
`NOVELTY_CHECKED` (searched existing CVE/Advisory refs, documented why novel)
→ `READY_FOR_RESPONSIBLE_DISCLOSURE` (PRIVATE draft in `docs/disclosures/`,
never published).

No candidates yet. Scout runs every 3rd cycle (first: Cycle 3).

## Scout Cycle 3 — PyJWT `jwks_client.py` @ `16231abf` (2026-10-14), MIT/BSD (2026-10-31)

- HYPOTHESIS tested: JWKS fetch SSRF (file/ftp/gopher URI, open redirect to
  cloud metadata) + `alg=none`/confusion acceptance at decode.
- Method: LOCAL clones only (depth 20-30, sparse for jwt/), LOCAL loopback
  experiments, no external traffic beyond `git clone` of public repos.
  Prior PyJWT 2.10.1 installed; clone tree exercised via sys.path.
- Results (all LOCAL, deterministic):
  1. `verify_signature=False` decodes unsigned tokens — DOCUMENTED opt-in,
     not a finding (caller explicitly disabled verification).
  2. Wrong-key HMAC forgery REJECTED (`InvalidSignatureError`).
  3. RS256→HS256 confusion with public key as HMAC secret REJECTED
     (`InvalidAlgorithmError`); control RS256 verifies.
  4. `file://`/`ftp://`/`gopher://` JWKS URIs REJECTED at constructor
     (`PyJWKClientError`: only http/https) — SSRF-via-scheme closed.
  5. Loopback 302 → `http://169.254.169.254/` NOT followed
     (`PyJWKClientConnectionError` on HTTP 302; server saw 1 request) —
     redirect-to-metadata closed; guard is `_NoRedirectHandler`.
- Verdict: **no candidate** — every tested shape is already guarded in the
  audited commit (scheme allowlist + no-redirect + alg allowlist + key-type
  binding). Stays at `HYPOTHESIS`-refuted; logged as negative to prevent
  re-work. Redirect-guard commit `4adcd02` noted as the fix reference.
- Responsible disclosure: nothing to disclose (no finding).

## Scout Cycle 6 — werkzeug `safe_join` + `send_from_directory` @ `2adaad1a` (2026-10-30), BSD (2026-10-31)

- HYPOTHESIS tested: traversal bypass (`..`, absolute, encoded `%2e`, `....//`,
  nested escapes, backslash confusion) reaching files outside the base dir.
- Method: LOCAL clones only (werkzeug + flask, shallow); in-process WSGI
  `Client` battery (no sockets, no network); `safe_join` unit battery.
- Results (all LOCAL, deterministic):
  1. Classic `../../secret.txt`, absolute `/etc/passwd`, bare `..`,
     `a/../../b`, `subdir/../../x`, `a/b/../../../x` → `None` → 404.
  2. `%2e%2e/` and `%2e%2e%2f` forms → 404 end-to-end (no silent decode-escape
     through the tested `request.args` + `safe_join` path).
  3. `....//outside.txt` → 404 (normpath does not collapse to `../..` escape
     that survives the `../` prefix check).
  4. Backslash payloads pass through as LITERAL filenames on POSIX
     (`/srv/docs/a\..\..\secret.txt`) — correct per docstring (only `/` is a
     separator for URL paths; `\` rejection is Windows-only via
     `_os_alt_seps`). Not an escape: no directory crossing occurs.
  5. Symlinks explicitly out-of-scope per docstring ("up to the application
     to ensure contents can be trusted") — documented limitation, not a bug.
- Verdict: **no candidate**. Every bypass shape is blocked at the audited
  commit; the remaining edges are documented behavior. Stays refuted.
- Responsible disclosure: nothing to disclose (no finding).

## Scout Cycle 9 — `Flask-File-Upload` @ `d914b3a` (2023-02-08), MIT (2026-10-31)

- HYPOTHESIS tested: path traversal via upload/stream filename; extension
  allowlist bypass (`evil.php.jpg`-style); stored-filename trust escape.
- Method: LOCAL clone only (depth 10, single-maintainer repo, last commit
  2023); LOCAL string-level batteries against the exact code shapes
  (`secure_filename` + `safe_join` semantics from the installed werkzeug).
- Results (all LOCAL, deterministic):
  1. Upload filenames pass through `secure_filename` in `_set_file_data`
     BEFORE `_create_file_dict` stores them — `.../../x.mp4`→`x.mp4`,
     `/etc/passwd`→`etc_passwd`, `..`→`''`. Traversal neutralized at save.
  2. Stream path is `send_from_directory(base, <stored name>)` → werkzeug
     `safe_join` rejects any residual `..`/absolute with 404. Defense in
     depth holds even if the stored name were hostile.
  3. Extension gate `allowed_file` uses `rsplit(".",1)[1]` (correct last
     suffix); the STORED `__ext` uses `split(".")[1]` (first suffix —
     `evil.php.jpg` stores `php`, `a.b.c.mp4` stores `b`). MISMATCH, but the
     stored ext is never consumed by any allowlist/stream decision in the
     audited tree (grep: only tests reference `__ext`). Data-quality wart,
     not a bypass. `noext` filenames would crash `_create_file_dict`
     (IndexError) — but `allowed_file` rejects extensionless names first
     ("." not in filename → False), so the crash is unreachable via the
     guarded entry.
  4. `content_type` stored verbatim from the client (attacker-controlled
     MIME) — never used in a security decision in-tree; reflected only if
     the app echoes it. Noted, not a finding.
- Verdict: **no candidate**. Traversal closed twice (sanitize + safe_join);
  ext mismatch is unconsumed; MIME is untrusted-data-correctly-unused.
  Stale single-maintainer surface, but no hole at this commit.
- Responsible disclosure: nothing to disclose (no finding).

## Scout Cycle 12 — `sabre/vobject` + `sabre/xml` (2026-10, BSD) (2026-10-31)

- HYPOTHESIS tested: code-exec sinks, XXE in xCal/xCard parsing, ReDoS in
  MimeDir parser regexes.
- Method: LOCAL clones only (vobject @ `5e2f3388` 2026-10-05, BSD; sabre/xml
  shallow). Code-shape audit + bounded PCRE timing battery in Docker PHP.
- Results (all LOCAL, deterministic):
  1. No `eval`/`system`/`exec`/dynamic-include/`unserialize` sinks in vobject
     `lib/` (grep clean).
  2. No `LIBXML_NOENT`/entity-expansion flags in the audited tree; the
     sabre/xml `Reader::parse()` disables the entity loader on
     libxml < 2.9 (`libxml_disable_entity_loader(true)`, version-gated
     because ≥2.9 disables network entity loading by default) and converts
     libxml errors to exceptions. XXE live-fire BLOCKED: target image PHP
     lacks the `XMLReader` class entirely (`Class "XMLReader" not found`),
     so the backend cannot even instantiate there — no expansion surface in
     this runtime.
  3. MimeDir parser regexes: 100KB hostile line + 50K-repeat line both parse
     in ~0.00s — no catastrophic backtracking on the tested shapes.
  4. Reader accepts string-or-stream; no size cap found in the audited
     surface — a resource-exhaustion note (large-input CPU/RAM), NOT a
     finding at the audited commit without a live threshold measurement.
- Verdict: **no candidate**. Hardened parsing stack; the one live-fire
  attempt died on a missing PHP extension (environment, not a guard).
- Responsible disclosure: nothing to disclose (no finding).

## Scout Cycle 15 — `@hapi/shot` request-injection helper @ `d4514387` (2026-05-27), BSD-3 (2026-10-31)

- HYPOTHESIS tested: code-exec sinks, prototype pollution via header merge
  (`headers[field.toLowerCase()]` assignment) or payload path in this
  test-injection helper.
- Method: LOCAL clone only (depth 6, 411-line lib). Grep audit + static
  merge-loop replication (deps `@hapi/hoek`/`validate` absent locally, so
  no live `inject()` run — static only, stated as a limit).
- Results (all LOCAL, deterministic):
  1. No `eval`/`Function(`/spawn/exec sinks in `lib/*.js` (grep clean).
  2. Header-merge loop `this.headers[field.toLowerCase()] = headers[field]`:
     `Object.keys(JSON.parse('{"__proto__":...}'))` DOES surface `__proto__`
     as a key, but replicating the exact loop shows the key lands WITHOUT
     polluting `({}).polluted` (V8 treats the JSON-produced own-property
     name through the assignment path that defines rather than sets the
     prototype in this shape; observed `undefined`). NOT a live
     demonstration — static reasoning only, flagged as inconclusive rather
     than cleared, because the real `Request` constructor path (with hoek
     `applyToDefaults`/`clone` in `index.js`) was NOT executed.
  3. Payload path `Payload.encode` only stringifies/Buffers — no key
     traversal.
- Verdict: **no candidate** (nothing demonstrated); the `__proto__` header
  shape stays `HYPOTHESIS`-open (not refuted, not reproduced) pending a
  dependency-complete live run — explicitly out of scope for tonight's
  keyless sandbox (no `npm install` of external deps per minimal-footprint
  rule). Honest inconclusive, not a silent clear.
- Responsible disclosure: nothing to disclose (no finding).

## Scout Cycle 21 — `he` (HTML entities) @ `e5658ecc` (v2.0.0, 2026-10-04), MIT (2026-10-31)

- HYPOTHESIS tested: the canonical JS entity codec (zero-dependency,
  single-file ESM `src/he.mjs`, 254 lines) mishandles a forge T6 payload
  class (double-encode, astral, option footgun) or its decode direction
  enables stored-XSS primitive.
- Method: LOCAL clone only (depth 4) + LOCAL node ESM batteries (no deps,
  no network). Zero-dependency rule SATISFIED (first exotic scout to meet it).
- Results (all LOCAL, deterministic):
  1. `encode` neutralizes every forge T6 payload tried (`<script>`,
     `<img onerror>`, `O'Brien` → `&lt;`/`&gt;`/`&quot;`/`&apos;`);
     defaults emit numeric refs (`&#x3C;`). The forge's `htmlspecialchars`
     doctrine is the PHP twin of this behavior — cross-validated.
  2. Pre-encoded input double-encodes (`&lt;` → `&amp;lt;`) — CORRECT
     (idempotent-safe direction; decode-then-render would be the app's bug,
     not the codec's).
  3. `decode` is specified-to-decode (roundtrip exact); strict mode THROWS
     on unterminated `&ampamp;` (`Parse error`) while legacy decodes to
     `&amp;` — documented strictness split, fails CLOSED (throw), not open.
  4. Numeric hex/dec + astral (`&#x1F600;` → emoji) all decode per spec.
  5. 200KB `encodeEverything` completes in ms-scale (no perf cliff on the
     tested shape).
- Verdict: **no candidate**. The codec is the CORRECT answer to the T6
  family, and its sharp edges (strict-throw, double-encode direction)
  fail closed or are caller-responsibility. Reusable: `he`'s option table
  (strict vs legacy, encodeEverything cost) as the reference for any
  future encoder audit.
- Responsible disclosure: nothing to disclose (no finding).

## Scout Cycle 33 — `validator.js` @ `9ff34247` (2026-09-11), MIT (2026-10-31)

- HYPOTHESIS tested: `isURL` scheme confusion (`javascript:`/`data:` /
  mixed-case / encoded-payload-before-`@`) and `escape()` coverage gaps
  in a widely-used validation library.
- Method: LOCAL clone only (depth 3). Static read of `escape.js` (8-char
  replacement table) + `isURL.js` scheme/auth/port disambiguation logic
  (explicit `javascript:`-with-auth comment block). Live battery BLOCKED:
  the repo ships unbuilt ESM (`src/`, no `index.js`); the build needs
  babel, which is absent, and installing deps violates the scout
  minimal-footprint rule (same constraint as Cycle 15).
- Results (LOCAL, deterministic-but-static):
  1. `escape()` covers `&"'<>/\`` — the T6 payload set is neutralized by
     inspection (matches the forge's htmlspecialchars + `he` behavior).
  2. `isURL` has DEDICATED scheme-confusion handling: protocol regex +
     auth-vs-protocol disambiguation + encoded-content check
     (`%61...` before `@` treated as malicious protocol) + port-vs-protocol
     check + case-insensitive compare. The exact attack shapes probed are
     named in the code comments.
  3. No live verdict possible without a build — recorded as
     HYPOTHESIS-open on the confusion shapes (not refuted, not reproduced).
- Verdict: **INCONCLUSIVE-valuable** (second of the night). The static
  evidence leans guarded (the guards are written for THESE attacks), but
  honesty requires the live battery. Zero-dep rule REFINED: the next
  exotic target must be runnable with ZERO build (single-file, no babel/
  bundler), like `he` (C21) was.
- Responsible disclosure: nothing to disclose (no finding).
