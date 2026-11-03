# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED-FIRST parity W3: CLI --show-intel / --vault-list / --vault-replay.

No Docker, no network, no Muse key: vault tests seed a tmp vault via
commit_verified; the scan test fakes execute_purple_workflow with a real
ScanResult carrying canned research_records.
"""

import sys

import pytest

import main


def _seed(vault_dir, namespace: str = "red") -> str:
    from modules.intel import sms_vault as vault

    return vault.commit_verified(
        namespace=vault.VaultNamespace(namespace),
        source="query($q) { user(id: $q) { name } }",
        payload={"kind": "probe-shape", "secret_blob": "SECRET-MARKER-XYZ"},
        vault_dir=vault_dir,
    )


def test_help_mentions_all_three_flags():
    help_text = main.build_parser().format_help()
    assert "--show-intel" in help_text
    assert "--vault-list" in help_text
    assert "--vault-replay" in help_text


def test_vault_list_prints_seeded_namespaces(tmp_path, monkeypatch, capsys):
    vault_dir = tmp_path / "vault"
    _seed(vault_dir, "red")
    _seed(vault_dir, "blue")
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(vault_dir))
    monkeypatch.setattr(sys, "argv", ["main.py", "--vault-list"])
    assert main.main() == 0
    out = capsys.readouterr().out
    assert "red" in out
    assert "blue" in out


def test_vault_list_empty_vault_succeeds(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "empty"))
    monkeypatch.setattr(sys, "argv", ["main.py", "--vault-list"])
    assert main.main() == 0


def test_vault_replay_bad_id_fail_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setattr(sys, "argv", ["main.py", "--vault-replay", "red:not-an-id"])
    assert main.main() == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err


def test_vault_replay_unknown_namespace_fail_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setattr(sys, "argv", ["main.py", "--vault-replay", "purple:" + "f" * 32])
    assert main.main() == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err


def test_vault_replay_round_trip_redacted(tmp_path, monkeypatch, capsys):
    vault_dir = tmp_path / "vault"
    record_id = _seed(vault_dir, "red")
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(vault_dir))
    monkeypatch.setattr(sys, "argv", ["main.py", "--vault-replay", f"red:{record_id}"])
    assert main.main() == 0
    out = capsys.readouterr().out
    assert record_id in out
    assert "SECRET-MARKER-XYZ" not in out


def test_show_intel_requires_scan(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--vault-list", "--show-intel"])
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2


def test_show_intel_prints_provenance_after_scan(monkeypatch, capsys):
    from library.workflows.workflow import ScanResult

    records = [
        {
            "source": "osv",
            "cve_id": "CVE-2024-1234",
            "summary": "A buffer overflow in example-lib allows remote code execution.",
            "extra": {"epss": "0.85"},
        }
    ]

    async def fake(target_key, emit, config=None, **kwargs):
        return ScanResult(
            target=target_key,
            status="verified",
            message="Probe blocked",
            pre_exit_code=0,
            post_exit_code=1,
            baseline_passed=True,
            regression_passed=True,
            research_records=records,
        )

    monkeypatch.setattr(main, "execute_purple_workflow", fake)
    monkeypatch.setattr(sys, "argv", ["main.py", "--scan", "node_query_sink", "--show-intel"])
    assert main.main() == 0
    out = capsys.readouterr().out
    assert "CVE-2024-1234" in out
