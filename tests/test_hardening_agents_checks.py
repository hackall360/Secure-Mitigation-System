# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Hardening coverage: JSON fences/retry, verifier AST, Docker cache, patch/secret/context guards."""

import pytest

from agents import _extract_json_object
from checks import validate_verifier_script


def test_extract_json_strips_fences_and_preserves_braces_in_strings():
    fenced = '```json\n{"a": "x { not a boundary } y", "b": 1}\n```'
    assert _extract_json_object(fenced) == '{"a": "x { not a boundary } y", "b": 1}'
    padded = 'Sure, here is the result:\n{"x": 1, "s": "a}b"}\nDone.'
    assert _extract_json_object(padded) == '{"x": 1, "s": "a}b"}'
    plain = '  {"x": 1}  '
    assert _extract_json_object(plain) == '{"x": 1}'
    with pytest.raises(ValueError):
        _extract_json_object('{"a": 1}\x00')


def test_verifier_script_rejects_missing_exit_and_forbidden_imports():
    validate_verifier_script("import sys\nsys.exit(1)\n")
    validate_verifier_script("import sys\nraise SystemExit(0)\n")
    with pytest.raises(ValueError, match="explicitly call sys.exit"):
        validate_verifier_script("import sys\nprint('no exit')\n")
    with pytest.raises(ValueError, match="forbidden"):
        validate_verifier_script("import subprocess\nimport sys\nsys.exit(0)\n")
    with pytest.raises(ValueError, match="forbidden"):
        validate_verifier_script("import ctypes.util\nimport sys\nsys.exit(1)\n")
    with pytest.raises(ValueError, match="forbidden"):
        validate_verifier_script("__import__('subprocess')\nimport sys\nsys.exit(0)\n")
    with pytest.raises(ValueError, match="syntax"):
        validate_verifier_script("def broken(:\n")


async def test_fenced_json_parses_and_transient_429_retries_with_usage():
    import httpx

    from agents import MetaMuseClient, RedTeamFinding
    from config import PurpleBoxConfig

    finding = {
        "vulnerability_class": "input validation",
        "sink_location": "app.js:1",
        "analysis_summary": "An unexpected type reaches an expression.",
        "verification_script_python": "import sys\nsys.exit(0)\n",
    }
    import json

    calls = []

    def handle(request):
        calls.append(request)
        body = json.loads(request.content)
        assert body.get("temperature") == 0.1
        assert "reasoning_effort" not in body
        if len(calls) == 1:
            return httpx.Response(429, json={"usage": {"prompt_tokens": 1, "completion_tokens": 1}})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "```json\n" + json.dumps(finding) + "\n```"},
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 2},
            },
        )

    client = MetaMuseClient(
        PurpleBoxConfig(meta_api_key="unit-test-key"), transport=httpx.MockTransport(handle)
    )
    try:
        result = await client.run_red_team_analysis("app.js", "source")
        assert isinstance(result, RedTeamFinding)
        assert len(calls) == 2
        assert len(client.usage) == 2
        assert all(call.prompt_tokens >= 1 for call in client.usage)
    finally:
        await client.aclose()


async def test_schema_failure_records_usage_before_error():

    import httpx

    from agents import AgentError, MetaMuseClient
    from config import PurpleBoxConfig

    def handle(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "not json"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4},
            },
        )

    client = MetaMuseClient(
        PurpleBoxConfig(meta_api_key="unit-test-key"), transport=httpx.MockTransport(handle)
    )
    try:
        with __import__("pytest").raises(AgentError):
            await client.run_red_team_analysis("app.js", "source")
        assert len(client.usage) == 1
        assert client.usage[0].prompt_tokens == 3
    finally:
        await client.aclose()


def test_runner_forces_exit_two_without_explicit_exit(monkeypatch):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "verifier_runner_hardening", Path("docker/runner.py")
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner.runpy, "run_path", lambda *a, **k: None)
    assert runner.main() == 2


def test_docker_caches_snapshots_and_untracks_staging():
    from unittest.mock import MagicMock

    from config import PurpleBoxConfig
    from docker_manager import DockerSandboxManager

    client = MagicMock()
    stage = MagicMock()
    stage.put_archive.return_value = True
    stage.commit.return_value = MagicMock()
    client.containers.create.return_value = stage
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)
    first = manager._snapshot("base", "/workspace", "app.js", "import sys\nsys.exit(1)", "verifier")
    second = manager._snapshot(
        "base", "/workspace", "app.js", "import sys\nsys.exit(1)", "verifier"
    )
    assert first == second
    assert client.containers.create.call_count == 1
    assert stage not in manager.containers


def test_docker_options_contain_ulimits_and_ipc():
    from unittest.mock import MagicMock

    from config import PurpleBoxConfig
    from docker_manager import DockerSandboxManager

    manager = DockerSandboxManager(PurpleBoxConfig(), client=MagicMock())
    opts = manager._options("verifier")
    assert opts["ipc_mode"] == "none"
    assert any(getattr(u, "name", None) == "nofile" for u in opts["ulimits"])
    assert any(getattr(u, "name", None) == "core" for u in opts["ulimits"])


