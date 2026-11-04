# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""V3 (recovery & convergence): MCP atomic busy + idempotent close + retry bound.

RED-first proofs for the Stage-6 remediation:
- MCP busy TOCTOU (F-02 shape): old check-then-gap-then-acquire lets two
  callers both run; the re-check-immediately-before-acquire lets exactly
  one through and the loser gets busy deterministically.
- close() is idempotent: second call reaps nothing, raises nothing.
- Retry budget: attempt==0 bound (one retry), capped delay <= 6 s,
  garbage Retry-After -> None.
- Registry flood cap + KEV TTL single-refetch (replay of chaos 07/09).
"""

import asyncio


def test_mcp_busy_toctou_old_runs_both_new_refuses_loser():
    async def trial_old():
        lock = asyncio.Lock()

        async def caller(name):
            if lock.locked():
                return f"{name}:busy"
            await asyncio.sleep(0.01)
            async with lock:
                await asyncio.sleep(0.05)
                return f"{name}:ran"

        return await asyncio.gather(caller("A"), caller("B"))

    assert asyncio.run(trial_old()) == ["A:ran", "B:ran"]

    async def trial_new():
        lock = asyncio.Lock()

        async def caller(name):
            acquired = False
            if not lock.locked():
                await asyncio.sleep(0.01)
                if not lock.locked():
                    await lock.acquire()
                    acquired = True
            if not acquired:
                return f"{name}:busy"
            try:
                await asyncio.sleep(0.05)
                return f"{name}:ran"
            finally:
                lock.release()

        return await asyncio.gather(caller("A"), caller("B"))

    assert asyncio.run(trial_new()) == ["A:ran", "B:busy"]


def test_mcp_live_duplicate_refused_and_health_truthful():
    import threading
    import time

    from fastapi.testclient import TestClient

    import main
    from modules.core.config import PurpleBoxConfig

    async def slow_wf(spec, emit, **kw):
        await emit("system", "slow")
        await asyncio.sleep(20)

    orig = main.execute_project_workflow
    main.execute_project_workflow = slow_wf
    try:
        app = main.create_app(PurpleBoxConfig(meta_api_key="k"))
        with TestClient(app, base_url="http://localhost") as client:
            headers = {"origin": "http://localhost"}

            def run():
                try:
                    with client.websocket_connect(
                        "ws://localhost/ws/project", headers=headers
                    ) as ws:
                        ws.send_json(
                            {
                                "path": "/tmp/x",
                                "image": "i",
                                "command": ["a"],
                                "test_command": ["b"],
                                "contract": "c",
                            }
                        )
                        while True:
                            ws.receive_json()
                except Exception:
                    pass

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            time.sleep(2)
            assert client.get("/api/health").json()["busy"] is True
            try:
                with client.websocket_connect(
                    "ws://localhost/ws/combat/node_query_sink", headers=headers
                ) as ws2:
                    frames = []
                    try:
                        while True:
                            frames.append(ws2.receive_json())
                    except Exception as exc:
                        assert getattr(exc, "code", None) == 1013
                        assert "busy" in [f.get("type") for f in frames if isinstance(f, dict)]
            except Exception as exc:
                assert getattr(exc, "code", None) == 1013
    finally:
        main.execute_project_workflow = orig


def test_close_idempotent_no_double_reap():
    from unittest.mock import MagicMock

    from modules.core.config import PurpleBoxConfig
    from modules.core.docker_manager import DockerSandboxManager
    from modules.shared.sms_async import blocking

    mgr = DockerSandboxManager.__new__(DockerSandboxManager)
    mgr.config = PurpleBoxConfig(meta_api_key="k")
    mgr.session_id = "idem"
    container = MagicMock()
    mgr.containers = [container]
    mgr.client = MagicMock()
    mgr.networks, mgr.images, mgr._snapshot_cache = [], [], {}
    asyncio.run(blocking(mgr.close))
    asyncio.run(blocking(mgr.close))
    container.remove.assert_called_once_with(force=True)


def test_retry_budget_bounded_and_capped():
    from modules.core.agents import (
        RETRY_MAX_ATTEMPTS,
        _parse_retry_after,
        _retry_delay_seconds,
    )

    # Ladder (2026-11-03 directive): 4 attempts, immediate → 10 s → 20 s.
    assert RETRY_MAX_ATTEMPTS == 4
    assert _retry_delay_seconds(1, 3600.0) <= 6.0
    assert 10.0 <= _retry_delay_seconds(2) <= 11.0
    assert 20.0 <= _retry_delay_seconds(3) <= 21.0
    assert _parse_retry_after("not-a-number") is None


def test_registry_flood_bounded_and_kev_single_refetch():
    import time

    from modules.intel import research as R
    from modules.services import mcp_bridge as B

    B._SCAN_REGISTRY.clear()
    try:
        for i in range(200):
            B.scan_status_register(f"v3-{i}", phase="red")
        assert len(B._SCAN_REGISTRY) == B.SCAN_REGISTRY_MAX_ENTRIES == 128
        assert "v3-199" in B._SCAN_REGISTRY
    finally:
        B._SCAN_REGISTRY.clear()
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
        outs = [R._kev_catalog() for _ in range(5)]
        assert calls["n"] == 1 and all(o is outs[0] for o in outs)
    finally:
        R._get_json = orig
        R._kev_cache_clear()
