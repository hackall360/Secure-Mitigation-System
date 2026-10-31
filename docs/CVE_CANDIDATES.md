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
