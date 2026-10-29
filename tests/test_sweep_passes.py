# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first 3-pass sweep tests (Milestone 3).

The sweep controller runs standard → deep → threat-actor passes over the
same sandboxed target, never stopping at the first finding. Blue answers
each confirmed pass with a minimal guarded patch; Docker exit codes decide
every pass verdict, fail-closed.
RED until modules/workflows/sweep.py lands.
"""

from modules.core.config import PurpleBoxConfig
from tests.helpers import FakeFixtureSandbox, silent_emit

TEST_CONFIG = PurpleBoxConfig(meta_api_key="test-key")


class SweepFakeMuse:
    """Red double returning one finding per pass; blue double counts patches."""

    def __init__(self):
        self.red_calls: list = []
        self.blue_calls = 0
        self.closed = False

    async def run_red_team_pass_analysis(self, pass_id, filename, source, contract=""):
        from modules.core.agents import RedTeamFinding

        self.red_calls.append(pass_id)
        return RedTeamFinding(
            vulnerability_class=f"test boundary {pass_id}",
            sink_location=filename,
            analysis_summary="Test-only injected agent.",
            verification_script_python="import sys\nsys.exit(0)",
        )

    async def run_blue_team_sanitizer(
        self, filename, source_code, finding=None, evidence="", contract=""
    ):
        from modules.core.agents import BlueTeamPatch

        self.blue_calls += 1
        # Patch the CURRENT source (carrying prior passes' patches) with a
        # distinct per-call guard comment, so each pass diff is non-empty
        # and the 60-line budget holds.
        patched = source_code.rstrip("\n") + f"\n// sweep-guard-{self.blue_calls}\n"
        return BlueTeamPatch(
            sanitization_strategy="Validate IDs",
            diff_summary="Add a guard",
            patched_file_content=patched,
        )

    async def aclose(self):
        self.closed = True


def _run_sweep(codes, muse=None):
    from modules.workflows.sweep import execute_sweep_scan

    sandbox = FakeFixtureSandbox(codes)
    muse = muse or SweepFakeMuse()
    return execute_sweep_scan(
        "node_query_sink",
        silent_emit,
        config=TEST_CONFIG,
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: muse,
    )


def test_sweep_pass_ids_ordered():
    from modules.workflows.sweep import SWEEP_PASSES

    assert tuple(SWEEP_PASSES) == ("standard", "deep", "threat_actor")


def test_sweep_runs_all_three_passes_when_first_confirms():
    """P1 exit 0 must not stop P2/P3; every pass gets a red call."""
    import asyncio

    # baseline 0, then per pass: pre, regression, post, final-health
    codes = [0] + [0, 0, 1, 0] * 3
    result = asyncio.new_event_loop().run_until_complete(_run_tracker(codes))
    assert result.pass_results[0].pass_id == "standard"
    assert result.pass_results[1].pass_id == "deep"
    assert result.pass_results[2].pass_id == "threat_actor"


async def _run_tracker(codes):
    from modules.workflows.sweep import execute_sweep_scan

    sandbox = FakeFixtureSandbox(codes)
    muse = SweepFakeMuse()
    result = await execute_sweep_scan(
        "node_query_sink",
        silent_emit,
        config=TEST_CONFIG,
        sandbox_factory=lambda settings: sandbox,
        muse_factory=lambda settings: muse,
    )
    assert muse.red_calls == ["standard", "deep", "threat_actor"]
    assert muse.blue_calls == 3
    return result


def test_sweep_verified_only_when_every_pass_holds():
    import asyncio

    codes = [0] + [0, 0, 1, 0] * 3
    result = asyncio.new_event_loop().run_until_complete(_run_tracker(codes))
    assert result.status == "verified"
    assert result.cleanup_ok is True
    assert len(result.pass_results) == 3
    assert all(p.receipt is not None for p in result.pass_results)


def test_sweep_clear_pass_needs_no_blue_patch():
    """A pass whose probe exits 1 is clear: no blue call, still verified."""

    class MixedMuse(SweepFakeMuse):
        pass

    import asyncio

    async def go():
        from modules.workflows.sweep import execute_sweep_scan

        # P1 confirms (0,0,1,0); P2 clear: pre exits 1, no blue/regression;
        # P3 confirms (0,0,1,0).
        sandbox = FakeFixtureSandbox([0, 0, 0, 1, 0, 1, 0, 0, 1, 0])
        muse = SweepFakeMuse()
        result = await execute_sweep_scan(
            "node_query_sink",
            silent_emit,
            config=TEST_CONFIG,
            sandbox_factory=lambda settings: sandbox,
            muse_factory=lambda settings: muse,
        )
        assert muse.red_calls == ["standard", "deep", "threat_actor"]
        assert muse.blue_calls == 2
        return result

    result = asyncio.new_event_loop().run_until_complete(go())
    assert result.status == "verified"


def test_sweep_inconclusive_probe_fails_closed():
    import asyncio

    async def go():
        from modules.workflows.sweep import execute_sweep_scan

        sandbox = FakeFixtureSandbox([0, 2])
        muse = SweepFakeMuse()
        return await execute_sweep_scan(
            "node_query_sink",
            silent_emit,
            config=TEST_CONFIG,
            sandbox_factory=lambda settings: sandbox,
            muse_factory=lambda settings: muse,
        )

    result = asyncio.new_event_loop().run_until_complete(go())
    assert result.status == "error"
    assert result.cleanup_ok is True


def test_sweep_cli_flag_reaches_controller(monkeypatch):
    """M3 CLI parity: --sweep-passes threads into execute_sweep_scan."""
    import main as _main

    seen = {}

    async def fake_sweep(target_key, emit, **kwargs):
        seen.update(kwargs)
        from modules.workflows.sweep import SweepScanResult

        return SweepScanResult(target=target_key, status="verified", message="ok")

    monkeypatch.setattr(_main, "execute_sweep_scan", fake_sweep)
    monkeypatch.setattr("sys.argv", ["main.py", "--scan", "node_query_sink", "--sweep-passes", "2"])
    assert _main.main() == 0
    assert seen.get("max_passes") == 2


def test_sweep_dashboard_controls_exist():
    """M3 dashboard parity: sweep pass selector + per-pass stage rows render."""
    from html.parser import HTMLParser
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[1]

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = set()

        def handle_starttag(self, tag, attrs):
            found = dict(attrs).get("id")
            if found:
                self.ids.add(found)

    parser = Elements()
    parser.feed((root / "static/index.html").read_text())
    for control in ("sweep-passes", "pipeline"):
        assert control in parser.ids, control


def test_sweep_ws_query_param_reaches_controller(monkeypatch):
    """M3 WS parity: ?sweep_passes=2 routes to execute_sweep_scan."""
    from fastapi.testclient import TestClient

    import main as _main
    from modules.core.config import PurpleBoxConfig

    seen = {}

    async def fake_sweep(target_key, emit, **kwargs):
        seen.update(kwargs)
        from modules.workflows.sweep import SweepScanResult

        return SweepScanResult(target=target_key, status="verified", message="ok")

    monkeypatch.setattr(_main, "execute_sweep_scan", fake_sweep)
    with TestClient(
        _main.create_app(PurpleBoxConfig(meta_api_key="k")), base_url="http://localhost"
    ) as client:
        with client.websocket_connect(
            "ws://localhost/ws/combat/node_query_sink?sweep_passes=2",
            headers={"origin": "http://localhost"},
        ) as socket:
            while True:
                event = socket.receive_json()
                if event["type"] == "result":
                    assert event["status"] == "verified"
                    break
    assert seen.get("max_passes") == 2


def test_sweep_ws_rejects_bad_depth(monkeypatch):
    """M3 WS parity: ?sweep_passes=9 refuses before Docker work."""
    from fastapi.testclient import TestClient

    import main as _main
    from modules.core.config import PurpleBoxConfig

    with TestClient(
        _main.create_app(PurpleBoxConfig(meta_api_key="k")), base_url="http://localhost"
    ) as client:
        import pytest as _pytest
        from starlette.websockets import WebSocketDisconnect as _WSD

        with _pytest.raises(_WSD):
            with client.websocket_connect(
                "ws://localhost/ws/combat/node_query_sink?sweep_passes=9",
                headers={"origin": "http://localhost"},
            ) as socket:
                socket.receive_json()
