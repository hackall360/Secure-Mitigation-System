# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Vault perf + isolation pins (W8 vault-perf, tribunal 2c-4 gap).

RED FIRST: pins (a) commit+fetch round-trip latency budget (p50 < 50ms local
AES-GCM on tmp_path vault, 100 records), (b) namespace isolation across all
three namespaces, (c) key-file 0600 perms enforced, (d) wrong-key decrypt
raises (no silent fallback). Uses tmp_path vault dirs only — never the real
~/. cache vault. Expected GREEN against the current implementation with no
crypto changes; a failure here is an escalation, not an invitation to touch
crypto.
"""

from __future__ import annotations

import os
import stat as _stat
import time

import pytest


def _payload(idx: int) -> dict:
    return {
        "kind": "boundary_escape",
        "fixture": "node_query_sink",
        "sink": "queryExpression",
        "idx": idx,
    }


def _percentile(sorted_ms: list[float], pct: float) -> float:
    if not sorted_ms:
        raise ValueError("empty sample")
    rank = min(len(sorted_ms) - 1, max(0, int(round((pct / 100) * (len(sorted_ms) - 1)))))
    return sorted_ms[rank]


def test_round_trip_latency_budget_100_records(tmp_path, monkeypatch):
    """100 commit+fetch round trips on a tmp_path vault finish inside budget."""
    from modules.intel import sms_vault as vault

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    store = vault.VaultStore(namespace=vault.VaultNamespace.RED)

    latencies_ms: list[float] = []
    for idx in range(100):
        started = time.perf_counter()
        record_id = store.commit(_payload(idx))
        fetched = store.fetch(record_id)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies_ms.append(elapsed_ms)
        assert fetched["idx"] == idx

    ordered = sorted(latencies_ms)
    p50 = _percentile(ordered, 50)
    p95 = _percentile(ordered, 95)
    assert p50 < 50.0, f"round-trip p50 {p50:.3f}ms exceeds 50ms budget"
    assert p95 < 250.0, f"round-trip p95 {p95:.3f}ms exceeds 250ms budget"


def test_namespace_isolation_all_pairs(tmp_path, monkeypatch):
    """A RED record is invisible to BLUE/GREEN fetch, and vice versa."""
    from modules.intel import sms_vault as vault

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    stores = {ns: vault.VaultStore(namespace=ns) for ns in vault.VaultNamespace}
    record_ids = {
        ns: stores[ns].commit({"kind": "probe", "ns": ns.value}) for ns in vault.VaultNamespace
    }
    for writer_ns, record_id in record_ids.items():
        assert stores[writer_ns].fetch(record_id)["ns"] == writer_ns.value
        for reader_ns, reader in stores.items():
            if reader_ns is writer_ns:
                continue
            with pytest.raises(KeyError):
                reader.fetch(record_id)


def test_key_file_owner_only_perms(tmp_path, monkeypatch):
    """Key file is 0600 and vault/namespace dirs are 0700."""
    from modules.intel import sms_vault as vault

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    store = vault.VaultStore(namespace=vault.VaultNamespace.RED)
    store.commit(_payload(0))
    assert _stat.S_IMODE(os.stat(store.vault_dir).st_mode) == 0o700
    assert _stat.S_IMODE(os.stat(store.namespace_dir).st_mode) == 0o700
    mode = _stat.S_IMODE(os.stat(store.key_path).st_mode)
    assert mode == 0o600, oct(mode)


def test_wrong_key_decrypt_raises_no_fallback(tmp_path):
    """Wrong-key and tampered-blob decrypts raise VaultError, never defaults."""
    from modules.intel import sms_vault as vault
    from modules.intel.sms_vault import VaultError

    vault_dir = tmp_path / "vault"
    store = vault.VaultStore(namespace=vault.VaultNamespace.RED, vault_dir=vault_dir)
    record_id = store.commit(_payload(0))
    blob = (vault_dir / "red" / f"{record_id}.vault").read_bytes()
    with pytest.raises(VaultError):
        vault.decrypt_blob(blob, key=b"\x00" * 32)
    with pytest.raises(VaultError):
        vault.decrypt_blob(blob, key=b"\x01" * 32)
    tampered = bytearray(blob)
    tampered[-8:] = b"deadbeef"
    with pytest.raises(VaultError):
        vault.decrypt_blob(bytes(tampered), key=store._key)


def test_vault_stats_tokens_saved_estimate_sanity(tmp_path, monkeypatch):
    """tokens_saved_estimate scales linearly with known archetype count."""
    from modules.intel import sms_vault as vault

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    red = vault.VaultStore(namespace=vault.VaultNamespace.RED)
    for idx in range(5):
        red.commit(_payload(idx))
    vault.VaultStore(namespace=vault.VaultNamespace.BLUE).commit({"kind": "patch"})
    stats = vault.vault_stats()
    assert stats["red"]["records"] == 5
    assert stats["blue"]["records"] == 1
    assert stats["green"]["records"] == 0
    assert stats["known_archetypes"] == 6
    assert stats["tokens_saved_estimate"] == 6 * 2000
