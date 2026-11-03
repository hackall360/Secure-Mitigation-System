"""F-221: docker_status reports networks/images using the cleanup selectors."""

from types import SimpleNamespace

from docker.errors import APIError

from library.core import docker_manager as dm


class _Coll:
    def __init__(self, items, raises=False):
        self.items, self.raises, self.calls = items, raises, []

    def list(self, *args, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise APIError("boom")
        return list(self.items)


class _Images(_Coll):
    def get(self, tag):
        return object()

    def remove(self, **kwargs):
        pass


class _Item:
    def remove(self, **kwargs):
        pass


def _client(net_raises=False):
    return SimpleNamespace(
        ping=lambda: True,
        containers=_Coll([_Item(), _Item()]),
        networks=_Coll([_Item(), _Item(), _Item()], raises=net_raises),
        images=_Images([SimpleNamespace(id="sha1")]),
    )


def _cfg():
    return SimpleNamespace(
        target_base_image="t:1", verifier_base_image="v:1", clone_repo_prefix="purplebox-snap"
    )


def test_status_counts_all_three_with_cleanup_selectors():
    status_client, sweep_client = _client(), _client()
    status = dm.docker_status(_cfg(), client=status_client)
    assert status["state"] == "ready"
    assert status["leftover_containers"] == 2
    assert status["leftover_networks"] == 3
    assert status["leftover_images"] == 1
    dm.remove_stale_resources(_cfg(), client=sweep_client)
    for attr in ("containers", "networks", "images"):
        assert getattr(status_client, attr).calls == getattr(sweep_client, attr).calls


def test_network_listing_failure_reports_none_rest_intact():
    status = dm.docker_status(_cfg(), client=_client(net_raises=True))
    assert status["state"] == "ready"
    assert status["leftover_networks"] is None
    assert status["leftover_containers"] == 2
    assert status["leftover_images"] == 1


def test_unavailable_keeps_keys():
    def boom():
        raise APIError("down")

    client = _client()
    client.ping = boom
    status = dm.docker_status(_cfg(), client=client)
    assert status["state"] == "unavailable"
    assert status["leftover_containers"] == 0
    assert "leftover_networks" in status and "leftover_images" in status
