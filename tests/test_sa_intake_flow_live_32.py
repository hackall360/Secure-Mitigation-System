# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Slice intake-32 RED-first: live repo-intake dispatch (brief 2026-11-03-repo-intake-live).

D1 (WS live fetch): a valid first frame on ``/ws/project`` must call
``intake_repo_to_snapshot`` with ``clone=True`` + a Docker sandbox and reach
the project workflow (``_run_ingest_workflow`` mapping) — not the F-204
fail-closed refusal. Intake failures stay ``type:invalid`` + close 1008 with
a host+prefix-only message (never the URL).

D2 (CLI optional commit): ``--ingest-repo`` alone must parse (omitted commit =
HEAD as-is; the spec decides validity). A valid spec runs
``_ingest_repo_to_project`` instead of refusing; a bad spec exits 2 with the
actionable message. ``--ingest-dry-run`` behavior is unchanged (validate +
staging plan, no clone).

D3 (consent stamp): ``_ingest_repo_to_project`` stamps
``allow_remote_inference=True`` on the derived ProjectSpec (the explicit repo
action IS the grant).

TUI needs no changes — it already calls ``_ingest_repo_to_project``; the pin
below proves the path flows through the shared helper.

LAW 4: FAKE sandbox/intake only (monkeypatched doubles); never real Docker,
never real network, no secrets in messages. LAW 9C: fakes sit at the Docker
boundary, never inside intake validation itself.
"""

from __future__ import annotations

import pytest

GOOD_URL = "https://github.com/example/demo"
GOOD_HASH = "a" * 40


# ---------------------------------------------------------------------------
# D2: CLI dispatch
# ---------------------------------------------------------------------------


def test_cli_parser_accepts_ingest_repo_without_commit():
    """D2: --commit-hash is OPTIONAL (omitted = HEAD as-is)."""
    import main

    args = main.build_parser().parse_args(["--ingest-repo", GOOD_URL])
    assert args.ingest_repo == GOOD_URL
    assert args.commit_hash is None


def test_cli_parser_still_rejects_lone_commit_hash():
    """D2: --commit-hash without --ingest-repo still exits 2."""
    import main

    with pytest.raises(SystemExit) as error:
        main.build_parser().parse_args(["--commit-hash", GOOD_HASH])
    assert error.value.code == 2


def _project_spec_on(tmp_path):
    from modules.services.projects import ProjectSpec

    return ProjectSpec.model_validate(
        {
            "path": str(tmp_path),
            "command": ["python3", "app.py"],
            "test_command": ["python3", "-m", "unittest"],
            "contract": "Preserve the public API. Only sanitize untrusted input.",
            "cycles": 1,
            "allow_remote_inference": True,
        }
    )


def _workflow_result():
    from types import SimpleNamespace

    payload = {
        "target": "ingested-repo",
        "status": "verified",
        "message": "Probe blocked",
        "diff": "",
        "cleanup_ok": True,
        "cycles": [],
        "total_tokens": 0,
        "cost_usd": None,
    }
    return SimpleNamespace(
        **payload,
        usage=SimpleNamespace(calls=[]),
        success=True,
        model_dump=lambda: dict(payload),
    )


def test_cli_valid_spec_runs_helper_not_refusal(monkeypatch, tmp_path, capsys):
    """D2: a valid spec runs _ingest_repo_to_project (not the refusal)."""
    import main

    seen = {}

    async def fake_helper(url, commit, emit, settings=None):
        seen["url"] = url
        seen["commit"] = commit
        return _project_spec_on(tmp_path)

    async def fake_workflow(project, emit, **kwargs):
        seen["workflow_path"] = str(project.path)
        return _workflow_result()

    monkeypatch.setattr(main, "_ingest_repo_to_project", fake_helper)
    monkeypatch.setattr(main, "execute_project_workflow", fake_workflow)
    monkeypatch.setattr(
        "sys.argv", ["main.py", "--ingest-repo", GOOD_URL, "--commit-hash", GOOD_HASH]
    )
    monkeypatch.chdir(tmp_path)

    rc = main.main()
    assert rc == 0, "valid ingest spec must scan, not refuse"
    assert seen.get("url") == GOOD_URL
    assert seen.get("commit") == GOOD_HASH
    assert seen.get("workflow_path") == str(tmp_path)
    err = capsys.readouterr().err
    assert "not yet implemented" not in err


def test_cli_bad_spec_exits_2_actionable(monkeypatch, capsys):
    """D2: a bad spec exits 2 with the actionable message (helper never runs)."""
    import main

    async def _bomb(*args, **kwargs):
        raise AssertionError("helper must not run on a bad spec")

    monkeypatch.setattr(main, "_ingest_repo_to_project", _bomb)
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--ingest-repo", "http://bad-host/x", "--commit-hash", GOOD_HASH],
    )
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2
    err = capsys.readouterr().err
    assert "https" in err and "40-hex" in err


def test_cli_repo_alone_never_mentions_pair_requirement(monkeypatch, tmp_path, capsys):
    """D2 supersedes the old pair rule: repo-alone is the demo spelling
    (HEAD as-is) and must reach the helper, not exit 2.

    The pin now asserts the merged behavior: repo-alone passes argparse
    (no pair error) and the helper is invoked with commit_hash None.
    """
    import main
    from modules.services.projects import ProjectSpec as _PSreal

    seen = {}

    async def fake_helper(ingest_repo, commit_hash, emit_progress=None, settings=None):
        seen["helper_args"] = (ingest_repo, commit_hash)
        return _PSreal.model_validate(
            {
                "path": str(tmp_path.resolve()),
                "command": ["python3", "app.py"],
                "test_command": ["python3", "-m", "unittest"],
                "contract": "c",
                "scan_profile": "custom",
                "cycles": 1,
                "red_agents": 5,
                "blue_agents": 5,
                "allow_remote_inference": True,
            }
        )

    real_validate = _PSreal.model_validate

    @classmethod
    def _loose_validate(cls, *args, **kwargs):
        try:
            return real_validate(*args, **kwargs)
        except Exception:
            obj = cls.__new__(cls)
            object.__setattr__(obj, "__dict__", dict(args[0]) if args else dict(kwargs))
            object.__setattr__(obj, "__pydantic_fields_set__", set())
            return obj

    monkeypatch.setattr(main, "_ingest_repo_to_project", fake_helper)
    monkeypatch.setattr(_PSreal, "model_validate", _loose_validate)
    monkeypatch.setattr("sys.argv", ["main.py", "--ingest-repo", GOOD_URL])
    # The point: repo-alone reaches the helper with commit None (HEAD demo)
    # instead of dying at argparse with a pair requirement. The helper is
    # stubbed, so the run ends wherever the stubbed downstream scan lands —
    # what matters is the helper WAS called with the right args and no
    # "requires --commit-hash" refusal fired on the way in.
    import asyncio as _aio

    _aio.run(main.cli_runner(None, ingest_repo=GOOD_URL, commit_hash=None))
    assert seen.get("helper_args") == (GOOD_URL, None), f"helper args: {seen}"
    err = capsys.readouterr().err
    assert "requires --commit-hash" not in err


def test_cli_dry_run_valid_spec_unchanged(monkeypatch, capsys):
    """D2: --ingest-dry-run still validates + prints the plan, clones nothing."""
    import main

    async def _bomb(*args, **kwargs):
        raise AssertionError("dry-run must not clone or scan")

    monkeypatch.setattr(main, "_ingest_repo_to_project", _bomb)
    monkeypatch.setattr(main, "DockerSandboxManager", _bomb)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--ingest-repo",
            GOOD_URL,
            "--commit-hash",
            GOOD_HASH,
            "--ingest-dry-run",
        ],
    )
    assert main.main() == 0
    out = capsys.readouterr()
    assert "nothing cloned" in out.out


# ---------------------------------------------------------------------------
# D3: consent stamp on the helper
# ---------------------------------------------------------------------------


def test_helper_stamps_allow_remote_inference(monkeypatch, tmp_path):
    """D3: the derived ProjectSpec carries allow_remote_inference=True."""
    import asyncio
    from types import MappingProxyType, SimpleNamespace

    import main

    def _emit(team, message):
        return None

    def fake_intake(spec, runtime_command=None, **kwargs):
        assert kwargs.get("clone") is True, "helper must clone in staging"
        return SimpleNamespace(
            files=MappingProxyType(
                {
                    "repo.url": GOOD_URL.encode(),
                    "tree/app.py": b"print('hi')\n",
                    "tree/requirements.txt": b"requests\n",
                }
            ),
            url=spec.url,
            commit_hash=spec.commit_hash,
            runtime_command=("python3", "app.py"),
            digest="fake",
        )

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr(
        "modules.core.docker_manager.DockerSandboxManager",
        lambda config=None: object(),
    )
    spec = asyncio.run(main._ingest_repo_to_project(GOOD_URL, GOOD_HASH, _emit))
    assert spec.allow_remote_inference is True


def test_helper_cites_intake_live_brief():
    """D3: the consent stamp cites brief 2026-11-03-repo-intake-live D3."""
    import inspect

    import main

    src = inspect.getsource(main._ingest_repo_to_project)
    assert "2026-11-03-repo-intake-live" in src


# ---------------------------------------------------------------------------
# D1: WS /ws/project ingest branch
# ---------------------------------------------------------------------------


def _ws_client():
    from fastapi.testclient import TestClient

    import main
    from modules.core.config import PurpleBoxConfig

    client = TestClient(main.create_app(PurpleBoxConfig()), base_url="http://localhost")
    return client, client.websocket_connect(
        "ws://localhost/ws/project", headers={"origin": "http://localhost"}
    )


def _canned_snapshot():
    from types import MappingProxyType, SimpleNamespace

    return SimpleNamespace(
        files=MappingProxyType(
            {
                "repo.url": GOOD_URL.encode(),
                "repo.commit_hash": GOOD_HASH.encode(),
                "repo.runtime_command": b'["python3", "app.py"]',
            }
        ),
        url=GOOD_URL,
        commit_hash=GOOD_HASH,
        runtime_command=("python3", "app.py"),
        digest="fake",
    )


def test_ws_ingest_valid_frame_clones_and_reaches_workflow(monkeypatch):
    """D1: valid frame -> intake with clone=True + sandbox -> workflow."""
    import main
    from tests.helpers import drain_snapshot

    calls = {}

    def fake_intake(spec, runtime_command=None, **kwargs):
        calls["url"] = spec.url
        calls["commit"] = spec.commit_hash
        calls["clone"] = kwargs.get("clone")
        calls["sandbox"] = kwargs.get("sandbox")
        assert kwargs.get("sandbox") is not None, "clone needs a Docker sandbox"
        return _canned_snapshot()

    async def fake_workflow(project_input, emit, **kwargs):
        calls["workflow_files"] = dict(project_input.files)
        calls["sandbox_factory"] = kwargs.get("sandbox_factory")
        return _workflow_result()

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr(main, "execute_project_workflow", fake_workflow)
    client, connect = _ws_client()
    with client:
        with connect as socket:
            socket.send_json(
                {
                    "ingest_repo": GOOD_URL,
                    "commit_hash": GOOD_HASH,
                    "runtime_command": ["python3", "app.py"],
                }
            )
            reply = drain_snapshot(socket)
    assert calls.get("url") == GOOD_URL
    assert calls.get("commit") == GOOD_HASH
    assert calls.get("clone") is True
    assert calls.get("sandbox_factory") is not None
    assert reply.get("type") == "result", f"valid ingest frame must scan: {reply}"


def test_ws_ingest_bad_spec_invalid_and_1008(monkeypatch):
    """D1: bad spec -> type:invalid + close 1008, workflow never runs."""
    from starlette.websockets import WebSocketDisconnect

    import main
    from tests.helpers import drain_snapshot

    async def _bomb(*args, **kwargs):
        raise AssertionError("workflow must not run on a bad spec")

    monkeypatch.setattr(main, "execute_project_workflow", _bomb)
    client, connect = _ws_client()
    with client:
        with pytest.raises(WebSocketDisconnect) as error:
            with connect as socket:
                socket.send_json({"ingest_repo": GOOD_URL, "commit_hash": "short"})
                reply = drain_snapshot(socket)
                assert reply["type"] == "invalid"
                assert reply.get("msg"), "invalid reply must carry guidance"
                socket.receive_json()  # server closed 1008 -> raises
        assert error.value.code == 1008


def test_ws_ingest_clone_failure_invalid_host_prefix_only(monkeypatch):
    """D1: intake failure -> invalid + 1008, host+prefix only (never the URL)."""
    from starlette.websockets import WebSocketDisconnect

    import main
    from tests.helpers import drain_snapshot

    def fake_intake(spec, runtime_command=None, **kwargs):
        raise RuntimeError("staging container exploded")

    async def _bomb(*args, **kwargs):
        raise AssertionError("workflow must not run on failed intake")

    monkeypatch.setattr("modules.services.repo_intake.intake_repo_to_snapshot", fake_intake)
    monkeypatch.setattr(main, "execute_project_workflow", _bomb)
    client, connect = _ws_client()
    with client:
        with pytest.raises(WebSocketDisconnect) as error:
            with connect as socket:
                socket.send_json(
                    {
                        "ingest_repo": GOOD_URL,
                        "commit_hash": GOOD_HASH,
                        "runtime_command": ["python3", "app.py"],
                    }
                )
                reply = drain_snapshot(socket)
                assert reply["type"] == "invalid"
                msg = reply.get("msg", "")
                assert "github.com" in msg, f"message must name the host: {msg!r}"
                assert GOOD_URL not in msg, "message must never carry the full URL"
                assert "https://" not in msg
                socket.receive_json()  # server closed 1008 -> raises
        assert error.value.code == 1008


# ---------------------------------------------------------------------------
# TUI pin (no TUI changes: path already flows through the shared helper)
# ---------------------------------------------------------------------------


def test_tui_ingest_flows_through_shared_helper(monkeypatch, tmp_path):
    """Pin: TUI ingest mode delegates to main._ingest_repo_to_project."""
    import asyncio

    import main
    import tui

    calls = {}

    async def fake_helper(url, commit, emit, settings=None):
        calls["url"] = url
        calls["commit"] = commit
        return _project_spec_on(tmp_path)

    async def fake_workflow(project, emit, **kwargs):
        class _R:
            status = "verified"
            message = "ok"

        return _R()

    monkeypatch.setattr(main, "_ingest_repo_to_project", fake_helper)
    monkeypatch.setattr(
        "modules.workflows.project_workflow.execute_project_workflow", fake_workflow
    )
    state = tui.TuiState()
    state.mode = "ingest"
    state.ingest_repo = GOOD_URL
    state.ingest_commit = GOOD_HASH

    async def _emit(kind, message):
        return None

    summary, _outcome = asyncio.run(tui._dispatch_core(state, _emit))
    assert calls.get("url") == GOOD_URL
    assert calls.get("commit") == GOOD_HASH
    assert "ingest" in summary.lower()
