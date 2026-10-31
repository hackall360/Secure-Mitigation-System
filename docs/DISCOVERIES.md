# Discoveries — novel findings only, with evidence links

Run: `overnight_1793434523077_12855248373640259943`.

None yet. Entries require: Docker evidence (Red exit 0 pre-patch / exit 1
post-patch + regression exit 0), evidence file path in run `validation/`,
and taxonomy link.

## D1 — T4a traversal guard prior (Cycle 1, 2026-10-31)

- Novel fixture: traversal-gated file read (`read_doc` join-without-check) +
  co-located eval sink, Python. Red exit 0 (traversal to planted secret),
  Blue realpath-containment patch → Red exit 1, regressions 0/0.
- Evidence: run `validation/task-101-c1-report.json` (receipt pre=0/post=1,
  patch sha `9eb8e75d…`), `validation/task-102-c1-vault.txt` (vault ids,
  KNOWN_ARCHETYPE recall).
- Taxonomy: T4/T4a. Vault: red `6ad9156807d4`, blue `366e65412fc8`.
- Gate-3: replay PASS on unseen renamed variant (traversal + absolute-path
  blocked, benign preserved) — prior generalizes.

## D2 — T2b decimal-allowlist prior (Cycle 2, 2026-10-31)

- Novel fixture: Node reflected-greeting (T6) + eval calculator (T2). Red
  exit 0 (`eval executed process.version`), Blue 7-line decimal allowlist →
  Red exit 1, regressions 0/0. Two instructive rollbacks preceded: Blue
  96-line parser over surgical budget (E2a), contract/test mismatch on `40+2`
  (E2b) — both fail-closed correct.
- Evidence: run `validation/task-203-c2c-report.json` (receipt pre=0/post=1,
  patch sha `195025c2…`), `validation/task-204-c2-vault.txt`.
- Taxonomy: T2/T2b (+T6 co-present). Vault: red `de34c8111ebd`,
  blue `cc18b84b9ff8`.
- Gate-3: replay PASS on unseen renamed Node variant (4/4 evil blocked).

## D3 — T7+T1 unified-chain prior (Cycle 4, 2026-10-31)

- Novel fixture: client-claimed role cookie (T7) gating string-concat SQLi
  (T1). Red ONE unified script (grant admin → reuse cookie → tautology)
  exit 0; Blue 1-line parameterization → Red exit 1, regressions 0/0.
  First-try verify, no rollbacks — the chain-explicit contract worked.
- Evidence: run `validation/task-401-c4-report.json` (receipt pre=0/post=1,
  patch sha `ae8d12c9…`), `validation/task-402-c4-vault.txt`.
