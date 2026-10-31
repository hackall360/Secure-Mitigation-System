# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: env-gated schema-debug dump must write on fault, stay silent otherwise.

Covers the PURPLEBOX_LOG_RAW_RESPONSES block in modules/core/agents.py:
- enabled (existing dir): a schema-failing model response raises AgentError
  AND leaves exactly one schemadebug-<role>-*.txt file with ROLE/MODEL
  lines plus the cleaned and raw payloads, without leaking the API key.
- disabled (var unset): same fault raises AgentError with no file created.
"""

import glob
import os

import pytest


def _schema_failing_body():
    import json

    finding = json.dumps({"vulnerability_class": "only-this-field"})
    return {
        "choices": [
            {"finish_reason": "stop", "message": {"content": finding}},
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4},
    }


def _mock_client(monkeypatch, tmp_path):
    import httpx

    from modules.core.agents import MetaMuseClient
    from modules.core.config import PurpleBoxConfig

    def handle(request):
        return httpx.Response(200, json=_schema_failing_body())

    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    return MetaMuseClient(
        PurpleBoxConfig(meta_api_key="unit-test-key-debug-dump"),
        transport=httpx.MockTransport(handle),
    )


async def test_debug_dump_writes_file_on_schema_fault(tmp_path, monkeypatch):
    from modules.core.agents import AgentError

    debug_dir = tmp_path / "schemadebug"
    debug_dir.mkdir()
    monkeypatch.setenv("PURPLEBOX_LOG_RAW_RESPONSES", str(debug_dir))
    client = _mock_client(monkeypatch, tmp_path)
    try:
        with pytest.raises(AgentError, match="invalid JSON"):
            await client.run_red_team_analysis("app.js", "source")
        files = sorted(debug_dir.glob("schemadebug-*.txt"))
        assert len(files) == 1, [p.name for p in debug_dir.iterdir()]
        text = files[0].read_text()
        assert "MODEL=muse-spark" in text
        assert "ROLE=" in text
        assert "----- RAW -----" in text
        assert "vulnerability_class" in text
        assert "unit-test-key-debug-dump" not in text
    finally:
        await client.aclose()


async def test_debug_dump_missing_dir_fails_loud_not_tmp(tmp_path, monkeypatch):
    """LAW 10J: a set-but-missing dir must surface, never silently land in /tmp."""
    import tempfile

    from modules.core.agents import AgentError

    missing = tmp_path / "no-such-dir"
    monkeypatch.setenv("PURPLEBOX_LOG_RAW_RESPONSES", str(missing))
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "schemadebug-*")))
    client = _mock_client(monkeypatch, tmp_path)
    try:
        with pytest.raises(AgentError, match="missing directory"):
            await client.run_red_team_analysis("app.js", "source")
        assert not missing.exists(), "must not auto-create directories"
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "schemadebug-*")))
        assert after == before, "must not fall back to system tmp"
    finally:
        await client.aclose()


async def test_debug_dump_silent_when_var_unset(tmp_path, monkeypatch):
    from modules.core.agents import AgentError

    monkeypatch.delenv("PURPLEBOX_LOG_RAW_RESPONSES", raising=False)
    before = set(os.listdir(tmp_path))
    client = _mock_client(monkeypatch, tmp_path)
    try:
        with pytest.raises(AgentError, match="invalid JSON"):
            await client.run_red_team_analysis("app.js", "source")
        assert set(os.listdir(tmp_path)) == before
    finally:
        await client.aclose()
