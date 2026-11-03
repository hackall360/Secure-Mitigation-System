# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Parity wave W2 RED: ops visibility in the library API.

CLI-only today (``--docker-status``, ``--cleanup``, ``--health`` busy/image
state); this probes the library parities ``docker_health`` and
``cleanup_preview`` in ``modules.services.sms_api``. Docker client is always
a test double here — never the real daemon.
"""

from unittest.mock import MagicMock

from docker.errors import DockerException


def test_docker_health_reports_ready_shape():
    from modules.core.config import PurpleBoxConfig
    from modules.services.sms_api import docker_health

    client = MagicMock()
    client.containers.list.return_value = []
    report = docker_health(PurpleBoxConfig(), client=client)
    assert report["state"] == "ready"
    assert report["missing_images"] == []
    assert report["leftover_containers"] == 0


def test_docker_health_daemon_unreachable_fail_closed():
    from modules.core.config import PurpleBoxConfig
    from modules.services.sms_api import docker_health

    client = MagicMock()
    client.ping.side_effect = DockerException("down")
    report = docker_health(PurpleBoxConfig(), client=client)
    assert report["state"] == "unavailable"
    assert report["missing_images"] == []
    assert report["leftover_containers"] == 0


def test_cleanup_preview_lists_without_removing():
    from modules.core.config import PurpleBoxConfig
    from modules.services.sms_api import cleanup_preview

    client = MagicMock()
    container, network, snapshot = MagicMock(), MagicMock(), MagicMock()
    container.name = "sms-session-abc"
    container.id = "container-abc123"
    network.name = "sms-net-abc"
    network.id = "network-abc123"
    snapshot.id = "sha256:snapshot123"
    snapshot.tags = []
    client.containers.list.return_value = [container]
    client.networks.list.return_value = [network]
    client.images.list.return_value = [snapshot]

    preview = cleanup_preview(PurpleBoxConfig(), client=client)

    assert preview == {
        "containers": ["sms-session-abc"],
        "networks": ["sms-net-abc"],
        "images": ["sha256:snapshot123"],
    }
    client.containers.list.assert_called_once_with(all=True, filters={"label": "purplebox.session"})
    client.networks.list.assert_called_once_with(filters={"label": "purplebox.session"})
    # Dry-run: nothing removed.
    container.remove.assert_not_called()
    network.remove.assert_not_called()
    client.images.remove.assert_not_called()


def test_cleanup_preview_daemon_unreachable_fail_closed():
    from modules.core.config import PurpleBoxConfig
    from modules.services.sms_api import cleanup_preview

    client = MagicMock()
    client.containers.list.side_effect = DockerException("down")
    client.networks.list.side_effect = DockerException("down")
    client.images.list.side_effect = DockerException("down")
    preview = cleanup_preview(PurpleBoxConfig(), client=client)
    assert preview == {"containers": [], "networks": [], "images": []}
