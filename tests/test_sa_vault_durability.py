# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""F-215 / F-216: vault fail-closed contract and index lost-update."""

from __future__ import annotations

import os
import stat
import threading
import time
from pathlib import Path

import pytest

from library.intel import sms_vault
from library.intel.sms_vault import VaultError, VaultNamespace, VaultStore


def test_default_dir_without_home_raises_vault_error(monkeypatch):
    monkeypatch.delenv("PURPLEBOX_VAULT_DIR", raising=False)

    def boom():
        raise RuntimeError("no home")

    monkeypatch.setattr(sms_vault.Path, "home", staticmethod(boom))
    with pytest.raises(VaultError, match="PURPLEBOX_VAULT_DIR or HOME"):
        sms_vault.default_vault_dir()


def test_relative_override_rejected(monkeypatch):
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", "relative/vault")
    with pytest.raises(VaultError, match="absolute path"):
        sms_vault.default_vault_dir()


def test_override_expands_user(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", "~/v")
    assert sms_vault.default_vault_dir() == tmp_path / "v"


def test_unwritable_dir_raises_vault_error_without_path(tmp_path, monkeypatch):
    target = tmp_path / "secretname" / "vault"

    def bad_mkdir(self, *a, **k):
        raise PermissionError(13, "denied", str(self))

    monkeypatch.setattr(sms_vault.Path, "mkdir", bad_mkdir)
    with pytest.raises(VaultError) as info:
        sms_vault.load_or_create_key(target)
    assert "secretname" not in str(info.value)
    assert "PermissionError" in str(info.value)


def test_store_namespace_mkdir_failure_is_vault_error(tmp_path, monkeypatch):
    sms_vault.load_or_create_key(tmp_path)
    real = sms_vault.Path.mkdir

    def bad_mkdir(self, *a, **k):
        if self.name == "red":
            raise OSError(30, "ro", str(self))
        return real(self, *a, **k)

    monkeypatch.setattr(sms_vault.Path, "mkdir", bad_mkdir)
    with pytest.raises(VaultError, match="not writable"):
        VaultStore(VaultNamespace.RED, vault_dir=tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="POSIX modes")
def test_unenforceable_mode_raises(tmp_path, monkeypatch):
    tmp_path.chmod(0o755)
    monkeypatch.setattr(sms_vault.Path, "chmod", lambda self, mode: None)
    with pytest.raises(VaultError, match="owner-only modes"):
        sms_vault.load_or_create_key(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="POSIX modes")
def test_modes_are_owner_only(tmp_path):
    store = VaultStore(VaultNamespace.BLUE, vault_dir=tmp_path)
    store.commit({"a": 1}, fingerprint="f" * 64)
    for p in (tmp_path, tmp_path / "vault.key", store.namespace_dir, store._index_path()):
        assert stat.S_IMODE(p.stat().st_mode) & 0o077 == 0


def test_bad_key_length_message(tmp_path):
    (tmp_path / "vault.key").write_bytes(b"short")
    with pytest.raises(VaultError, match="move the vault directory aside"):
        sms_vault.load_or_create_key(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="fcntl lock is POSIX only")
def test_concurrent_bumps_do_not_lose_updates(tmp_path, monkeypatch):
    store = VaultStore(VaultNamespace.GREEN, vault_dir=tmp_path)
    real_read = VaultStore._read_index

    def slow_read(self):
        data = real_read(self)
        time.sleep(0.001)
        return data

    monkeypatch.setattr(VaultStore, "_read_index", slow_read)
    fp = "a" * 64
    threads = [
        threading.Thread(
            target=VaultStore(VaultNamespace.GREEN, vault_dir=tmp_path)._bump_index, args=(fp,)
        )
        for _ in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    monkeypatch.setattr(VaultStore, "_read_index", real_read)
    assert store._read_index() == {fp: 20}


def test_stale_tmp_cleaned_on_init(tmp_path):
    ns = tmp_path / "red"
    ns.mkdir(parents=True)
    old = ns / "x.abc.tmp"
    fresh = ns / "y.abc.tmp"
    old.write_bytes(b"1")
    fresh.write_bytes(b"1")
    past = time.time() - 7200
    os.utime(old, (past, past))
    VaultStore(VaultNamespace.RED, vault_dir=tmp_path)
    assert not old.exists()
    assert fresh.exists()
    assert isinstance(Path(fresh), Path)
