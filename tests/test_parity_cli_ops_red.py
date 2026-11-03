# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Parity wave W3 RED: unified CLI ops surface.

``--ops-status`` (docker state + missing images + leftovers + effective
knobs + showcase presence, one table/JSON) and ``--cleanup-dry-run`` (what
``--cleanup`` WOULD remove; removes nothing). Never touches the real
Docker daemon: docker-touching library calls are monkeypatched on
``main`` (same pattern as existing CLI parity tests).
"""

import json
from unittest.mock import MagicMock

import main
from modules.core.config import PurpleBoxConfig


def _ready_docker():
    return {"state": "ready", "missing_images": [], "leftover_containers": 0}


def _patch_ops_fakes(monkeypatch):
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr(main, "docker_health", lambda settings: _ready_docker())
    monkeypatch.setattr(
        main,
        "cleanup_preview",
        lambda settings: {"containers": [], "networks": [], "images": []},
    )
    monkeypatch.setattr(
        main,
        "effective_knobs",
        lambda settings: {
            "timeout_seconds": 60,
            "max_tokens": 4096,
            "reasoning_effort": "medium",
            "verifier_timeout": 120,
            "research_scanners": [],
        },
    )
    monkeypatch.setattr(
        main,
        "showcase_status",
        lambda: {"tts": {"present": True}, "capture": {"present": False}},
    )


def test_help_lists_ops_status_and_cleanup_dry_run():
    text = main.build_parser().format_help()
    assert "--ops-status" in text
    assert "--cleanup-dry-run" in text


def test_ops_status_prints_all_five_sections(monkeypatch, capsys):
    _patch_ops_fakes(monkeypatch)
    monkeypatch.setattr("sys.argv", ["main.py", "--ops-status"])
    assert main.main() == 0
    out = capsys.readouterr().out.lower()
    assert "docker" in out
    assert "missing images" in out
    assert "leftover" in out
    assert "knob" in out
    assert "showcase" in out


def test_ops_status_json_shape(monkeypatch, capsys):
    _patch_ops_fakes(monkeypatch)
    monkeypatch.setattr("sys.argv", ["main.py", "--ops-status", "--format", "json"])
    assert main.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert {"docker", "cleanup_preview", "knobs", "showcase"} <= set(payload)
    assert payload["docker"]["state"] == "ready"
    assert payload["docker"]["missing_images"] == []
    assert payload["docker"]["leftover_containers"] == 0


def test_cleanup_dry_run_removes_nothing(monkeypatch, capsys):
    from modules.services import sms_api

    client = MagicMock()
    container, network, snapshot = MagicMock(), MagicMock(), MagicMock()
    container.name = "sms-session-abc"
    container.id = "container-abc123"
    network.name = "sms-net-abc"
    network.id = "network-abc123"
    snapshot.id = "sha256:snapshot123"
    client.containers.list.return_value = [container]
    client.networks.list.return_value = [network]
    client.images.list.return_value = [snapshot]

    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    monkeypatch.setattr(main, "docker_health", lambda settings: _ready_docker())
    monkeypatch.setattr(
        main, "cleanup_preview", lambda settings: sms_api.cleanup_preview(settings, client=client)
    )

    def _bomb(settings, **kwargs):
        raise AssertionError("--cleanup-dry-run must never call remove_stale_resources")

    monkeypatch.setattr(main, "remove_stale_resources", _bomb)
    monkeypatch.setattr("sys.argv", ["main.py", "--cleanup-dry-run"])
    assert main.main() == 0
    out = capsys.readouterr().out
    assert "sms-session-abc" in out
    # Dry-run: nothing removed; fakes still present afterwards.
    container.remove.assert_not_called()
    network.remove.assert_not_called()
    client.images.remove.assert_not_called()
    assert client.containers.list(all=True, filters={"label": "purplebox.session"}) == [container]
    assert client.networks.list(filters={"label": "purplebox.session"}) == [network]


def test_ops_status_daemon_unreachable_fail_closed(monkeypatch, capsys):
    _patch_ops_fakes(monkeypatch)
    monkeypatch.setattr(
        main,
        "docker_health",
        lambda settings: {"state": "unavailable", "missing_images": [], "leftover_containers": 0},
    )
    monkeypatch.setattr("sys.argv", ["main.py", "--ops-status"])
    assert main.main() == 1
    captured = capsys.readouterr()
    assert "unreachable" in captured.err.lower() or "unavailable" in captured.out.lower()


def test_cleanup_dry_run_daemon_unreachable_fail_closed(monkeypatch, capsys):
    _patch_ops_fakes(monkeypatch)
    monkeypatch.setattr(
        main,
        "docker_health",
        lambda settings: {"state": "unavailable", "missing_images": [], "leftover_containers": 0},
    )
    monkeypatch.setattr("sys.argv", ["main.py", "--cleanup-dry-run"])
    assert main.main() == 1
    assert "unreachable" in capsys.readouterr().err.lower()
