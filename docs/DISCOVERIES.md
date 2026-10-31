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
