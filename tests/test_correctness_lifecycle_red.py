# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Z6 (correctness deep-validation round 6): replace_target tracking + registry + vault + accounting.

1. replace_target keeps the previous container TRACKED when remove hits a
   transient DockerException (session close() retries the reap); NotFound
   and clean removes still untrack. Regression for the round-6 leak where
   one running target per scan survived with both labels.
2. Registry: 4 UTF-8 fixtures read bounded/argv-shaped; binary ELF raises
   UnicodeDecodeError (the documented reason for the binary path).
3. Vault: per-dir keys differ, key file 0600, cross-vault isolation.
4. Usage accounting: ScanUsage sums tokens + cost.
5. Dockerfiles pinned to sha256 digests; chatter capped <= 220 chars.
6. Compression never expands context.
"""

from unittest.mock import MagicMock

from docker.errors import DockerException, NotFound

from modules.core.config import PurpleBoxConfig
from modules.core.docker_manager import DockerSandboxManager


def _mgr():
    mgr = DockerSandboxManager.__new__(DockerSandboxManager)
    mgr.config = PurpleBoxConfig(meta_api_key="k")
    mgr.session_id = "test-session"
    return mgr


def test_replace_target_transient_failure_keeps_tracked():
    mgr = _mgr()
    prev = MagicMock()
    prev.remove.side_effect = DockerException("transient 500")
    mgr.containers = [prev]
    newc = MagicMock()
    mgr.start_cloneable_target = MagicMock(return_value=(newc, "snap"))
    out = mgr.replace_target(prev, "snap", MagicMock(), MagicMock(), "src")
    assert out == (newc, "snap")
    assert prev in mgr.containers


def test_replace_target_notfound_still_untracks():
    mgr = _mgr()
    prev = MagicMock()
    prev.remove.side_effect = NotFound("gone")
    mgr.containers = [prev]
    mgr.start_cloneable_target = MagicMock(return_value=(MagicMock(), "snap"))
    mgr.replace_target(prev, "snap", MagicMock(), MagicMock(), "src")
    assert prev not in mgr.containers


def test_replace_target_clean_remove_still_untracks():
    mgr = _mgr()
    prev = MagicMock()
    mgr.containers = [prev]
    mgr.start_cloneable_target = MagicMock(return_value=(MagicMock(), "snap"))
    mgr.replace_target(prev, "snap", MagicMock(), MagicMock(), "src")
    prev.remove.assert_called_once_with(force=True)
    assert prev not in mgr.containers


def test_registry_utf8_fixtures_bounded_and_binary_elf_unreadable():
    import pytest

    from modules.core.registry import TARGETS_REGISTRY

    for key in ("node_query_sink", "node_chain_link", "php_command_sink", "mysql_insecure_conf"):
        target = TARGETS_REGISTRY[key]
        src = target.read_source()
        assert 0 < len(src.encode()) <= 65536
        assert isinstance(target.command, tuple)
    with pytest.raises(UnicodeDecodeError):
        TARGETS_REGISTRY["binary_argv_echo"].read_source()


def test_vault_keys_isolated_and_0600():
    import os
    import tempfile

    from modules.intel import sms_vault as V

    dir1, dir2 = tempfile.mkdtemp(), tempfile.mkdtemp()
    vault1, vault2 = os.path.join(dir1, "v1"), os.path.join(dir2, "v2")
    for vault in (vault1, vault2):
        V.commit_verified(
            namespace=V.VaultNamespace.RED,
            source="sink-same",
            payload={"kind": "boundary_escape", "fixture": "t"},
            vault_dir=vault,
        )
    key1 = open(os.path.join(vault1, "vault.key"), "rb").read()
    key2 = open(os.path.join(vault2, "vault.key"), "rb").read()
    assert key1 != key2
    assert oct(os.stat(os.path.join(vault1, "vault.key")).st_mode & 0o777) == "0o600"


def test_usage_accounting_sums():
    from modules.core.agents import CallUsage
    from modules.core.pricing import ScanUsage

    call = CallUsage(
        role="red",
        model="muse-spark-1.3",
        prompt_tokens=1000,
        completion_tokens=500,
        reasoning_tokens=100,
        seconds=2.0,
        cost_usd=0.001,
    )
    usage = ScanUsage(calls=[call])
    assert usage.total_tokens == 1500


def test_dockerfiles_pinned_and_chatter_capped():
    import pathlib

    for name in ("Dockerfile.target", "Dockerfile.verifier", "Dockerfile.binary"):
        assert "sha256:" in (pathlib.Path("docker") / name).read_text()
    from modules.services.chatter import chatter

    assert len(chatter("blue_done", persona="Bastion", path="app.js", code=0, seed=1)) <= 220


def test_compression_never_expands():
    from modules.shared.sms_compress import compress_context

    src = open("targets/node_query_sink/app.js", encoding="utf-8").read()
    report = compress_context(src, filename="app.js")
    assert report.compressed_tokens_sent <= report.raw_tokens_estimated
