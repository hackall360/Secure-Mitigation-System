# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: VaultStore.commit must be atomic (temp + rename, no partial blobs).

A crash between write_bytes and chmod leaves a truncated .vault file that
count() still counts but nothing can decrypt: silent corruption that the
Task C fail-closed guard cannot see (mixed healthy+truncated scans skip
silently by design). Atomic commit removes the window.
"""

import os

import pytest


def _committed_blob(tmp_path):
    from modules.intel import sms_vault as vault

    store = vault.VaultStore(namespace=vault.VaultNamespace.RED, vault_dir=tmp_path / "v")
    record_id = store.commit({"kind": "boundary_escape", "sink": "eval(x)"}, fingerprint="abc")
    return store, tmp_path / "v" / "red" / f"{record_id}.vault"


def test_commit_leaves_no_temp_files(tmp_path):
    store, blob = _committed_blob(tmp_path)
    assert blob.exists()
    leftovers = [p for p in (tmp_path / "v" / "red").iterdir() if p.suffix == ".tmp"]
    assert leftovers == [], [p.name for p in leftovers]
    assert store.fetch(blob.stem)["sink"] == "eval(x)"


def test_commit_is_atomic_via_temp_rename(tmp_path, monkeypatch):
    """Simulate a crash mid-write: the final path must never hold a partial blob."""
    import pathlib

    from modules.intel import sms_vault as vault
    from modules.intel.sms_vault import VaultError

    store = vault.VaultStore(namespace=vault.VaultNamespace.RED, vault_dir=tmp_path / "v")

    crashed = []

    def crashing_replace(src, dst):
        crashed.append((str(src), str(dst)))
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(os, "replace", crashing_replace)
    with pytest.raises(VaultError, match="Vault write failed"):
        store.commit({"kind": "x"}, fingerprint="abc")
    assert crashed, "commit must go through an atomic rename step"
    finals = list(pathlib.Path(store.namespace_dir).glob("*.vault"))
    partials = [p for p in finals if p.stat().st_size < 50]
    assert partials == [], [p.name for p in finals]
