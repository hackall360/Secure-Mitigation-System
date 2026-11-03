"""RED-first tests for F-208 (sms_api config loading), F-218 (offline CVE), F-220 (redaction)."""

from __future__ import annotations

import asyncio

from library.core.config import ConfigurationError, PurpleBoxConfig
from library.services import sms_api
from library.shared import sms_observability as obs
from library.workflows import cve_workflow as cw


# ---- F-208 ------------------------------------------------------------------
def test_docker_health_uses_load_config(monkeypatch):
    sentinel = PurpleBoxConfig()
    seen = {}
    monkeypatch.setattr(sms_api, "load_config", lambda: sentinel, raising=False)
    import library.core.docker_manager as dm

    def fake_status(cfg, client=None):
        seen["cfg"] = cfg
        return {"state": "ok", "missing_images": [], "leftover_containers": 0}

    monkeypatch.setattr(dm, "docker_status", fake_status)
    out = sms_api.docker_health(client=object())
    assert seen["cfg"] is sentinel
    assert out["state"] == "ok"


def test_docker_health_config_error_degrades(monkeypatch):
    def boom():
        raise ConfigurationError("bad env")

    monkeypatch.setattr(sms_api, "load_config", boom, raising=False)
    out = sms_api.docker_health(client=object())
    assert out["state"] == "unavailable"
    assert out["missing_images"] == [] and out["leftover_containers"] == 0
    assert out["configuration_error"] is True


class _Lister:
    def __init__(self, items):
        self._items = items

    def list(self, **kw):
        self.kw = kw
        return self._items


class _Client:
    def __init__(self):
        self.containers = _Lister([])
        self.networks = _Lister([])
        self.images = _Lister([])


def test_cleanup_preview_uses_load_config(monkeypatch):
    sentinel = PurpleBoxConfig()
    object.__setattr__(sentinel, "clone_repo_prefix", "sentinel-prefix")
    monkeypatch.setattr(sms_api, "load_config", lambda: sentinel, raising=False)
    client = _Client()
    out = sms_api.cleanup_preview(client=client)
    assert client.images.kw == {"name": "sentinel-prefix"}
    assert out == {"containers": [], "networks": [], "images": []}


def test_cleanup_preview_config_error_degrades(monkeypatch):
    def boom():
        raise ConfigurationError("bad env")

    monkeypatch.setattr(sms_api, "load_config", boom, raising=False)
    out = sms_api.cleanup_preview(client=_Client())
    assert out["containers"] == [] and out["networks"] == [] and out["images"] == []
    assert out["configuration_error"] is True


# ---- F-218 ------------------------------------------------------------------
def _run_scan(monkeypatch, include_osv):
    calls = []
    monkeypatch.setattr(cw, "query_osv_batch", lambda deps: calls.append(deps) or {"results": []})
    logs = []

    async def emit(team, message):
        logs.append(message)

    files = {"requirements.txt": "jinja2==3.1.4\n", "app.py": "x = 1\n"}
    report = asyncio.run(
        cw.execute_cve_scan(files, emit, include_osv=include_osv, include_deep_assessment=False)
    )
    return report, logs, calls


def test_offline_cve_marks_report(monkeypatch):
    report, logs, calls = _run_scan(monkeypatch, False)
    assert calls == []
    assert report.osv_queried is False
    assert report.message.startswith("Offline (no OSV lookup): ")
    assert any("skipping OSV lookup (offline mode)" in str(m) for m in logs)


def test_live_cve_unchanged(monkeypatch):
    report, logs, calls = _run_scan(monkeypatch, True)
    assert calls
    assert report.osv_queried is True
    assert not report.message.startswith("Offline")
    assert not any("offline mode" in str(m) for m in logs)


# ---- F-220 ------------------------------------------------------------------
SECRET_VALUES = [
    "ghp_" + "a" * 36,
    "gho_" + "b" * 36,
    "ghs_" + "c" * 36,
    "github_pat_" + "d" * 30,
    "xoxb-1234567890-abcdef",
    "xoxp-1234567890-abcdef",
    "AKIAABCDEFGHIJKLMNOP",
    "ASIAABCDEFGHIJKLMNOP",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----",
]


def test_new_value_shapes_redacted():
    for v in SECRET_VALUES:
        assert obs._redact({"field": v}) == {"field": "REDACTED"}, v
        assert obs._redact(v) == "REDACTED", v


def test_new_key_names_redacted():
    for k in (
        "credential",
        "Cookie",
        "bearer",
        "private_key",
        "privatekey",
        "session_key",
        "X-API-Key",
        "passwd",
    ):
        assert obs._redact({k: "plainvalue"}) == {k: "REDACTED"}, k


def test_url_userinfo_redacted():
    out = obs._redact({"url": "https://alice:s3cr3t@example.com/repo.git"})
    assert out == {"url": "https://***@example.com/repo.git"}
    assert obs._redact("see postgres://u:p@db:5432/x now") == "see postgres://***@db:5432/x now"


def test_normal_values_kept():
    digest = "a" * 64
    rec = {"status": "verified", "rule": "node_query_sink", "script_sha256": digest}
    assert obs._redact(rec) == rec
    assert obs._redact("https://example.com/path") == "https://example.com/path"
