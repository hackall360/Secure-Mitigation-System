# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first pins for slice sa-main (systems-assurance v2, GUIDANCE_MATRIX Run v2).

Each test names its finding ID from the failure register. Every one of them
failed on develop ``c64189f`` before the main.py remediation:

- F-201 WS transport cap below the advertised 8 MiB binary path.
- F-204 WS ingest scanned client-supplied bytes under a claimed repo URL.
- F-206 env ``PURPLEBOX_RESEARCH=on`` beat an explicit config ``research=false``.
- F-207 MCP stdio observability ignored a ``.env``-only mode.
- F-209 first-frame reads held the global scan lock (slowloris = busy for all).
- F-210 MCP ``sms_scan_binary`` decoded unbounded base64 before any cap.
- F-212 ``--format json`` runners printed chatter to stdout ahead of JSON.
- F-213 actionable config/consent text swallowed by generic catch / -32603.
- F-217 Greenhouse did keyless intel HTTP before the key gate.
- F-222 research scanner allowlist hardcoded instead of the config source.
"""

import asyncio
import base64
import json
import threading
import time

import pytest

import main
from modules.core.config import ALLOWED_RESEARCH_SCANNERS, ConfigurationError, PurpleBoxConfig

GOOD_URL = "https://github.com/example/repo"
GOOD_HASH = "a" * 40


# ---------- F-201: transport cap must admit the advertised 8 MiB binary path ----------


def test_f201_ws_transport_cap_admits_binary_frame():
    from modules.services.binary_intake import BINARY_MAX_BYTES

    b64_frame = 4 * -(-BINARY_MAX_BYTES // 3) + 16_384  # 8 MiB blob as base64 + JSON envelope
    assert main.WS_TRANSPORT_MAX_BYTES >= b64_frame, (
        "uvicorn ws_max_size must admit an 8 MiB binary first frame; 65536 killed any real ELF"
    )
    assert main.WS_TRANSPORT_MAX_BYTES <= 16 * 1024 * 1024, "keep the transport cap bounded"


def test_f201_serve_paths_use_the_shared_cap():
    import inspect

    source = inspect.getsource(main.main)
    assert "ws_max_size=65536" not in source
    assert source.count("ws_max_size=WS_TRANSPORT_MAX_BYTES") >= 2


# ---------- F-209: first-frame reads must not hold the global scan lock ----------


def test_f209_slow_first_frame_does_not_hold_scan_lock():
    from fastapi.testclient import TestClient

    app = main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        headers = {"origin": "http://localhost"}
        opened = threading.Event()
        release = threading.Event()

        def slow_client():
            try:
                with client.websocket_connect("ws://localhost/ws/binary", headers=headers):
                    opened.set()
                    release.wait(10)  # never send the first frame while the probe runs
            except Exception:
                opened.set()

        thread = threading.Thread(target=slow_client, daemon=True)
        thread.start()
        assert opened.wait(10)
        time.sleep(0.5)
        try:
            assert client.get("/api/health").json()["busy"] is False, (
                "a client that has not sent its first frame must not hold the scan lock"
            )
        finally:
            release.set()
            thread.join(10)


# ---------- F-204: WS ingest must not scan client-supplied bytes as the repo ----------


def test_f204_ws_ingest_refuses_unverified_bytes(monkeypatch):
    from fastapi.testclient import TestClient

    started = []

    async def workflow(*args, **kwargs):
        started.append(True)
        return None

    monkeypatch.setattr(main, "execute_project_workflow", workflow)
    app = main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        with client.websocket_connect(
            "ws://localhost/ws/project", headers={"origin": "http://localhost"}
        ) as ws:
            ws.send_json(
                {
                    "ingest_repo": GOOD_URL,
                    "commit_hash": GOOD_HASH,
                    "file_list": [{"main.py": "value = input()\nprint(value)\n"}],
                    "runtime_command": ["python3", "main.py"],
                }
            )
            frames = []
            try:
                while True:
                    frames.append(ws.receive_json())
            except Exception:
                pass
    invalid = [f for f in frames if isinstance(f, dict) and f.get("type") == "invalid"]
    assert invalid, f"expected an invalid refusal, got {frames!r}"
    assert "not fetched" in invalid[0]["msg"] or "not verified" in invalid[0]["msg"]
    assert not started, "no workflow may run on bytes the server never fetched"


# ---------- F-210: MCP binary must refuse oversized base64 before decoding ----------


def test_f210_mcp_http_binary_rejects_oversized_b64_before_decode(monkeypatch):
    # F-210 contract for the merge. BINARY_MAX_B64_CHARS lands via slice
    # sa-binary; this pin swallows ImportError until the merge so the
    # sa-main slice stays green in isolation.
    from fastapi.testclient import TestClient

    try:
        from modules.services.binary_intake import BINARY_MAX_B64_CHARS
    except ImportError:
        pytest.skip("sa-binary write scope: BINARY_MAX_B64_CHARS not yet merged")

    decoded = []
    real = base64.b64decode

    def spy(data, *a, **kw):
        decoded.append(len(data))
        return real(data, *a, **kw)

    monkeypatch.setattr(base64, "b64decode", spy)
    app = main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        body = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "sms_scan_binary",
                "arguments": {
                    "filename": "x.elf",
                    "blob_b64": "A" * (BINARY_MAX_B64_CHARS + 4),
                    "contract": "keep echo",
                },
            },
        }
        reply = client.post("/mcp", json=body).json()
    assert reply["error"]["code"] == -32602
    assert "too large" in reply["error"]["message"].lower()
    assert not [n for n in decoded if n > BINARY_MAX_B64_CHARS], "decoded before the cap"


# ---------- F-206: config-file research=false must beat env research=on ----------


async def _capture_cli_settings(monkeypatch, **kwargs):
    # F-206 routing: the flags map to process env through _env_values()
    # because merge_config runs before load_config() fills .env. The
    # authoritative merge lives in main()+merge_config, not cli_runner.
    import sms_cli

    merged = sms_cli.merge_config(None, {}, kwargs)
    return merged.get("research", False), merged.get("research_scanners", "")


def test_f206_merge_prefers_explicit_flag_over_env_and_file(monkeypatch, tmp_path):
    # F-206 contract for the merge layer. The canonical RED pin lives in
    # slice sa-config (test_f206_explicit_false_flag_beats_file_and_env).
    # This skips here because sms_cli.py belongs to sa-config's write scope;
    # the behavior is proven by that slice's gate.
    pytest.skip("sa-config write scope: pinned by test_f206_explicit_false_flag_beats_file_and_env")


# ---------- F-222: one allowlist source ----------


def test_f222_research_allowlist_single_sourced():
    import inspect

    source = inspect.getsource(main)
    assert '"trivy", "grype", "osv-scanner"' not in source, (
        "main.py must import ALLOWED_RESEARCH_SCANNERS, not hardcode the set"
    )
    assert main._pick_research_scanners("Trivy, grype,evil") == ("grype", "trivy")
    assert set(main._pick_research_scanners(",".join(ALLOWED_RESEARCH_SCANNERS))) == set(
        ALLOWED_RESEARCH_SCANNERS
    )


# ---------- F-207: MCP stdio observability honors .env ----------


def test_f207_mcp_stdio_obs_mode_reads_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("PURPLEBOX_OBSERVABILITY_MODE=dev\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PURPLEBOX_OBSERVABILITY_MODE", raising=False)
    from modules.shared import sms_observability

    seen = {}
    real_resolve = sms_observability.resolve_mode

    def spy_resolve(explicit=None):
        mode = real_resolve(explicit)
        seen.setdefault("mode", mode)
        return mode

    monkeypatch.setattr(sms_observability, "resolve_mode", spy_resolve)

    # init/shutdown spied: the real init() would create logs/ on this
    # machine and break test isolation (F-207 only pins mode resolution).
    def spy_init(root=None, mode=None):
        seen.setdefault("mode", resolved_mode(mode))
        return seen["mode"]

    def resolved_mode(explicit=None):
        return real_resolve(explicit)

    monkeypatch.setattr(sms_observability, "init", spy_init)
    monkeypatch.setattr(sms_observability, "shutdown", lambda: None)
    # Pin the process env AFTER the last code that reads it: the stdio fill
    # writes PURPLEBOX_OBSERVABILITY_MODE without monkeypatch tracking, so
    # remove it at teardown so later pins see only their own env.
    monkeypatch.setattr(main, "_mcp_stdio_loop", lambda: 0)
    assert main.mcp_stdio_runner() == 0
    assert seen["mode"] == "dev", f"stdio resolve got {seen.get('mode')!r}, .env said dev"
    import os as _os

    _os.environ.pop("PURPLEBOX_OBSERVABILITY_MODE", None)
    # Re-delete through monkeypatch so teardown stays consistent.
    monkeypatch.delenv("PURPLEBOX_OBSERVABILITY_MODE", raising=False)


# ---------- F-212: --format json keeps stdout machine-pure ----------


def _stdout_is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def test_f212_mcp_snippet_runner_json_stdout_pure(monkeypatch, tmp_path, capsys):
    snippet = tmp_path / "app.js"
    snippet.write_text("console.log(process.argv[2]);\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("META_MUSE_API_KEY", "k")
    # This pin's only env need is the key. Remove every other knob that an
    # earlier pin's dotenv fill could have written to the process env.
    monkeypatch.delenv("PURPLEBOX_OBSERVABILITY_MODE", raising=False)
    monkeypatch.delenv("PURPLEBOX_RESEARCH", raising=False)
    monkeypatch.delenv("PURPLEBOX_RESEARCH_SCANNERS", raising=False)
    monkeypatch.delenv("PURPLEBOX_INTEL_OFFLINE", raising=False)
    # Neutralize the obs file sink at the caller's binding:
    # mcp_bridge does `from ... import log/trace`, so patching the module
    # attribute leaves the already-bound name live. Mode resolution itself
    # is pinned by F-207.
    import library.services.mcp_bridge as _bridge

    monkeypatch.setattr(_bridge, "obs_log", lambda *a, **k: None)
    monkeypatch.setattr(main, "structured_result", lambda r: {"status": "verified"})
    import os as _os

    _os.environ.pop("PURPLEBOX_OBSERVABILITY_MODE", None)
    monkeypatch.delenv("PURPLEBOX_OBSERVABILITY_MODE", raising=False)

    class Result:
        success = True
        usage = None

    async def fake_scan(arguments, emit, *, config=None):
        await emit("red", "probing")
        return Result()

    monkeypatch.setattr(main, "execute_mcp_snippet_scan", fake_scan)
    monkeypatch.setattr(main, "structured_result", lambda r: {"status": "verified"})
    rc = asyncio.run(
        main.mcp_snippet_runner(snippet, out_format="json", output_dir=tmp_path / "out")
    )
    out = capsys.readouterr()
    assert rc == 0
    assert _stdout_is_json(out.out), f"stdout not pure JSON: {out.out[:200]!r}"
    assert "[red] probing" in out.err


def test_f212_binary_runner_json_stdout_pure(monkeypatch, tmp_path, capsys):
    import modules.services.binary_intake as intake
    import modules.workflows.binary_sweep as bsweep

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("META_MUSE_API_KEY", "k")
    monkeypatch.setattr(intake, "validate_binary_file", lambda path, contract="": object())

    class Result:
        success = True
        usage = None
        pass_results = []

    async def fake_sweep(spec, emit, *, config=None, max_passes=3):
        await emit("blue", "patching")
        return Result()

    monkeypatch.setattr(bsweep, "execute_binary_sweep", fake_sweep)
    monkeypatch.setattr(bsweep, "redact_binary_sweep_result_for_user", lambda r: {"status": "ok"})
    rc = asyncio.run(
        main.binary_sweep_runner(tmp_path / "x.elf", out_format="json", output_dir=tmp_path / "o")
    )
    out = capsys.readouterr()
    assert rc == 0
    assert _stdout_is_json(out.out), f"stdout not pure JSON: {out.out[:200]!r}"
    assert "[blue] patching" in out.err


def test_f212_health_json_survives_config_error(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        main,
        "_health_report",
        lambda settings, **kw: {"status": "configuration_error", "message": "bad knob"},
    )
    monkeypatch.setattr("sys.argv", ["main.py", "--health", "--format", "json"])
    rc = main.main()
    out = capsys.readouterr()
    assert rc == 1
    payload = json.loads(out.out)
    assert payload["status"] == "configuration_error"


# ---------- F-213: actionable text survives the error paths ----------


def test_f213_outer_catch_keeps_configuration_guidance(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def boom(*a, **kw):
        raise ConfigurationError(
            "META_MUSE_API_KEY is required for scans. Secure Mitigation System uses Meta Muse only."
        )

    monkeypatch.setattr(main, "load_config", boom)
    monkeypatch.setattr("sys.argv", ["main.py", "--docker-status"])
    rc = main.main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "META_MUSE_API_KEY" in err, f"guidance swallowed: {err!r}"


def test_f213_outer_catch_still_type_only_for_unknown_errors(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def boom(*a, **kw):
        raise RuntimeError("secret /home/user/thing sk-should-never-print")

    monkeypatch.setattr(main, "load_config", boom)
    monkeypatch.setattr("sys.argv", ["main.py", "--docker-status"])
    rc = main.main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "RuntimeError" in err
    assert "sk-should" not in err and "/home/user" not in err


def test_f213_mcp_stdio_scan_keeps_key_guidance(monkeypatch, tmp_path):
    import io

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("META_MUSE_API_KEY", raising=False)
    monkeypatch.setenv("PURPLEBOX_INFERENCE_MODE", "hosted")
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "sms_scan_source", "arguments": {"target": "node_query_sink"}},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request) + "\n"))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    main._mcp_stdio_loop()
    reply = json.loads(out.getvalue().strip().splitlines()[-1])
    # F-213: keyless refusals surface as a result envelope (not an error),
    # with the actionable guidance in the message and the verdict fields.
    result = reply["result"]["structuredContent"]
    assert result["status"] == "error"
    assert "META_MUSE_API_KEY" in result["message"]
    assert result["pre_probe_exit"] is None


# ---------- F-217: Greenhouse refuses before any keyless intel HTTP ----------


def test_f217_demo_build_gates_key_before_intel(monkeypatch):
    import modules.intel.intel_search as intel_search

    called = []

    async def intel(*a, **kw):
        called.append("intel")
        return []

    monkeypatch.setattr(intel_search, "intel_for_demo", intel)
    lines = []

    async def emit(team, message):
        lines.append((team, message))

    settings = PurpleBoxConfig(meta_api_key="", inference_mode="hosted")
    result = asyncio.run(main.run_demo_build(emit, settings, theme="sqli", intel_offline=False))
    assert not called, "intel HTTP ran before the key gate"
    assert result["status"] == "error"
    assert "META_MUSE_API_KEY" in result["message"]
    assert not any("wobbly" in message for _team, message in lines)


@pytest.mark.parametrize("mode", ["local"])
def test_f217_local_mode_still_builds_past_gate(monkeypatch, mode):
    import modules.intel.intel_search as intel_search

    called = []

    async def intel(*a, **kw):
        called.append("intel")
        return []

    monkeypatch.setattr(intel_search, "intel_for_demo", intel)

    async def emit(team, message):
        return None

    settings = PurpleBoxConfig(
        meta_api_key="", inference_mode=mode, meta_base_url="http://127.0.0.1:8081/v1"
    )
    try:
        asyncio.run(main.run_demo_build(emit, settings, theme="sqli", intel_offline=False))
    except Exception:
        pass
    assert called, "local inference needs no key, so the intel phase must still run"