- Taxonomy: new T7 class + T1. Vault: red `4a9146b18ac3`, blue `b09cb5a8f3ee`.
- Gate-3: replay PASS (renamed variant; tautology → empty per bundled
  semantics; first replay script's exception-expectation was my error).

## D4 — T3a escapeshellarg prior (Cycle 5, 2026-10-31)

- Novel fixture: PHP `/ping?host=` → `shell_exec("printf '%s' " . $host)`.
  Red exit 0 (`a;echo PWNED` → `aPWNED`); Blue `is_string` + `escapeshellarg`
  → Red exit 1, regressions 0/0. Attempts 1-2 died on `RedReport` schema
  validation (infra fault, not verdict); slim agents=1 cleared it AND was
  cheapest cycle yet (≈$0.14).
- Evidence: run `validation/task-503-c5c-report.json` (receipt pre=0/post=1,
  patch sha `81b2fba0…`), `validation/task-504-c5-vault.txt`.
- Taxonomy: T3/T3a (first forge proof of the T3 family). Vault:
  red `bc06d91cdbed`, blue `e63fc6e43cea`.
- Gate-3: replay PASS in Docker PHP (renamed variant; injection inert).

## D5 — T8b+T2c selector-chain prior (Cycle 7, 2026-10-31)

- Novel fixture: profile-store selector (`profiles/<user>.json`, T8b) + eval
  theme (T2c). Red ONE unified script (traversal to `../../secret.json` +
  eval) exit 0; Blue dual patch (regex allowlist + realpath/commonpath;
  decimal-regex) → Red exit 1, regressions 0/0. Attempts 1-2 proved
  TRUE SSRF unprovable in `network_mode=none` (external DNS dead, self-dial
  502) — the provable SSRF class is selector-injection (T8b).
- Evidence: run `validation/task-703-c7c-report.json` (receipt pre=0/post=1,
  patch sha `8bdab469…`), `validation/task-704-c7-vault.txt`.
- Taxonomy: new T8 class (a=true-SSRF unprovable-here, b=selector provable).
  Vault: red `256ab8c3e090`, blue `95a4d221b4c2`.
- Gate-3: replay PASS (renamed variant; both links blocked).

## D6 — T4b+T2d Node cross-language prior (Cycle 8, 2026-10-31)

- Novel fixture: Node `readDoc` join-without-check + eval `calc`. Red exit 0
  (eval sink retained finding; traversal co-present); Blue dual patch
  (resolve+startsWith + decimal-regex) → Red exit 1, regressions 0/0.
  First-try verify — the T4a containment prior transferred languages.
- Evidence: run `validation/task-801-c8-report.json` (receipt pre=0/post=1,
  patch sha `8946f259…`), `validation/task-802-c8-vault.txt`.
- Taxonomy: new T4b (Node) + T2d (Node decimal) subclasses. Vault:
  red `20734eb19022`, blue `11d9759e7414`.
- Gate-3: replay PASS (renamed variant; traversal blocked, benign ok).

## D7 — T6b htmlspecialchars prior (Cycle 10, 2026-10-31)

- Novel fixture: PHP `/hi?name=` raw reflection. Red exit 0
  (`<script>alert(1)</script>` reflected raw); Blue `is_string` +
  `htmlspecialchars(ENT_QUOTES)` → Red exit 1, regressions 0/0. First-try.
- Evidence: run `validation/task-1001-c10-report.json` (receipt pre=0/post=1,
  patch sha `195e17c6…`), `validation/task-1002-c10-vault.txt`.
- Taxonomy: new T6b (PHP) subclass (T6 was co-present-only before). Vault:
  red `b5753bddae95`, blue `517a43a5ddea`.
- Gate-3: replay PASS in Docker PHP (script neutralized, quotes escaped).

## D8 — T9+T4 invite-gate chain prior (Cycle 11, 2026-10-31)

- Novel fixture: Node invite redeem (`WELCOME-123`→member badge) gating a
  traversal-sensitive note store. Red ONE unified script (redeem badge →
  reuse cookie → `../../secret.txt`) exit 0; Blue strict containment →
  Red exit 1, regressions 0/0. First-try.
- Evidence: run `validation/task-1101-c11-report.json` (receipt pre=0/post=1,
  patch sha `80210f96…`), `validation/task-1102-c11-vault.txt`.
- Taxonomy: new T9 class (invite/badge gate) + T4. Vault:
  red `26245a5fb2af`, blue `8af210c7fd86`.
- Gate-3: replay PASS (renamed variant; 4/4 evil blocked).

## D9 — T3c tar-sink prior (Cycle 13, 2026-10-31)

- Novel fixture: PHP `/extract?archive=` → `tar tzf` shell concat + T4
  store read. Red exit 0 (`; echo MARKER` in listing); Blue allowlist +
  escapeshellarg (+T4 containment) → Red exit 1, regressions 0/0. First-try.
- Evidence: run `validation/task-1301-c13-report.json` (receipt pre=0/post=1,
  patch sha `cd8ce205…`), `validation/task-1302-c13-vault.txt`.
- Taxonomy: new T3c subclass. Vault: red `d6387a003a23`,
  blue `bf98fd13ec7b`.
- Gate-3: replay PASS (renamed variant; injection inert).

## D10 — T5b promo-gate eval-chain prior (Cycle 14, 2026-10-31)

- Novel fixture: Node promo redeem (PRO-2026→pro badge) gating template
  eval projection. Red ONE unified script exit 0; Blue dual-decimal
  allowlist (eval eliminated) → Red exit 1, regressions 0/0. First-try.
- Evidence: run `validation/task-1401-c14-report.json` (receipt pre=0/post=1,
  patch sha `73373247…`), `validation/task-1402-c14-vault.txt`.
- Taxonomy: new T5b subclass (T5 novel beyond the bundled fixture). Vault:
  red `1f9cdccfa4b4`, blue `3f2a9723607d`.
- Gate-3: replay PASS (3/3 evil blocked, benign preserved).

## D11 — T6c stored-XSS prior (Cycle 16, 2026-10-31)

- Novel fixture: PHP guestbook (`/sign` stores, `/wall` renders raw).
  Red two-step exit 0; Blue render-time escaping → Red exit 1,
  regressions 0/0. Attempt 1 died on the read-only runtime (store in
  `__DIR__`); /tmp fix verified attempt 2.
- Evidence: run `validation/task-1602-c16b-report.json` (receipt pre=0/post=1,
  patch sha `77140d1e…`), `validation/task-1603-c16-vault.txt`.
- Taxonomy: new T6c subclass. Vault: red `e82ce135d029`,
  blue `8d071b865442`.
- Gate-3: replay PASS (renamed variant; stored payload neutralized).

## D12 — T4c+T2e lambda-fixture prior (Cycle 17, 2026-10-31)

- Novel fixture: Node `readDoc` join + `Function('x','return '+expr)` ctor.
  Gate-0 locally proved BOTH links (version string computes, secret leaks).
  Red retained the T4 traversal (exit 0); Blue closed ONLY it → exit 1.
  The T2e Function sink stays OPEN by explicit vault record (follow-up
  planned) — a partial patch honestly labeled, not hidden.
- Evidence: run `validation/task-1702-c17b-report.json` (receipt pre=0/post=1,
  patch sha `28d3f176…`), `validation/task-1703-c17-vault.txt`.
- Taxonomy: new T2e (Function ctor, Gate-0 proven) + T4c (Node containment).
  Vault: red `1dccdbe650ff`, blue `7ee3a5a461ec`.
- Gate-3: replay PASS (renamed variant; traversal blocked).

## D13 — T4e check-split prior (Cycle 19, 2026-10-31)

- Novel fixture: PHP `/note?name=` checks the UNRESOLVED join but reads the
  RESOLVED path (TOCTOU). Red exit 0 (`../secret.txt` leaks despite the
  prefix check passing); Blue resolve-FIRST + containment → exit 1,
  regressions 0/0. Attempts 1-2 died on closing-report schema faults;
  short contract verified attempt 3 (3rd confirmation of the rule).
- Evidence: run `validation/task-1903-c19c-report.json` (receipt pre=0/post=1,
  patch sha `35576912…`), `validation/task-1904-c19-vault.txt`.
- Taxonomy: new T4e subclass. Vault: red `3de754d6ef13`,
  blue `f2d0692014af`.
- Gate-3: replay PASS (renamed variant; split closed).

## D14 — T1c ORDER-BY/LIMIT prior (Cycle 22, 2026-10-31)

- Novel fixture: Python leaderboard with sort/dir/limit interpolation.
  Red exit 0 (boolean CASE flip changes row order); Blue allowlists +
  `LIMIT ?` → exit 1, regressions 0/0. First-try (short contract held).
- Evidence: run `validation/task-2201-c22-report.json` (receipt pre=0/post=1,
  patch sha `b6845f5f…`), `validation/task-2202-c22-vault.txt`.
- Taxonomy: new T1c subclass (identifier-position injection). Vault:
  red `08f8e7c97a65`, blue `a6598cd153a6`.
- Gate-3: replay PASS (renamed variant; flip dead).

## D15 — T4f greeter-containment prior (Cycle 24, 2026-10-31, PARTIAL)

- Fixture: Python greeter with stored-nickname second-order SQLi (Gate-0
  proven) + avatar traversal. Red chose the T4 link (exit 0); Blue closed
  it → exit 1, regressions 0/0. The T1d second-order stays OPEN by record
  (solo fixture queued) — second C17-pattern partial.
- Evidence: run `validation/task-2401-c24-report.json` (receipt pre=0/post=1,
  patch sha `dc1f0708…`), `validation/task-2402-c24-vault.txt`.
- Taxonomy: new T4f subclass. Vault: red `f7332fd6e860`,
  blue `25afac938546`.
- Gate-3: replay PASS (renamed variant; traversal blocked).

## D16 — T1d SOLO close prior (Cycle 25, 2026-10-31)

- Solo fixture (ONE-sink rule): stored nickname re-read into WHERE.
  Red two-step exit 0 (`amy' OR '1'='1` → hey,yo); Blue parameterized
  re-read → exit 1, regressions 0/0. First-try — CLOSES the C24 OPEN.
- Evidence: run `validation/task-2501-c25-report.json` (receipt pre=0/post=1,
  patch sha `23f052ba…`), `validation/task-2502-c25-vault.txt`.
- Taxonomy: T1d-closed. Vault: red `a25a9265a074`, blue `893ae13cafc2`.
- Gate-3: replay PASS (renamed schema; injection → stranger).

## D17 — T4g prefix-strip prior (Cycle 26, 2026-10-31)

- Novel fixture: Python `safe/`-strip then join. Red exit 0
  (`safe/../../secret.txt` leaks); Blue normalize-after-strip →
  exit 1, regressions 0/0. First-try.
- Evidence: run `validation/task-2601-c26-report.json` (receipt pre=0/post=1,
  patch sha `0577656b…`), `validation/task-2602-c26-vault.txt`.
- Taxonomy: new T4g subclass. Vault: red `4ab0b4866c07`,
  blue `2e16108b9cc1`.
- Gate-3: replay PASS (renamed variant; bypass dead).

## D18 — T3e format-template prior (Cycle 29, 2026-10-31)

- Novel fixture: Python user-controlled `str.format` template with an
  Author object in scope. Red exit 0 (`{1.__class__}` leaks); Blue
  parse-gate + single-arg format → exit 1, regressions 0/0. First-try.
- Evidence: run `validation/task-2901-c29-report.json` (receipt pre=0/post=1,
  patch sha `06abe85e…`), `validation/task-2902-c29-vault.txt`.
- Taxonomy: new T3e subclass (CWE-74, new family). Vault:
  red `9e21d63fd849`, blue `53bd3cb3bd28`.
- Gate-3: replay PASS (renamed variant; attribute walk dead).

## D19 — T1e solo prior, T9b-link open (Cycle 30, 2026-10-31, PARTIAL)

- Fixture: PIN-gated vault with two-slot concat lookup. Red proved the
  T1e sink via DIRECT IMPORT (no HTTP, no cookie) → exit 0; Blue
  parameterized both slots → exit 1. The T9b PIN-gate link was never
  exercised — OPEN by record (HTTP cookie round-trip required for gate
  proofs; new rule).
- Evidence: run `validation/task-3001-c30-report.json` (receipt pre=0/post=1,
  patch sha `d8207378…`), `validation/task-3002-c30-vault.txt`.
- Taxonomy: T1e-closed + T9b-open. Vault: red `375fc78c80f1`,
  blue `5818718a7d63`.
- Gate-3: replay PASS (renamed schema; injection → none).

## D20 — T9b-closed HTTP-cookie chain prior (Cycle 31, 2026-10-31)

- Follow-up fixture with the HTTP-enforced chain contract: Red ran the
  cookie round-trip (`/claim` → Set-Cookie → Cookie replay → hostile
  label → admin leak) exit 0; Blue parameterized both slots → exit 1.
  First-try. CLOSES the C30 OPEN gate-link record.
- Evidence: run `validation/task-3101-c31-report.json` (receipt pre=0/post=1,
  patch sha `fa4bceeeb…`), `validation/task-3102-c31-vault.txt`.
- Taxonomy: T9b-closed. Vault: red `5016cfe59e99`, blue `78cbd6661296`.
- Gate-3: replay PASS (renamed schema; gate-honored injection dead).

## D21 — T3f triple-stash prior (Cycle 32, 2026-10-31)

- Novel fixture: Node mini-mustache with `{{{ }}}` raw override reachable
  via the `tpl` param. Red exit 0 (script renders raw); Blue normalize +
  branch-removal → exit 1, regressions 0/0. First-try.
- Evidence: run `validation/task-3201-c32-report.json` (receipt pre=0/post=1,
  patch sha `391e2cf4…`), `validation/task-3202-c32-vault.txt`.
- Taxonomy: new T3f subclass (3rd CWE-74 member). Vault:
  red `1a97e89f1406`, blue `024cb234faeb`.
- Gate-3: replay PASS (renamed variant; raw path dead).

## D22 — T8c theme-selector prior (Cycle 36, 2026-10-31)

- Novel fixture: PHP theme-pack manifest selector (`pack` → manifest
  path). Red exit 0 (twin reads EVIL-PACK-MARKER); Blue allowlist +
  realpath-under-packs → exit 1, regressions 0/0. Attempt-2 retry.
- Evidence: run `validation/task-3602-c36b-report.json` (receipt pre=0/post=1,
  patch sha `68a00e60…`), `validation/task-3603-c36-vault.txt`.
- Taxonomy: new T8c subclass. Vault: red `a4357fa1433b`,
  blue `538245a2bf00`.
- Gate-3: replay PASS (renamed variant; escape dead).

## D23 — T3g exec-string prior (Cycle 37, 2026-10-31)

- Novel fixture: Node `exec('echo ' + host)` shell string. Red exit 0
  (`;`/`$()`/backtick/pipe all execute); Blue hostname allowlist +
  `execFile` argv (NO shell) → exit 1, regressions 0/0. First-try.
- Evidence: run `validation/task-3701-c37-report.json` (receipt pre=0/post=1,
  patch sha `ee8d931d…`), `validation/task-3702-c37-vault.txt`.
- Taxonomy: new T3g subclass (shell ELIMINATION doctrine). Vault:
  red `a7fe96cb1c35`, blue `a16b36b9ab0c`.
- Gate-3: replay PASS (renamed variant; shell dead, benign kept).

## D24 — T8d double-decode prior (Cycle 38, 2026-10-31)

- Novel fixture: PHP asset selector with check-then-decode split.
  Red exit 0 (`%252e` bypasses the `..` check, decodes at read);
  Blue decode-FIRST + NUL-reject + containment → exit 1, regressions 0/0.
  Attempt-2 retry (transient fault).
- Evidence: run `validation/task-3802-c38b-report.json` (receipt pre=0/post=1,
  patch sha `a158455d…`), `validation/task-3803-c38-vault.txt`.
- Taxonomy: new T8d subclass (dual of T4e). Vault: red `8bcef832a528`,
  blue `67a40f9e7de4`.
- Gate-3: replay PASS (layer-correct; all encodings 400).

## D25 — T7c price-tamper + T1h lookup chain prior (Cycle 40, 2026-10-31)

- Red (HTTP cookie round-trip, enforced): GET /tag?item=book&price=20 →
  capture Set-Cookie → replay hostile price on /checkout → 0 on cross-row leak.
- Blue (both links hardened): server-side gate (unknown-item reject +
  mismatch ValueError, return expected) + parametrized `WHERE price = ?`.
- Gate-3: unseen comment-inject / tamper-down / direct-cookie all blocked.
- Taxonomy: new T7c + T1h subclasses (v29). Vault: red `15edd883f29a`,
  blue `d887aa3dee3`. recall NOVEL_SURFACE (fingerprint-exact).
