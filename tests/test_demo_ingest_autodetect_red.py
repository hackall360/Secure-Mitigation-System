# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): WS ingest auto-detects runtime from the cloned tree.

Found live 2026-11-03 (Part 2 dry run): the console sent an ingest frame
with repo URL + contract but no runtime_command and no file_list. The
server refused: "runtime_command is required when file_list is not given."
The form never asked for either — the server demanded what the UI never
collected.

Fix contract: with no explicit argv and no file_list, the server clones
with a placeholder then resolves the real runtime from the cloned tree
via detect_runtime (same derivation the library path uses) — rather than
refusing a frame the UI cannot fully populate. Undetectable trees still
fail closed (explicit argv required). Explicit runtime_command and
file_list paths are unchanged.
"""

from __future__ import annotations

from types import MappingProxyType, SimpleNamespace

from fastapi.testclient import TestClient

import main
from library.core.config import PurpleBoxConfig


def _canned_snapshot(runtime=("python3", "anycam.py")):
    return SimpleNamespace(
        files=MappingProxyType(
            {
                "repo.url": b"https://github.com/hackall360/AnyCam.git",
                "repo.commit_hash": b"a" * 40,
                "repo.runtime_command": b'["true"]',
                "tree/anycam.py": b"print('hi')\n",
                "tree/main.py": b"print('hi')\n",
                "tree/requirements.txt": b"",
            }
        ),
        url="https://github.com/hackall360/AnyCam.git",
        commit_hash="a" * 40,
        runtime_command=("true",),
        digest="fake",
    )


def test_ingest_without_runtime_auto_detects_from_cloned_tree(monkeypatch):
    """No runtime_command + no file_list: clone, detect, workflow runs."""
    seen = {}

    def fake_intake(spec, runtime_command=None, **kwargs):
        assert kwargs.get("clone") is True
        assert runtime_command == ["true"], f"placeholder clone, got {runtime_command}"
        return _canned_snapshot()

    async def workflow(project_input, emit, **kwargs):
        seen["ran"] = True
        seen["regression"] = list(project_input.regression_command)

        class _R:
            def model_dump(self, mode="json"):
                return {
                    "target": "x",
                    "status": "verified",
                    "message": "ok",
                    "diff": "",
                    "cleanup_ok": True,
                    "cycles": [],
                    "total_tokens": 0,
                    "cost_usd": None,
                }

        return _R()

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        from tests.test_w22_ingest_wire_red import connect, drain_snapshot

        with connect(client) as socket:
            socket.send_json({"ingest_repo": "https://github.com/hackall360/AnyCam.git"})
            reply = drain_snapshot(socket)
            assert reply.get("type") != "invalid", f"auto-detect refused: {reply}"
    assert seen.get("ran") is True
    assert seen["regression"] == ["python3", "main.py"], (
        f"runtime must resolve from cloned tree, got {seen.get('regression')}"
    )


def test_ingest_explicit_runtime_still_wins(monkeypatch):
    """Explicit runtime_command bypasses auto-detect (unchanged path)."""
    seen = {}

    def fake_intake(spec, runtime_command=None, **kwargs):
        seen["argv"] = list(runtime_command) if runtime_command else None
        return _canned_snapshot(runtime=tuple(seen["argv"]))

    async def workflow(*args, **kwargs):
        seen["ran"] = True

        class _R:
            def model_dump(self, mode="json"):
                return {
                    "target": "x",
                    "status": "verified",
                    "message": "ok",
                    "diff": "",
                    "cleanup_ok": True,
                    "cycles": [],
                    "total_tokens": 0,
                    "cost_usd": None,
                }

        return _R()

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        from tests.test_w22_ingest_wire_red import connect, drain_snapshot

        with connect(client) as socket:
            socket.send_json(
                {
                    "ingest_repo": "https://github.com/hackall360/AnyCam.git",
                    "runtime_command": ["python3", "-m", "http.server"],
                }
            )
            reply = drain_snapshot(socket)
            assert reply.get("type") != "invalid", f"explicit argv refused: {reply}"
    assert seen.get("ran") is True
    assert seen["argv"] == ["python3", "-m", "http.server"]
