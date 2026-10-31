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
