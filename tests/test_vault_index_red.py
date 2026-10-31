# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: vault fingerprint index — query_vault must not decrypt every blob.

Today query_vault → record_fingerprints decrypts ALL records per namespace
per query (O(records); 24ms at 2k records). Pin: commit maintains a bounded
JSON index (fingerprint → count) per namespace; query reads the index
(O(1)); index corruption/missing falls back to a full scan (fail open to
correctness, never wrong answers).
"""

import tempfile
from pathlib import Path

from modules.intel import sms_vault as V


def _tmp():
    return Path(tempfile.mkdtemp(prefix="vault-idx-"))


def test_commit_maintains_index():
    tmp = _tmp()
    store = V.VaultStore(V.VaultNamespace.RED, tmp)
    store.commit({"a": 1}, fingerprint="fp-1")
    store.commit({"a": 2}, fingerprint="fp-1")
    index_files = list(tmp.rglob("*fingerprint*")) + list(tmp.rglob("*index*"))
    assert index_files, "commit must maintain a fingerprint index file"


def test_query_uses_index_not_full_decrypt():
    tmp = _tmp()
    store = V.VaultStore(V.VaultNamespace.RED, tmp)
    for i in range(10):
        store.commit({"i": i}, fingerprint=f"fp-{i}")
    calls = {"n": 0}
    real_decrypt = V.decrypt_blob

    def counting(*a, **k):
        calls["n"] += 1
        return real_decrypt(*a, **k)

    V.decrypt_blob = counting
    try:
        V.query_vault("probe sink-1 text", vault_dir=tmp)
    finally:
        V.decrypt_blob = real_decrypt
    assert calls["n"] <= 2, f"query must not decrypt every blob (did {calls['n']})"


def test_corrupt_index_falls_back_to_scan():
    tmp = _tmp()
    store = V.VaultStore(V.VaultNamespace.RED, tmp)
    store.commit({"a": 1}, fingerprint="fp-9")
    for p in list(tmp.rglob("*fingerprint*")) + list(tmp.rglob("*index*")):
        p.write_bytes(b"corrupt{{{")
    result = V.query_vault("probe", vault_dir=tmp)
    assert result.status in ("KNOWN_ARCHETYPE", "NOVEL_SURFACE")
