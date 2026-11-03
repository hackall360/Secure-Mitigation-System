# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED-FIRST parity W1: vault browse + replay (tmp_path only, LAW 4)."""

import pytest


def _commit(vault_dir, namespace: str = "red", marker: str = "SECRET-MARKER-XYZ") -> str:
    from modules.intel import sms_vault as vault

    return vault.commit_verified(
        namespace=vault.VaultNamespace(namespace),
        source="query($x) { user(id: $x) { name } }",
        payload={"kind": "probe-shape", "secret_blob": marker, "api_key": "KEY-MATERIAL-ABC"},
        vault_dir=vault_dir,
    )


def test_list_vault_namespaces_importable():
    from modules.services.sms_api import list_vault_namespaces

    assert callable(list_vault_namespaces)


def test_replay_vault_record_importable():
    from modules.services.sms_api import replay_vault_record

    assert callable(replay_vault_record)


def test_empty_vault_dir_lists_nothing(tmp_path):
    from modules.services.sms_api import list_vault_namespaces

    assert list_vault_namespaces(tmp_path / "empty") == []


def test_list_namespaces_after_commit(tmp_path):
    from modules.services.sms_api import list_vault_namespaces

    vault_dir = tmp_path / "vault"
    _commit(vault_dir)
    result = list_vault_namespaces(vault_dir)
    assert result == [{"namespace": "red", "record_count": 1}]


def test_replay_unknown_namespace(tmp_path):
    from modules.services.sms_api import replay_vault_record

    with pytest.raises(ValueError):
        replay_vault_record(tmp_path / "vault", "purple", "f" * 32)


def test_replay_unknown_id(tmp_path):
    from modules.services.sms_api import replay_vault_record

    vault_dir = tmp_path / "vault"
    _commit(vault_dir)
    with pytest.raises(ValueError):
        replay_vault_record(vault_dir, "red", "0" * 32)


def test_replay_malformed_id(tmp_path):
    from modules.services.sms_api import replay_vault_record

    with pytest.raises(ValueError):
        replay_vault_record(tmp_path / "vault", "red", "not-an-id")


def test_replay_empty_dir_unknown_id_fail_closed(tmp_path):
    from modules.services.sms_api import replay_vault_record

    with pytest.raises(ValueError):
        replay_vault_record(tmp_path / "empty", "red", "f" * 32)


def test_replay_summary_is_redacted(tmp_path):
    from modules.intel.sms_vault import fingerprint_source
    from modules.services.sms_api import replay_vault_record

    vault_dir = tmp_path / "vault"
    record_id = _commit(vault_dir)
    summary = replay_vault_record(vault_dir, "red", record_id)
    assert set(summary) == {"id", "fingerprint_prefix", "status", "created"}
    assert summary["id"] == record_id
    full_fp = fingerprint_source("query($x) { user(id: $x) { name } }")
    assert summary["fingerprint_prefix"] == full_fp[:12]
    assert summary["status"] == "KNOWN_ARCHETYPE"
    assert summary["created"]
    leaked = str(summary)
    for forbidden in (
        "SECRET-MARKER-XYZ",
        "KEY-MATERIAL-ABC",
        "secret_blob",
        "api_key",
        "payload",
        "ciphertext",
        "nonce",
    ):
        assert forbidden not in leaked, forbidden
