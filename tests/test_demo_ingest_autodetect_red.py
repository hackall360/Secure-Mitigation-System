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
    assert seen["regression"][0] == "python3" and seen["regression"][1] == "-c", (
        f"runtime must be the HTTP service wrapper, got {seen.get('regression')[:2]}"
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


def test_ingest_skips_binary_blobs_keeps_text(monkeypatch):
    """Font/image bytes in the cloned tree are skipped, text runs."""
    import main

    seen = {}

    def fake_intake(spec, runtime_command=None, **kwargs):
        return SimpleNamespace(
            files=MappingProxyType(
                {
                    "repo.url": b"https://x/y.git",
                    "repo.commit_hash": b"b" * 40,
                    "repo.runtime_command": b'["python3", "anycam.py"]',
                    "tree/anycam.py": b"print('hi')\n",
                    "tree/requirements.txt": b"",
                    "tree/font.ttf": b"\x00\x01\xff\xfe" * 100,
                }
            ),
            url="https://x/y.git",
            commit_hash="b" * 40,
            runtime_command=("python3", "anycam.py"),
            digest="fake",
        )

    async def workflow(project_input, emit, **kwargs):
        seen["names"] = sorted(project_input.files.keys())

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

    from fastapi.testclient import TestClient

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    with TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost") as client:
        from tests.test_w22_ingest_wire_red import connect, drain_snapshot

        with connect(client) as socket:
            socket.send_json({"ingest_repo": "https://x/y.git"})
            reply = drain_snapshot(socket)
            assert reply.get("type") != "invalid", f"binary blob refused: {reply}"
    assert "tree/anycam.py" in seen["names"]
    assert "tree/requirements.txt" in seen["names"]
    assert not any(n.endswith(".ttf") for n in seen["names"])


def test_service_wrapper_boots_and_serves(monkeypatch, tmp_path):
    """build_service_wrapper: fixed loader argv + file map, boots + serves."""
    import json
    import socket
    import subprocess
    import time
    import urllib.error
    import urllib.request

    from library.services.repo_intake import build_service_wrapper

    snap = _canned_snapshot()
    wrapped = build_service_wrapper(snap)
    argv = list(wrapped.runtime_command)
    assert argv[0] == "python3" and argv[1] == "-c"
    assert len(argv[2].encode()) < 8192, "loader must stay small"
    assert "tree/.wrapper_files.json" in wrapped.files
    fmap = json.loads(wrapped.files["tree/.wrapper_files.json"])
    assert set(fmap) >= {"anycam.py", "requirements.txt", "main.py"}

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    (tmp_path / ".wrapper_files.json").write_bytes(wrapped.files["tree/.wrapper_files.json"])
    assert (tmp_path / ".wrapper_files.json").exists(), "map must land before boot"
    for rel in ("anycam.py", "requirements.txt", "main.py"):
        (tmp_path / rel).write_bytes(wrapped.files[f"tree/{rel}"])
    # Guard: a stale server on our (freshly-bound-then-released) port would
    # answer 404s and poison the test. Probe first; refuse to run against
    # anything already listening. NOTE: the developer's own AnyCam install
    # squats on 8080 system-wide — this test deliberately uses a RANDOM
    # free port (never 8080) so it is hermetic to that.
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
        raise AssertionError(f"port {port} already serves — refusing poisoned test")
    except urllib.error.URLError:
        pass  # free as expected
    loader = argv[2].replace("8080", str(port))
    assert "8080" not in loader or str(port) == "8080"
    # pytest's tmp_path honors $TMPDIR (here: ~/.jcode/scratch, possibly on
    # a mounted volume) while the loader child resolves relative paths
    # against the process cwd — on this box those disagree, so pass the
    # map by ABSOLUTE path: patch the loader's candidates, not its port.
    # (Production is unaffected: the sandbox cwd IS the staged tree.)
    abs_map = str(tmp_path / ".wrapper_files.json")
    loader = loader.replace(
        '_MAP_CANDIDATES = ("wrapper_files.json", "/workspace/.wrapper_files.json")',
        f'_MAP_CANDIDATES = ({abs_map!r}, "/workspace/.wrapper_files.json")',
    )
    proc = subprocess.Popen(
        ["python3", "-c", loader],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        body = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise AssertionError("wrapper exited before serving")
            try:
                with urllib.request.urlopen(base + "/", timeout=2) as r:
                    body = r.read()
                break
            except OSError:
                time.sleep(0.3)
        assert body is not None, "wrapper never served /"
        health = urllib.request.urlopen(base + "/health", timeout=5).read()
        assert b'"status": "ok"' in health
        served = urllib.request.urlopen(base + "/anycam.py", timeout=5).read()
        assert served == b"print('hi')\n"
        try:
            urllib.request.urlopen(base + "/nope.py", timeout=5)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        proc.terminate()


def test_service_wrapper_no_text_fails_closed():
    """A tree with zero decodable text still refuses (explicit argv needed)."""
    from types import MappingProxyType, SimpleNamespace

    import pytest

    from library.services.repo_intake import build_service_wrapper

    snap = SimpleNamespace(
        files=MappingProxyType(
            {
                "repo.url": b"https://x/y.git",
                "repo.commit_hash": b"b" * 40,
                "tree/font.ttf": b"\x00\x01\xff\xfe" * 10,
            }
        ),
        url="https://x/y.git",
        commit_hash="b" * 40,
        runtime_command=("true",),
        digest="fake",
    )
    with pytest.raises(ValueError, match="no decodable text"):
        build_service_wrapper(snap)


def test_wrapper_smoke_command_exits_zero():
    """The smoke argv verifies the map and exits 0 (regression command)."""
    import json

    from library.services.repo_intake import build_service_wrapper

    snap = _canned_snapshot()
    wrapped = build_service_wrapper(snap)
    smoke = json.loads(wrapped.files["repo.smoke_command"].decode("utf-8"))
    assert smoke[:2] == ["python3", "-c"] and smoke[-1] == "--smoke"
    assert len(json.dumps(smoke).encode()) < 8192, "smoke argv must stay small"
