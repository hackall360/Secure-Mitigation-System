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
