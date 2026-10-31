# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: full-scan fingerprint path must fail closed on undecryptable blobs.

record_fingerprints() prefers the bounded JSON index but falls back to a
full decrypt scan when the index is missing/corrupt. In that fallback, an
undecryptable (tampered) blob is silently skipped, so query_vault() can
report NOVEL_SURFACE for a target whose only record was tampered with —
the module docstring promises fail-closed behavior instead.
"""

import pytest


def _committed_store(tmp_path):
    from modules.intel import sms_vault as vault

    store = vault.VaultStore(namespace=vault.VaultNamespace.RED, vault_dir=tmp_path / "v")
    record_id = store.commit({"kind": "boundary_escape", "sink": "eval(x)"}, fingerprint="abc123")
    blob_path = tmp_path / "v" / "red" / f"{record_id}.vault"
    blob_path.write_bytes(b"tampered-bytes")
    (tmp_path / "v" / "red" / "_fingerprints.json").unlink(missing_ok=True)
    return store


def test_full_scan_surfaces_tamper_instead_of_empty(tmp_path):
    from modules.intel.sms_vault import VaultError

    store = _committed_store(tmp_path)
    with pytest.raises(VaultError, match="authentication|decrypt|tamper"):
        store.record_fingerprints()


def test_healthy_full_scan_still_counts(tmp_path):
    from modules.intel import sms_vault as vault

    store = vault.VaultStore(namespace=vault.VaultNamespace.RED, vault_dir=tmp_path / "v")
    store.commit({"kind": "boundary_escape", "sink": "eval(x)"}, fingerprint="abc123")
    (tmp_path / "v" / "red" / "_fingerprints.json").unlink(missing_ok=True)
    counts = store.record_fingerprints()
    assert sum(counts.values()) == 1
