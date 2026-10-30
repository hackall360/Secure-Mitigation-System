# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first vault tests (Subsystem B, V1 guidance matrix Y2).

RED per LAW 9: written BEFORE modules/intel/sms_vault.py exists.
Authenticated encryption uses AES-256-GCM from the `cryptography` package
(dev dependency to add); these tests pin the security contract:
wrong-key decryption fails closed, namespaces are isolated, stats are
redacted (no payload material), key files are owner-only.
"""

import pytest


def _sample_payload() -> dict:
    return {
        "kind": "boundary_escape",
        "fixture": "node_query_sink",
        "sink": "queryExpression",
        "shape": "decimal-integer allowlist",
    }


def test_vault_module_importable():
    import modules.intel.sms_vault as vault

    for name in (
        "VaultStore",
        "VaultNamespace",
        "fingerprint_source",
        "query_vault",
        "commit_verified",
        "vault_stats",
        "VaultQueryResult",
    ):
        assert hasattr(vault, name), name


def test_round_trip_and_namespace_isolation(tmp_path, monkeypatch):
    from modules.intel import sms_vault as vault

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    store = vault.VaultStore(namespace=vault.VaultNamespace.RED)
    record_id = store.commit(_sample_payload())
    assert record_id
    assert store.fetch(record_id)["sink"] == "queryExpression"
    blue = vault.VaultStore(namespace=vault.VaultNamespace.BLUE)
    with pytest.raises(KeyError):
        blue.fetch(record_id)


def test_wrong_key_fails_closed(tmp_path):
    from modules.intel import sms_vault as vault
    from modules.intel.sms_vault import VaultError

    vault_dir = tmp_path / "vault"
    store = vault.VaultStore(namespace=vault.VaultNamespace.RED, vault_dir=vault_dir)
    record_id = store.commit(_sample_payload())
    blob = (vault_dir / "red" / f"{record_id}.vault").read_bytes()
    with pytest.raises(VaultError):
        vault.decrypt_blob(blob, key=b"\x00" * 32)


def test_key_file_is_owner_only(tmp_path, monkeypatch):
    import os

    from modules.intel import sms_vault as vault

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    store = vault.VaultStore(namespace=vault.VaultNamespace.GREEN)
    store.commit({"kind": "archetype", "note": "shape"})
    mode = os.stat(store.key_path).st_mode & 0o777
    assert mode == 0o600, oct(mode)


def test_fingerprint_is_deterministic_and_sink_sensitive():
    from modules.intel.sms_vault import fingerprint_source

    a = "const rawUserId = req.query.id;\nconst queryExpression = eval(rawUserId);\n"
    b = "const rawUserId = req.query.id;\nconst queryExpression = eval(rawUserId);\n"
    c = "const host = req.query.host;\nchild_process.exec('diag ' + host);\n"
    assert fingerprint_source(a) == fingerprint_source(b)
    assert fingerprint_source(a) != fingerprint_source(c)
    assert len(fingerprint_source(a)) == 64


def test_query_known_vs_novel(tmp_path, monkeypatch):
    from modules.intel import sms_vault as vault

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    source = "const rawUserId = req.query.id;\neval(rawUserId);\n"
    first = vault.query_vault(source)
    assert first.status == "NOVEL_SURFACE"
    vault.commit_verified(
        namespace=vault.VaultNamespace.RED,
        source=source,
        payload=_sample_payload(),
    )
    second = vault.query_vault(source)
    assert second.status == "KNOWN_ARCHETYPE"
    assert second.record_count >= 1


def test_stats_are_redacted(tmp_path, monkeypatch):
    import json

    from modules.intel import sms_vault as vault

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    vault.commit_verified(
        namespace=vault.VaultNamespace.RED,
        source="eval(rawUserId);",
        payload=_sample_payload(),
    )
    stats = vault.vault_stats()
    dumped = json.dumps(stats)
    assert "queryExpression" not in dumped
    assert "decimal-integer" not in dumped
    assert stats["red"]["records"] >= 1
    assert stats["blue"]["records"] == 0
    assert stats["green"]["records"] == 0
    assert "tokens_saved_estimate" in stats
