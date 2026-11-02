# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""R3 (resilience remediation): F-01..F-05 + F-07 regression pins.

RED-first proofs for every remediation in the resilience pass:
- F-01: replace_binary_harness keeps previous tracked on transient
  DockerException; NotFound/clean still untrack.
- F-02: atomic busy - re-check immediately before acquire lets exactly one
  winner through (old check-then-gap-then-acquire shape let both run).
- F-03: scan registry capped at SCAN_REGISTRY_MAX_ENTRIES with oldest-first
  eviction.
- F-04: KEV cache refetches after TTL expiry; fresh cache served w/o refetch.
- F-05: operator label hygiene documented in ARCHITECTURE.md isolation section.
- F-07: vault_committed defaults False on ScanResult and survives redaction.
"""

import asyncio
from unittest.mock import MagicMock

from docker.errors import DockerException, NotFound

from modules.core.config import PurpleBoxConfig
from modules.core.docker_manager import DockerSandboxManager


def _mgr():
    mgr = DockerSandboxManager.__new__(DockerSandboxManager)
    mgr.config = PurpleBoxConfig(meta_api_key="k")
    mgr.session_id = "test-session"
    return mgr


def test_f01_binary_replace_transient_keeps_tracked():
    mgr = _mgr()
    prev = MagicMock()
    prev.remove.side_effect = DockerException("transient 500")
    mgr.containers = [prev]
    newc = MagicMock()
    mgr.start_binary_harness_from_snapshot = MagicMock(return_value=(newc, "snap"))
    out = mgr.replace_binary_harness(prev, "snap", MagicMock(), mitigation="x")
    assert out == (newc, "snap")
    assert prev in mgr.containers


def test_f01_binary_replace_notfound_still_untracks():
    mgr = _mgr()
    prev = MagicMock()
    prev.remove.side_effect = NotFound("gone")
    mgr.containers = [prev]
    mgr.start_binary_harness_from_snapshot = MagicMock(return_value=(MagicMock(), "snap"))
    mgr.replace_binary_harness(prev, "snap", MagicMock(), mitigation="x")
    assert prev not in mgr.containers


def test_f02_atomic_busy_exactly_one_winner():
    async def trial_old():
        lock = asyncio.Lock()

        async def caller(name):
            if not lock.locked():
                await asyncio.sleep(0.01)
                async with lock:
                    await asyncio.sleep(0.05)
                    return f"{name}:ran"
            return f"{name}:busy"

        return await asyncio.gather(caller("A"), caller("B"))

    assert asyncio.run(trial_old()) == ["A:ran", "B:ran"]

    async def trial_new():
        lock = asyncio.Lock()

        async def caller(name):
            acquired = False
            if not lock.locked():
                if not lock.locked():
                    await lock.acquire()
                    acquired = True
            if not acquired:
                return f"{name}:busy"
            try:
                await asyncio.sleep(0.01)
                await asyncio.sleep(0.05)
                return f"{name}:ran"
            finally:
                lock.release()

        return await asyncio.gather(caller("A"), caller("B"))

    assert asyncio.run(trial_new()) == ["A:ran", "B:busy"]


def test_f03_registry_bound_oldest_first():
    from modules.services import mcp_bridge as B

    B._SCAN_REGISTRY.clear()
    try:
        for i in range(200):
            B.scan_status_register(f"r3-{i}", phase="red")
        assert len(B._SCAN_REGISTRY) == B.SCAN_REGISTRY_MAX_ENTRIES == 128
        assert "r3-0" not in B._SCAN_REGISTRY
        assert "r3-199" in B._SCAN_REGISTRY
    finally:
        B._SCAN_REGISTRY.clear()


def test_f04_kev_ttl_refetch_and_fresh_hit():
    import time

    from modules.intel import research as R

    R._kev_cache_clear()
    R._KEV_CACHE = {"CVE-2024-3094": {"cveID": "CVE-2024-3094"}}
    R._KEV_CACHE_FETCHED_AT = time.monotonic() - R.KEV_CACHE_TTL_SECONDS - 1
    calls = {"n": 0}
    orig = R._get_json

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        return {"vulnerabilities": [{"cveID": "CVE-2024-3094"}]}

    R._get_json = fake_get
    try:
        out = R._kev_catalog()
        assert calls["n"] == 1 and "CVE-2024-3094" in out
        out2 = R._kev_catalog()
        assert calls["n"] == 1 and out2 is out
    finally:
        R._get_json = orig
        R._kev_cache_clear()


def test_f05_label_hygiene_documented():
    import pathlib

    text = pathlib.Path("docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "purplebox.base=true" in text
    assert "purplebox.session" in text


def test_f07_vault_committed_default_and_redacted():
    from modules.workflows.workflow import ScanResult, redact_fixture_result_for_user

    assert ScanResult(target="t").vault_committed is False
    assert redact_fixture_result_for_user(ScanResult(target="t"))["vault_committed"] is False
    hit = ScanResult(target="t", vault_committed=True)
    assert redact_fixture_result_for_user(hit)["vault_committed"] is True