def test_replace_target_untracks_previous_container():
    from unittest.mock import MagicMock

    from config import PurpleBoxConfig
    from docker_manager import DockerSandboxManager

    client = MagicMock()
    manager = DockerSandboxManager(PurpleBoxConfig(), client=client)
    previous = MagicMock()
    manager.containers.append(previous)
    manager.start_cloneable_target = MagicMock(return_value=(MagicMock(), "snap"))
    manager.replace_target(
        previous,
        "snap",
        MagicMock(),
        MagicMock(command=["true"], filename="app.js", key="k"),
        "src",
    )
    previous.remove.assert_called_once_with(force=True)
    assert previous not in manager.containers


def test_validate_replacements_rejects_deep_guards():
    import hashlib

    from project_agents import BlueProposal, FileReplacement
    from project_workflow import validate_replacements

    def proposal(path, original, new, kind="input_validation"):
        return BlueProposal(
            strategy="test",
            replacements=[
                FileReplacement(
                    path=path,
                    original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                    replacement_content=new,
                    rationale="r",
                    change_kind=kind,
                )
            ],
            limitations=[],
        )

    current = {"a.py": "def keep(x):\n    return x\n"}
    # Delete function
    bad = proposal("a.py", current["a.py"], "x = 1\n")
    v, _ = validate_replacements(bad, current, max_changed_files=8, max_changed_bytes=100000)
    assert not v.accepted and "deleted function" in v.reason
    # Param change
    bad2 = proposal("a.py", current["a.py"], "def keep(x, y):\n    return x\n")
    v, _ = validate_replacements(bad2, current, max_changed_files=8, max_changed_bytes=100000)
    assert not v.accepted and "parameters" in v.reason
    # Dangerous sink
    bad3 = proposal("a.py", current["a.py"], "def keep(x):\n    return eval(x)\n")
    v, _ = validate_replacements(bad3, current, max_changed_files=8, max_changed_bytes=100000)
    assert not v.accepted and "forbidden sink" in v.reason
    # License strip
    lic = "# Required Notice: Copyright (c) 2026 hackall360\ndef keep(x):\n    return x\n"
    bad4 = proposal("a.py", lic, "def keep(x):\n    return x\n")
    v, _ = validate_replacements(bad4, {"a.py": lic}, max_changed_files=8, max_changed_bytes=100000)
    assert not v.accepted and "license" in v.reason.lower()
    # NUL and fences
    bad5 = proposal("a.py", current["a.py"], "def keep(x):\n    return x\n\x00")
    v, _ = validate_replacements(bad5, current, max_changed_files=8, max_changed_bytes=100000)
    assert not v.accepted
    fenced = proposal("a.py", current["a.py"], "```\ndef keep(x):\n    return x\n```")
    v, _ = validate_replacements(fenced, current, max_changed_files=8, max_changed_bytes=100000)
    assert not v.accepted and "fence" in v.reason.lower()
    # ratio guard
    big_orig = "\n".join(f"line{i}" for i in range(100))
    big_new = "\n".join(f"changed{i}" for i in range(100))
    v, _ = validate_replacements(
        proposal("b.txt", big_orig, big_new),
        {"b.txt": big_orig},
        max_changed_files=8,
        max_changed_bytes=1000000,
    )
    assert not v.accepted and "budget" in v.reason


def test_secret_content_scanner_and_skipped(tmp_path):
    from projects import ProjectSpec, _contains_secret_material, snapshot_project

    assert _contains_secret_material(b"-----BEGIN PRIVATE KEY-----\nabc")
    assert _contains_secret_material(b"key AKIAIOSFODNN7EXAMPLE here")
    assert _contains_secret_material(b"token ghp_" + b"a" * 36)
    assert _contains_secret_material(b"xoxb-123456789012 here")
    assert _contains_secret_material(b"sk_live_" + b"a" * 24)
    assert _contains_secret_material(b"sk-ant-" + b"a" * 20)
    assert not _contains_secret_material(b"hello world")
    (tmp_path / "ok.py").write_text("print(1)\n")
    (tmp_path / "leak.py").write_text("token = 'AKIAIOSFODNN7EXAMPLE'\n")
    spec = ProjectSpec.model_validate(
        {
            "path": str(tmp_path),
            "command": ["python3", "ok.py"],
            "test_command": ["python3", "-m", "unittest"],
            "contract": "x",
        }
    )
    snap = snapshot_project(spec)
    assert "leak.py" not in snap.files
    assert snap.skipped["leak.py"] == "secret or credential content pattern"
    assert "ok.py" in snap.files


def test_snapshot_context_prioritizes_source_over_docs(tmp_path):
    from project_workflow import ProjectWorkflowLimits, _snapshot_context
    from projects import ProjectSpec, snapshot_project

    for i in range(4):
        (tmp_path / f"doc{i}.md").write_text("x\n")
    (tmp_path / "app.py").write_text("print(1)\n")
    (tmp_path / "util.js").write_text("console.log(1)\n")
    spec = ProjectSpec.model_validate(
        {
            "path": str(tmp_path),
            "command": ["python3", "app.py"],
            "test_command": ["python3", "-m", "unittest"],
            "contract": "x",
        }
    )
    snap = snapshot_project(spec)
    safe, omitted, notes = _snapshot_context(
        spec, snap, ProjectWorkflowLimits(max_context_files=2, max_context_bytes=1000000)
    )
    assert set(safe.files) == {"app.py", "util.js"}
    assert all("doc" in p for p in omitted)
