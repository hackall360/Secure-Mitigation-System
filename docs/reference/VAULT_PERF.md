# Vault performance note (W8 vault-perf)

Pins the tribunal 2c-4 gap: isolation/speed proven with numbers against the
current AES-256-GCM implementation (`modules/intel/sms_vault.py`). Crypto
untouched — these pins measure existing behavior on `tmp_path` vault dirs
(never the real `~/.cache` vault).

Up: [index.md](index.md)

## Measured numbers

Machine: 12th Gen Intel i5-12400F, x86_64, Python 3.14.4, local tmpfs
`tmp_path` vault, 100 commit+fetch round trips per trial.

| op | n | p50 (ms) | p95 (ms) | max (ms) | note |
| --- | --- | --- | --- | --- | --- |
| commit+fetch round trip | 100 | 0.045 | 0.061 | 0.673 | trial 0 (cold keygen + FS) |
| commit+fetch round trip | 100 | 0.044 | 0.050 | 0.136 | trial 1 |
| commit+fetch round trip | 100 | 0.042 | 0.051 | 0.097 | trial 2 |
| commit only | 100 | 0.030 | 0.047 | — | split from combined run |
| fetch only | 100 | 0.013 | 0.021 | — | split from combined run |

Budget pinned in `tests/test_w8_vault_perf_red.py`: round-trip p50 < 50 ms,
p95 < 250 ms. Measured p50 is ~1000x inside budget (AES-GCM on small JSON
payloads is sub-millisecond; the budget leaves headroom for loaded CI disks).

## Scale story (post-sprint close-the-gap, G3)

Found at scale: `query_vault` → `record_fingerprints` decrypted EVERY blob
per namespace per query — O(records), 23.81 ms/op at 2,000 records, linear
to seconds at 100k+. Every sweep cycle pays it (workflow, project,
sweep, binary_sweep all query once per cycle).

Fix shipped (`modules/intel/sms_vault.py`): per-namespace
`_fingerprints.json` index (fingerprint → count, 0600, 1 MiB cap),
bumped on commit (best-effort, never breaks the write), read on query
with full-scan fallback on missing/corrupt (fail open to correctness,
never wrong answers). Pinned in `tests/test_vault_index_red.py`:
index file exists after commit, query does ≤2 decrypts at 10 records,
corrupt index still answers correctly.

| op | n | before (ms/op) | after (ms/op) | speedup |
| --- | --- | --- | --- | --- |
| commit | 2000 | 0.033 | 0.033 | same path + one small JSON write |
| fetch single | 1000 | 0.014 | 0.014 | untouched |
| query_vault | 2000 records | 23.81 | 0.50 | **48x** (O(records) → O(1)) |

Multi-repo: namespaces are per-vault-dir directories; each repo gets its
own vault dir (or its own namespace), so the index stays per-corpus
bounded. The 1 MiB index cap bounds memory even for pathological
fingerprint cardinality; past the cap the index stops updating and
queries degrade to full scans (correct, slower — never wrong).

## Isolation + fail-closed pins (same file)

- Namespace isolation: RED record raises `KeyError` on BLUE/GREEN fetch, all
  six writer/reader pairs.
- Key file `vault.key` is `0600`; vault and namespace dirs are `0700`.
- Wrong-key (`0x00*32`, `0x01*32`) and tampered-blob decrypts raise
  `VaultError` — no silent fallback, no forgiving default.

## `vault_stats()` sanity

`tokens_saved_estimate == known_archetypes * 2000` (one red-analysis round
trip saved per known archetype). Pinned: 5 RED + 1 BLUE records give
`known_archetypes == 6` and `tokens_saved_estimate == 12000`, with
`green.records == 0`. Stats stay redacted (no payload material — see
`tests/test_vault.py::test_stats_are_redacted`).
