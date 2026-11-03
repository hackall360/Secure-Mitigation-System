# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first R2 vault gap tests (verification sweep): encrypt/decrypt round-trip,
fingerprinting, namespaced queries, budget resolve/floor, record shapes.

LAW 9 RED-first + LAW 4 sandbox/intel discipline: every test uses tmp_path
dirs (or mock-sealed seams) only — never the real vault; no network, no
library/ edits. Each test targets lines the fixed-filter BEFORE run showed
uncovered (sms_vault.py 89.0%, 31 missed lines incl. key-guard, crypto-guard,
index-fallback, list-fail, and error-path branches; budget/records already
100% on statement lines, so those tests pin branches the line tracer cannot
see: floor-vs-cap resolve, boundary sizes, strict shapes, cve/title key
splits, scanner fallbacks, summary limits).
"""

import pytest


def test_encrypt_refuses_short_key_and_decrypt_rejects_it(tmp_path):
    from library.intel.sms_vault import VaultError, decrypt_blob, encrypt_blob

    with pytest.raises(VaultError, match="32 bytes"):
        encrypt_blob({"a": 1}, key=b"\x01" * 16)
    with pytest.raises(VaultError, match="32 bytes"):
        decrypt_blob(b"{}", key=b"\x01" * 8)


def test_decrypt_rejects_non_record_payload(tmp_path):
    import json
    import secrets

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    from library.intel.sms_vault import VaultError, decrypt_blob

    key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps([1, 2]).encode(), None)
    blob = json.dumps({"v": 1, "nonce": nonce.hex(), "ciphertext": ciphertext.hex()}).encode()
    with pytest.raises(VaultError, match="did not decrypt to a record"):
        decrypt_blob(blob, key=key)


def test_key_file_wrong_length_refuses_and_unreadable_fails_closed(tmp_path):
    from unittest import mock

    from library.intel.sms_vault import VaultError, load_or_create_key

    bad = tmp_path / "bad"
    bad.mkdir(parents=True)
    (bad / "vault.key").write_bytes(b"short")
    with pytest.raises(VaultError, match="unexpected length"):
        load_or_create_key(bad)

    denied = tmp_path / "denied"
    denied.mkdir(parents=True)
    (denied / "vault.key").write_bytes(b"x" * 32)
    with mock.patch("pathlib.Path.read_bytes", side_effect=PermissionError("denied")):
        with pytest.raises(VaultError, match="unreadable"):
            load_or_create_key(denied)


def test_key_race_recovers_and_reload_tightens_permissions(tmp_path):
    import os
    from unittest import mock

    from library.intel.sms_vault import load_or_create_key

    raced = tmp_path / "raced"
    raced.mkdir(parents=True)
    calls = {"n": 0}
    real_open = os.open

    def fake_open(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise FileExistsError("race")
        return real_open(*args, **kwargs)

    with mock.patch.object(os, "open", side_effect=fake_open):
        assert len(load_or_create_key(raced)) == 32

    keyed = tmp_path / "keyed"
    load_or_create_key(keyed)
    os.chmod(keyed / "vault.key", 0o644)
    assert load_or_create_key(keyed) is not None
    assert os.stat(keyed / "vault.key").st_mode & 0o777 == 0o600


def test_commit_guards_and_namespace_split_record_ids(tmp_path):
    from library.intel.sms_vault import VaultError, VaultNamespace, VaultStore

    store = VaultStore(namespace=VaultNamespace.RED, vault_dir=tmp_path / "v")
    with pytest.raises(VaultError, match="malformed"):
        store.fetch("../escape")
    with pytest.raises(VaultError, match="mapping"):
        store.commit(["not", "a", "mapping"])  # type: ignore[arg-type]
    red_id = VaultStore(namespace=VaultNamespace.RED, vault_dir=tmp_path / "n").commit({"k": 1})
    blue_id = VaultStore(namespace=VaultNamespace.BLUE, vault_dir=tmp_path / "n").commit({"k": 1})
    assert red_id != blue_id


def test_corrupt_and_zeroed_index_falls_back_to_full_scan(tmp_path):
    from library.intel.sms_vault import VaultNamespace, VaultStore

    store = VaultStore(namespace=VaultNamespace.RED, vault_dir=tmp_path / "v")
    store.commit({"k": 1}, fingerprint="fp1")
    index = tmp_path / "v" / "red" / "_fingerprints.json"
    index.write_bytes(b"not-json{{{")
    assert store.record_fingerprints() == {"fp1": 1}
    index.write_text('{"fp1": "notanint"}')
    assert store.record_fingerprints() == {"fp1": 1}
    index.write_text('{"fp1": 0}')
    assert store.record_fingerprints() == {"fp1": 1}


def test_empty_fingerprint_commit_skips_index_but_stays_fetchable(tmp_path):
    from library.intel.sms_vault import VaultNamespace, VaultStore

    vault_dir = tmp_path / "v"
    store = VaultStore(namespace=VaultNamespace.RED, vault_dir=vault_dir)
    record_id = store.commit({"k": 1})
    assert not (vault_dir / "red" / "_fingerprints.json").exists()
    assert store.record_fingerprints() == {}
    assert store.fetch(record_id) == {"k": 1}


def test_list_io_failure_fails_closed_for_scan_and_count(tmp_path):
    from unittest import mock

    from library.intel.sms_vault import VaultError, VaultNamespace, VaultStore

    store = VaultStore(namespace=VaultNamespace.RED, vault_dir=tmp_path / "v")
    with mock.patch("pathlib.Path.glob", side_effect=OSError("io-fail")):
        with pytest.raises(VaultError, match="list failed"):
            store.record_fingerprints()
        with pytest.raises(VaultError, match="list failed"):
            store.count()


def test_query_error_path_raises_and_tampered_namespace_is_skipped(tmp_path):
    from library.intel import sms_vault as vault

    with pytest.raises(AttributeError):
        vault.query_vault(None, vault_dir=tmp_path / "v")  # type: ignore[arg-type]

    vault_dir = tmp_path / "w"
    source = "eval(sharedSink)"
    fingerprint = vault.fingerprint_source(source)
    red = vault.VaultStore(namespace=vault.VaultNamespace.RED, vault_dir=vault_dir)
    record_id = red.commit({"kind": "x"}, fingerprint=fingerprint)
    (vault_dir / "red" / f"{record_id}.vault").write_bytes(b"tampered")
    (vault_dir / "red" / "_fingerprints.json").unlink(missing_ok=True)
    blue = vault.VaultStore(namespace=vault.VaultNamespace.BLUE, vault_dir=vault_dir)
    blue.commit({"kind": "y"}, fingerprint=fingerprint)
    (vault_dir / "blue" / "_fingerprints.json").unlink(missing_ok=True)
    result = vault.query_vault(source, vault_dir=vault_dir)
    assert result.status == "KNOWN_ARCHETYPE"
    assert result.namespaces == ["blue"]
    assert result.record_count == 1


def test_namespaced_query_reports_only_committed_namespace(tmp_path):
    from library.intel import sms_vault as vault

    vault_dir = tmp_path / "v"
    source = "const q = req.query.id;\neval(q);\n"
    assert vault.query_vault(source, vault_dir=vault_dir).status == "NOVEL_SURFACE"
    vault.commit_verified(
        namespace=vault.VaultNamespace.RED,
        source=source,
        payload={"sink": "eval(q)"},
        vault_dir=vault_dir,
    )
    result = vault.query_vault(source, vault_dir=vault_dir)
    assert result.status == "KNOWN_ARCHETYPE"
    assert result.namespaces == ["red"]
    assert result.record_count == 1


def test_fingerprint_blank_comment_and_code_sources_differ():
    from library.intel.sms_vault import fingerprint_source

    blank = fingerprint_source("")
    comment = fingerprint_source("# only a comment")
    code = fingerprint_source("eval(x)")
    assert len({blank, comment, code}) == 3
    assert all(len(digest) == 64 for digest in (blank, comment, code))


def test_vault_stats_counts_namespaces_and_estimates_savings(tmp_path):
    from library.intel import sms_vault as vault

    vault_dir = tmp_path / "v"
    vault.commit_verified(
        namespace=vault.VaultNamespace.RED,
        source="eval(a)",
        payload={"sink": "a"},
        vault_dir=vault_dir,
    )
    vault.commit_verified(
        namespace=vault.VaultNamespace.BLUE,
        source="exec(b)",
        payload={"fix": "b"},
        vault_dir=vault_dir,
    )
    stats = vault.vault_stats(vault_dir=vault_dir)
    assert stats["red"]["records"] == 1
    assert stats["blue"]["records"] == 1
    assert stats["green"]["records"] == 0
    assert stats["known_archetypes"] == 2
    assert stats["tokens_saved_estimate"] == 4000


def test_resolve_payload_budget_applies_floor_and_cap():
    from library.shared.sms_budget import DEFAULT_FLOOR_BYTES, resolve_payload_budget

    assert resolve_payload_budget(10**9, 100) == max(DEFAULT_FLOOR_BYTES, 400)
    assert resolve_payload_budget(100, 10**9) == 100
    assert resolve_payload_budget(5000, 1000) == 5000


def test_check_payload_budget_boundary_passes_and_over_fails_named():
    from library.shared.sms_budget import check_payload_budget, payload_size_bytes

    payload = {"a": 1}
    exact = payload_size_bytes(payload)
    assert check_payload_budget(payload, exact, "ctx") == exact
    with pytest.raises(ValueError, match="ctx"):
        check_payload_budget(payload, exact - 1, "ctx")


def test_sanitize_cve_id_bounds_and_strict_shape():
    from library.shared.sms_records import sanitize_cve_id, sanitize_cve_id_strict

    assert sanitize_cve_id(None) == ""
    assert sanitize_cve_id(123) == "123"
    assert sanitize_cve_id("cve-" + "9" * 100) == "CVE-" + "9" * 28
    assert sanitize_cve_id_strict("CVE-2024-3094") == "CVE-2024-3094"
    assert sanitize_cve_id_strict("CVE-24-1") == ""
    assert sanitize_cve_id_strict(None) == ""


def test_truncate_summary_limits_and_record_dict_shapes():
    from library.shared.sms_records import dedupe_records, to_record_dict, truncate_summary

    assert truncate_summary("abcdef", 3) == "abc"
    assert truncate_summary("abc", 3) == "abc"
    assert truncate_summary("abcdef", 0) == ""
    assert truncate_summary(123) == ""

    class Rec:
        source = "s"
        cve_id = "C"
        title = "t"
        summary = "x" * 700
        severity = "H"
        cvss = "9.0"
        cwe = None

    shaped = to_record_dict(Rec())
    assert len(shaped["summary"]) == 600
    assert shaped["cwe"] == []

    class Bare:
        pass

    fallback = to_record_dict(Bare())
    assert fallback["source"] == "?"
    assert fallback["cve_id"] == ""

    class WithScanner:
        scanner = "g"
        title = "t2"

    assert to_record_dict(WithScanner())["source"] == "g"

    class A:
        source = "a"
        cve_id = "C1"
        title = "t1"
        summary = "s"
        severity = ""
        cvss = ""
        cwe = []

    class B:
        source = "a"
        cve_id = ""
        title = "t1"
        summary = "s"
        severity = ""
        cvss = ""
        cwe = []

    assert len(dedupe_records([A(), B()])) == 2
    assert dedupe_records([]) == []
