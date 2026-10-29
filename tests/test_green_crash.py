# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Green-build crash regressions: generation failures return a result card, never a dead socket."""

import asyncio


def _run(coro):
    return asyncio.run(coro)


def test_demo_build_returns_error_card_when_client_construction_fails(monkeypatch):
    """Missing/bad key config surfaces as an error result, not a raised crash."""
    import main as _main
    import modules.core.agents as _agents
    from modules.core.config import ConfigurationError, PurpleBoxConfig

    class RaisingClient:
        def __init__(self, config):
            raise ConfigurationError("META_MUSE_API_KEY is required for scans.")

    monkeypatch.setattr(_agents, "MetaMuseClient", RaisingClient)
    seen = []

    async def emit(team, msg):
        seen.append((team, msg))

    result = _run(
        _main.run_demo_build(
            emit, PurpleBoxConfig(meta_api_key="k"), theme="xss", intel_offline=True
        )
    )
    assert result["status"] == "error"
    assert "Demo generation failed" in result["message"]
    assert result["cleanup_ok"] is True
    assert any(team == "green" for team, _ in seen)


def test_demo_build_returns_error_card_when_generation_is_invalid(monkeypatch):
    """Muse returning syntactically broken app.py yields an error card, not SyntaxError."""
    import main as _main
    import modules.core.agents as _agents
    import modules.services.demo_gen as _dg
    from modules.core.config import PurpleBoxConfig

    class FakeClient:
        def __init__(self, config):
            self.config = config

        async def aclose(self):
            pass

    async def fake_generate(client, **kwargs):
        return _dg.DemoProjectFiles(
            app_py="def broken(:\n  pass(\n",
            test_contract_py="print('ok')\n",
            contract="demo contract",
            flaw_notes=["SQL injection at /q via string concat"],
            cve_inspiration=["CVE-2024-3094"],
        )

    monkeypatch.setattr(_agents, "MetaMuseClient", FakeClient)
    monkeypatch.setattr(_dg, "generate_demo_project", fake_generate)
    seen = []

    async def emit(team, msg):
        seen.append((team, msg))

    result = _run(
        _main.run_demo_build(
            emit, PurpleBoxConfig(meta_api_key="k"), theme="xss", intel_offline=True
        )
    )
    assert result["status"] == "error"
    assert "Demo generation failed" in result["message"]
    assert "app.py" in result["message"]
    assert any(team == "green" for team, _ in seen)


def test_generate_demo_project_rejects_invalid_syntax():
    """Fail-fast boundary: broken Muse output raises ValueError naming the file."""
    import pytest as _pytest

    import modules.services.demo_gen as _dg

    class FakeClient:
        config = type("C", (), {"red_team_model": "muse-spark-1.3"})()

        async def _request(self, model, system, payload, schema, **kwargs):
            return _dg.DemoProjectFiles(
                app_py="x = 1\n",
                test_contract_py="def broken(:\n",
                contract="c",
                flaw_notes=["SQL injection at /q"],
                cve_inspiration=["CVE-2024-3094"],
            )

    with _pytest.raises(ValueError, match="test_contract.py"):
        _run(_dg.generate_demo_project(FakeClient(), intel_context=[], theme="t"))


def test_materialize_demo_project_names_invalid_file(tmp_path):
    """Materialize names the broken file in a ValueError, never leaks SyntaxError."""
    import pytest as _pytest

    from modules.services.demo_gen import DemoProjectFiles, materialize_demo_project

    bad = DemoProjectFiles(
        app_py="def broken(:\n",
        test_contract_py="print('ok')\n",
        contract="demo contract",
    )
    with _pytest.raises(ValueError, match="app.py"):
        materialize_demo_project(bad, dest_dir=str(tmp_path / "bad"))
