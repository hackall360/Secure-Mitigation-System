# LAWs 0, 9 govern this task (RED-first: failing test before implementation).
"""P5 services + tags gap tests — intent parsing, validation, redaction, registry.

Scope: library/services/ (demo_gen, repo_intake, mcp_bridge, sms_api,
chatter, projects, binary_intake, binary_telemetry, project_agents,
telemetry_hub) + library/tags.py. No live Muse/Docker: every test below
exercises pure host-side helpers or doubles the transport boundary the way
existing tests do (KnownMuse-style fakes, real validators, no network).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


# --- demo_gen._text: list/set joining, None, non-string coercion ---


def test_text_joins_list_and_skips_blanks():
    from modules.services.demo_gen import _text

    assert _text(["sqli", "", "  xss "]) == "sqli, xss"
    assert _text(None) == ""
    assert _text("  spaced  ") == "  spaced  "
    assert _text({"b", "a"}, sep="|") in ("a|b", "b|a")
    assert _text(123) == "123"


def test_text_odd_values_coerce_without_raising():
    from modules.services.demo_gen import _text

    assert _text(["", None, "x"]) == "x"
    assert _text(0) == ""  # falsy non-string coerces to empty (str(value or ""))


def test_parse_build_intent_numbered_bullets_and_cve_case():
    from modules.services.demo_gen import parse_build_intent

    intent = parse_build_intent(vulns="1. cve-2024-3094 and sqli")
    assert intent.cve_ids == ["CVE-2024-3094"]
    assert intent.named_types == ["SQL injection"]
    assert intent.free_text == []


def test_upper_cve_validator_non_list_passthrough():
    from pydantic import ValidationError

    from modules.services.demo_gen import BuildIntent

    # Non-list input passes the validator through untouched (else-branch,
    # covers line 151), then strict list validation rejects it.
    with pytest.raises(ValidationError):
        BuildIntent.model_validate({"build_brief": "", "cve_ids": "CVE-2021-44228"})


def test_demo_gen_vulns_property_merges_all_sources():
    from modules.services.demo_gen import parse_build_intent

    intent = parse_build_intent(vulns="sqli, CVE-2024-3094, weird header thing")
    assert intent.vulns == [*intent.cve_ids, *intent.named_types, *intent.free_text]
    assert intent.vulns[0] == "CVE-2024-3094"


def test_materialize_rejects_secret_and_bad_syntax(tmp_path):
    from modules.services.demo_gen import DemoProjectFiles, materialize_demo_project

    good = DemoProjectFiles(
        app_py="print('hi')\n",
        test_contract_py="print('ok')\n",
        contract="c",
    )
    spec = materialize_demo_project(good, dest_dir=str(tmp_path / "g"))
    assert str(spec.path).endswith("g")
    assert spec.test_command == ["python3", "test_contract.py"]

    evil = DemoProjectFiles(
        app_py="x = 'sk_live_" + "a" * 24 + "'\nprint(x)\n",
        test_contract_py="print('ok')\n",
        contract="c",
    )
    with pytest.raises(ValueError, match="secret"):
        materialize_demo_project(evil, dest_dir=str(tmp_path / "e"))

    broken = DemoProjectFiles(
        app_py="def broken(:\n",
        test_contract_py="print('ok')\n",
        contract="c",
    )
    with pytest.raises(ValueError, match="invalid app.py"):
        materialize_demo_project(broken, dest_dir=str(tmp_path / "b"))

    with pytest.raises(ValueError, match="unsafe"):
        materialize_demo_project(good, dest_dir=str(tmp_path / "n"), name="../evil")


def test_generate_demo_project_fail_fast_on_bad_syntax():
    from modules.services.demo_gen import DemoProjectFiles, generate_demo_project

    class FakeClient:
        from modules.core.config import PurpleBoxConfig

        config = PurpleBoxConfig()

        async def _request(self, *args, **kwargs):
            return DemoProjectFiles(
                app_py="def broken(:\n",
                test_contract_py="print('ok')\n",
                contract="c",
            )

    with pytest.raises(ValueError, match="invalid app.py"):
        asyncio.run(
            generate_demo_project(FakeClient(), intel_context=[], build_brief="b")
        )


# --- repo_intake pure helpers: normalise entries, commands, detection ---


def test_normalise_entries_object_with_files_mapping():
    from modules.services.repo_intake import _normalise_file_entries

    class Snap:
        files = {"a/../b/app.py": "print(1)"}

    assert _normalise_file_entries(Snap()) == (("a/b/app.py", "print(1)"),)
    assert _normalise_file_entries(None) == ()
    assert _normalise_file_entries({"x.py": b"print(1)"}) == (("x.py", "print(1)"),)


def test_normalise_entries_list_forms_and_errors():
    from modules.services.repo_intake import _normalise_file_entries

    assert _normalise_file_entries(["a.py"]) == (("a.py", None),)
    assert _normalise_file_entries([{"a.py": "x"}]) == (("a.py", "x"),)
    # A bare list holding a list is not a valid entry shape: raises.
    with pytest.raises(ValueError, match="must be names"):
        _normalise_file_entries([[("a.py", "x")]])
    assert _normalise_file_entries([("a.py", "x")]) == (("a.py", "x"),)
    with pytest.raises(ValueError, match="must be names"):
        _normalise_file_entries([[(123,)]])
    with pytest.raises(ValueError, match="must be names"):
        _normalise_file_entries([(123, "x")])
    with pytest.raises(ValueError, match="must be str, bytes"):
        _normalise_file_entries({"a.py": 123})
    with pytest.raises(ValueError, match="file-name list"):
        _normalise_file_entries(42)
    with pytest.raises(ValueError, match="non-empty strings"):
        _normalise_file_entries([{"": "x"}])


def test_package_python_php_makefile_commands():
    from modules.services import repo_intake as RI

    assert RI._package_json_command('{"scripts": {"start": "x"}}') == ["npm", "start"]
    assert RI._package_json_command('{"main": "srv.js"}') == ["node", "srv.js"]
    assert RI._package_json_command("{bad json") == ["npm", "start"]
    assert RI._package_json_command('{"scripts": {}}') == ["npm", "start"]
    assert RI._python_command({"app.py"}) == ["python3", "app.py"]
    assert RI._python_command({"zzz.py"}) == ["python3", "main.py"]
    assert RI._php_command({"other.php"}) == ["php", "index.php"]
    assert RI._php_command({"public/index.php"}) == ["php", "public/index.php"]
    assert RI._makefile_command("run:\n\tx\nfoo:\n\ty\n") == ["make", "run"]
    assert RI._makefile_command("zzz:\n\tx\n") == ["make", "zzz"]
    assert RI._makefile_command(None) == ["make"]


def test_detect_runtime_all_branches():
    from modules.services.repo_intake import detect_runtime

    assert detect_runtime(["package.json"]) == ["npm", "start"]
    assert detect_runtime(["requirements.txt"]) == ["python3", "main.py"]
    assert detect_runtime(["composer.json"]) == ["php", "index.php"]
    assert detect_runtime(["Makefile"]) == ["make"]
    assert detect_runtime({"app.py": "", "package.json": ""}) == ["npm", "start"]
    with pytest.raises(ValueError, match="could not detect"):
        detect_runtime([])
    with pytest.raises(ValueError, match="could not detect"):
        detect_runtime(["notes.txt"])


def test_intake_auto_detect_and_argv_guards():
    from modules.services.repo_intake import RepoIntakeSpec, intake_repo_to_snapshot

    spec = RepoIntakeSpec(url="https://github.com/o/r", commit_hash="a" * 40)
    snap = intake_repo_to_snapshot(spec, file_list=["package.json"])
    assert snap.runtime_command == ("npm", "start")
    assert snap.digest and len(snap.digest) == 64
    with pytest.raises(ValueError, match="non-empty argv"):
        intake_repo_to_snapshot(spec, runtime_command=[])
    with pytest.raises(ValueError, match="non-empty strings"):
        intake_repo_to_snapshot(spec, runtime_command=["", 1])
    with pytest.raises(TypeError, match="host paths"):
        intake_repo_to_snapshot(spec, ["npm", "start"], host_path="/tmp/x")
    with pytest.raises(ValueError, match="RepoIntakeSpec"):
        intake_repo_to_snapshot("nope", ["npm", "start"])


def test_repo_spec_rejects_bad_commit_even_with_good_url():
    from modules.services.repo_intake import RepoIntakeSpec

    with pytest.raises(ValueError, match="commit_hash"):
        RepoIntakeSpec(url="https://github.com/o/r", commit_hash="abc")


# --- binary_telemetry pure summarizer ---


def test_summarize_profile_branches():
    from modules.services.binary_telemetry import summarize_profile

    assert summarize_profile("")["notes"] == "empty profile"
    assert summarize_profile(None)["format"] == "unknown"
    assert summarize_profile(123)["format"] == "unknown"
    elf = summarize_profile("ELF file imports system and strcpy, has /bin/sh")
    assert elf["format"] == "elf"
    assert "imports:system" in elf["signals"] and "string:/bin/sh" in elf["signals"]
    assert summarize_profile("Mach-O binary, nothing here")["format"] == "macho"
    assert summarize_profile("mach-o image")["format"] == "macho"
    assert summarize_profile("PE32 MZ executable")["format"] == "pe"
    clean = summarize_profile("ELF hello world")
    assert clean["format"] == "elf"
    assert "unclassified" in clean["notes"]


# --- telemetry_hub batcher + snapshot (async doubles, no I/O) ---


def test_telemetry_hub_window_clamps_and_coalesces():
    from modules.services.telemetry_hub import TelemetryBatcher

    async def go():
        frames = []
        b = TelemetryBatcher(frames.append, window_ms=1)
        assert 0.10 <= b.window_s <= 0.25
        big = TelemetryBatcher(frames.append, window_ms=10_000)
        assert big.window_s == 0.25
        small = TelemetryBatcher(frames.append, window_ms=1, max_events=2)
        for i in range(5):
            await small.push({"i": i})
        await small.flush()
        assert frames and frames[-1]["count"] == 2
        before = len(frames)
        await small.flush()
        assert len(frames) == before
        return frames

    frames = asyncio.run(go())
    assert frames[-1]["events"] == [{"i": 3}, {"i": 4}]


def test_build_snapshot_busy_and_key_states():
    from modules.services.telemetry_hub import build_snapshot

    snap = build_snapshot(targets={"a": {}}, busy=True, docker_state="ready", key_ok=True)
    assert snap["chips"] == {"server": "busy", "docker": "ready", "key": "ok"}
    idle = build_snapshot()
    assert idle["nodes"] == [] and idle["chips"]["server"] == "ok"


# --- mcp_bridge status registry, snippet targets, envelopes ---


def test_scan_status_registry_eviction_and_latest():
    import modules.services.mcp_bridge as B

    B._SCAN_REGISTRY.clear()
    assert B.scan_status_latest()["scan_id"] == "none"
    B.scan_status_register("v3-1", phase="red")
    B.scan_status_mark_phase("v3-1", "blue")
    assert B.scan_status_for("v3-1") == {"scan_id": "v3-1", "phase": "blue", "done": False}
    assert B.scan_status_for("missing")["done"] is True
    assert B.scan_status_for(None)["scan_id"] == "v3-1"
    B._SCAN_REGISTRY.clear()
    for i in range(B.SCAN_REGISTRY_MAX_ENTRIES + 5):
        B.scan_status_register(f"k-{i}")
    assert len(B._SCAN_REGISTRY) == B.SCAN_REGISTRY_MAX_ENTRIES
    assert "k-0" not in B._SCAN_REGISTRY
    B.scan_status_mark_done("v3-1")
    assert B.scan_status_for("v3-1")["done"] is True
    B._SCAN_REGISTRY.clear()


def test_scan_status_sinks_track_phases():
    import modules.services.mcp_bridge as B

    async def go():
        B._SCAN_REGISTRY.clear()
        emit = B.scan_status_sink("s1")
        await emit("research", "x")
        assert B.scan_status_for("s1")["phase"] == "red"
        await emit("bogus-team", "x")
        assert B.scan_status_for("s1")["phase"] == "red"

        seen = []

        async def capture(team, message):
            seen.append((team, message))

        inner = B.scan_status_phase_sink("s2", capture)
        await inner("blue", "y")
        assert seen == [("blue", "y")]
        assert B.scan_status_for("s2")["phase"] == "blue"
        B._SCAN_REGISTRY.clear()

    asyncio.run(go())


def test_snippet_targets_and_envelopes():
    import modules.services.mcp_bridge as B

    for lang, key in (("JavaScript", "node_query_sink"), ("PYTHON", "node_query_sink"), ("php", "php_command_sink")):
        args = B.validate_snippet_arguments(
            {"filename": "x", "language": lang, "source": "print(1)", "contract": "c"}
        )
        assert B.snippet_baseline_key(args) == key
        tgt = B.snippet_target(args)
        assert tgt.key == "mcp_snippet"
        assert B.snippet_target_source(args) == "print(1)"
        reg = B.mcp_registry_with_snippet(args)
        assert reg["mcp_snippet"].key == "mcp_snippet"

    assert B.structured_result(object())["status"] == "error"
    assert B.jsonrpc_result(1, {"a": 1}) == {"jsonrpc": "2.0", "id": 1, "result": {"a": 1}}
    err = B.jsonrpc_error(2, -1, "m", {"k": 1})
    assert err["error"]["data"] == {"k": 1}
    plain = B.jsonrpc_error(2, -1, "m")
    assert "data" not in plain["error"]
    wrapped = B._wrap_tool_result(7, {"ok": True})
    assert wrapped["id"] == 7
    assert wrapped["result"]["structuredContent"] == {"ok": True}


def test_validate_snippet_rejects_bad_filename_and_oversize():
    import modules.services.mcp_bridge as B

    base = {"filename": "x", "language": "python", "source": "print(1)", "contract": "c"}
    with pytest.raises(ValueError, match="bare filename"):
        B.validate_snippet_arguments({**base, "filename": "../evil"})
    with pytest.raises(ValueError, match="bare filename"):
        B.validate_snippet_arguments({**base, "filename": ".hidden"})
    with pytest.raises(ValueError, match="Invalid snippet arguments"):
        B.validate_snippet_arguments({**base, "source": "x" * (B.MCP_SNIPPET_MAX_BYTES + 1)})
    with pytest.raises(ValueError, match="Unsupported language"):
        B.validate_snippet_arguments({**base, "language": "Ruby"})
    with pytest.raises(ValueError, match="Invalid snippet arguments"):
        B.validate_snippet_arguments({"filename": "x"})
    assert B.new_scan_id() and len(B.new_scan_id()) == 32


def test_handle_mcp_request_branches():
    import modules.services.mcp_bridge as B

    assert B.handle_mcp_request({"id": 1})["error"]["code"] == -32600
    assert B.handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "ping"})["result"] == {}
    init = B.handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init["result"]["serverInfo"]["name"] == "secure-mitigation-system"
    assert B.handle_mcp_request(
        {"jsonrpc": "2.0", "id": 1, "method": "notifications/initialized"}
    )["result"] == {}
    tools = B.handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert tools["result"]["tools"]
    listed = B.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        }
    )
    assert listed["error"]["code"] == -32602
    blocked = B.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "sms_scan_source", "arguments": {}},
        }
    )
    assert blocked["error"]["code"] == -32001
    bad = B.handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "bogus"})
    assert bad["error"]["code"] == -32601
    status = B.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "sms_scan_status", "arguments": {}},
        }
    )
    assert status["result"]["structuredContent"]["done"] is True


# --- sms_api pure builders: redaction + receipt chain ---


def test_build_ingest_event_redacts_credentials():
    from modules.services.sms_api import build_ingest_event

    evt = build_ingest_event(repo_url="https://user:pass@github.com/o/r?x=1", sha="abcdef123456")
    assert evt["team"] == "ingest"
    assert "@" not in evt["msg"] and "user" not in evt["msg"] and "pass" not in evt["msg"]
    assert "github.com" in evt["msg"] and "abcdef123456" in evt["msg"]
    bad = build_ingest_event(repo_url="not a url", sha="")
    assert bad["msg"].startswith("Ingest: ")
    assert isinstance(evt["ts"], float)


def _receipt_fixture(patch=b"patch-bytes", pre=0, post=1):
    import hashlib

    from modules.workflows.workflow import VerdictReceipt

    return VerdictReceipt(
        fixture="node_query_sink",
        pre_exit_code=pre,
        post_exit_code=post,
        regression_passed=True,
        differential_passed=True,
        property_exit_code=None,
        property_passed=None,
        patch_sha256=hashlib.sha256(patch).hexdigest(),
    )


def test_verify_receipt_genesis_valid_chain_false_and_linked_ok():
    from modules.services.sms_api import verify_receipt

    genesis = _receipt_fixture()
    out = verify_receipt(genesis.model_dump())
    assert out == {
        "valid": True,
        "chain_ok": False,
        "fixture": "node_query_sink",
        "expected": {
            "fixture": "node_query_sink",
            "pre_exit_code": 0,
            "post_exit_code": 1,
            "regression_passed": True,
        },
    }
    linked = _receipt_fixture()
    linked.prev_receipt_sha = linked.patch_sha256
    chained = verify_receipt(linked.model_dump())
    assert chained["valid"] is True and chained["chain_ok"] is True


def test_verify_receipt_bad_chain_link_and_bad_exits():
    from modules.services.sms_api import verify_receipt

    r = _receipt_fixture()
    r.prev_receipt_sha = "f" * 64
    assert verify_receipt(r.model_dump())["valid"] is False
    bad_exits = _receipt_fixture(pre=9)
    assert verify_receipt(bad_exits.model_dump())["reason"].startswith("exit codes")
    short_digest = _receipt_fixture()
    short_digest.patch_sha256 = "abc"
    assert verify_receipt(short_digest.model_dump())["reason"].startswith("patch_sha256")
    assert verify_receipt({"fixture": "x"})["valid"] is False


def test_build_result_hud_object_and_missing_fields():
    from modules.services.sms_api import build_result_hud

    class Obj:
        hud_tokens = {"raw": "100", "sent": "bad", "saved": 10, "ratio": 2.0}
        hud_vault = {"novel": 1, "known": "x", "recall": "r", "namespaces": "ns1"}

    hud = build_result_hud(Obj())
    assert hud["hud_tokens"]["raw"] == 100
    assert hud["hud_tokens"]["sent"] == 0
    assert hud["savings_pct"] == 10.0
    assert hud["hud_vault"]["namespaces"] == ["ns1"]
    empty = build_result_hud({})
    assert empty["hud_vault"]["recall"] == "Not reported"
    assert empty["novel_vs_historical"] == "0 novel vs 0 historical"


# --- projects: snapshot digests, secret content, replace guards ---


def test_snapshot_digest_orders_and_binds_mode_and_bytes(tmp_path):
    from modules.services.projects import ProjectSpec, _make_snapshot, snapshot_project

    (tmp_path / "a.py").write_text("print(1)\n")
    spec = ProjectSpec(
        path=tmp_path, command=["python3", "a.py"], test_command=["python3", "-m", "unittest"], contract="c"
    )
    snap = snapshot_project(spec)
    assert snap.digest and len(snap.digest) == 64
    assert snap.binary_files == ()
    twin = _make_snapshot(dict(snap.files), dict(snap.metadata), dict(snap.skipped))
    assert twin.digest == snap.digest
    assert snap.total_bytes == sum(len(v) for v in snap.files.values())


def test_cannot_decode_and_secret_prefilter(tmp_path):
    from modules.services.projects import _cannot_decode_utf8, _contains_secret_material

    assert _cannot_decode_utf8(b"\xff\xfe bad") is True
    assert _cannot_decode_utf8(b"plain") is False
    assert _contains_secret_material(b"-----BEGIN PRIVATE KEY-----\nx") is True
    assert _contains_secret_material(b"token ghp_" + b"a" * 36) is True
    assert _contains_secret_material(b"hello world") is False
    assert _contains_secret_material(b"\xff\xfe") is False


def test_replace_snapshot_guards_and_paths(tmp_path):
    from modules.services.projects import ProjectSpec, replace_snapshot_files, snapshot_project

    (tmp_path / "a.py").write_text("print(1)\n")
    spec = ProjectSpec(
        path=tmp_path, command=["python3", "a.py"], test_command=["python3", "-m", "unittest"], contract="c"
    )
    snap = snapshot_project(spec)
    assert replace_snapshot_files(snap, {}) is snap
    with pytest.raises(ValueError, match="not in the original"):
        replace_snapshot_files(snap, {"ghost.py": b"x"})
    with pytest.raises(TypeError, match="bytes or UTF-8"):
        replace_snapshot_files(snap, {"a.py": 123})
    with pytest.raises(ValueError, match="exceeds"):
        replace_snapshot_files(snap, {"a.py": b"x" * 9_999_999})
    again = replace_snapshot_files(snap, {"a.py": "print(2)\n"})
    assert again.files["a.py"] == b"print(2)\n"
    assert again.digest != snap.digest


def test_validate_relative_path_rejects_dot_segments():
    from modules.services.projects import _validate_relative_path

    for bad in ("", "/abs", "a/../b", "./a", "a/./b", "..", "a\\b"):
        with pytest.raises(ValueError, match="unsafe"):
            _validate_relative_path(bad)
    assert _validate_relative_path("src/app.py").as_posix() == "src/app.py"


# --- project_agents pure validators and leaders (no Muse calls) ---


def test_source_chunk_bounds_and_outcome_guards():
    from modules.services.project_agents import RedReport, SourceChunk

    good = SourceChunk(
        path="a.py",
        content="hi",
        start_byte=0,
        end_byte=2,
        file_size_bytes=2,
        sha256="a" * 64,
    )
    assert good.end_byte == 2
    with pytest.raises(Exception, match="byte range"):
        SourceChunk(
            path="a.py",
            content="hi",
            start_byte=2,
            end_byte=5,
            file_size_bytes=10,
            sha256="a" * 64,
        )
    with pytest.raises(Exception, match="byte range"):
        SourceChunk(
            path="a.py",
            content="hey",
            start_byte=0,
            end_byte=2,
            file_size_bytes=3,
            sha256="a" * 64,
        )
    ok = RedReport(
        outcome="finding",
        vulnerability="v",
        affected_paths=["a.py"],
        analysis_summary="s",
        verification_script_python="print(1)",
    )
    assert ok.outcome == "finding"
    with pytest.raises(Exception, match="finding requires"):
        RedReport(outcome="finding", analysis_summary="s")
    with pytest.raises(Exception, match="no-finding"):
        RedReport(
            outcome="no_finding", analysis_summary="s", vulnerability="v"
        )


def test_compact_indices_and_focus_labels():
    from modules.services.project_agents import _compact_worker_indices, _safe_focus_labels

    assert _compact_worker_indices([]) == "none"
    assert _compact_worker_indices([1, 2, 3, 5, "x", -1, 2]) == "1-3, 5"
    assert _compact_worker_indices([True, 1.5, None]) == "none"
    assert _safe_focus_labels(["  a\nb  ", 123, "", "x" * 100]) == ["a b", "x" * 48]
    assert _safe_focus_labels([]) == []


def test_leader_messages_and_batch_guards():
    from modules.services.project_agents import (
        blue_leader_decision_message,
        build_source_batches,
        red_leader_decision_message,
    )

    class Assign:
        def __init__(self, i):
            self.agent_index = i

    class Plan:
        assignments = [Assign(1), Assign("bad"), Assign(3)]

    red = red_leader_decision_message(Plan(), cycle="x", pass_number=2, focus=["  hi\nthere  "])
    assert "hunters" in red and "hi there" in red
    blue = blue_leader_decision_message(Plan(), cycle=1, pass_number=1)
    assert "defenders" in blue and "routine sweep" in blue

    with pytest.raises(ValueError, match="max_batch_bytes"):
        build_source_batches([], max_batch_bytes=10)
    from modules.services.project_agents import SourceDocument, build_source_batches

    d = SourceDocument(path="a.py", content="x")
    e2 = SourceDocument(path="a.py", content="y")
    with pytest.raises(ValueError, match="unique"):
        build_source_batches([d, e2], max_batch_bytes=2048)


def test_build_source_batches_empty_doc_and_notes():
    from modules.services.project_agents import SourceDocument, build_source_batches

    empty = SourceDocument(path="e.py", content="")
    batches, coverage = build_source_batches([empty], max_batch_bytes=2048)
    assert coverage.total_paths == 1 and coverage.complete is True
    assert "UTF-8" in coverage.notes[0]


# --- tags registry binding branches ---


def test_binding_live_all_surfaces(tmp_path):
    from library import tags as T

    (tmp_path / "main.py").write_text("--serve --port 1")
    entry = {"backend": "main.py:main", "cli": "--serve", "ui": "chip-x", "tui": "run_plain"}
    assert T._binding_live({"backend": "no-colon"}, "api", tmp_path) is False
    assert T._binding_live({"backend": "web/app.html:tok"}, "api", tmp_path) is False
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "app.html").write_text("tok")
    assert T._binding_live({"backend": "web/app.html:tok"}, "api", tmp_path) is True
    assert T._binding_live({"backend": "missing.py:main"}, "api", tmp_path) is False
    REPO = Path(__file__).resolve().parent.parent
    assert T._binding_live({"backend": "main.py:main"}, "api", REPO) is True
    assert T._binding_live({"backend": "main.py:main", "cli": ""}, "cli", tmp_path) is False
    (tmp_path / "sms_cli.py").write_text("--serve")
    assert T._binding_live({"backend": "x", "cli": "--serve"}, "cli", tmp_path) is True
    assert T._binding_live({"backend": "x", "cli": ""}, "cli", tmp_path) is False
    assert T._binding_live({"backend": "x", "ui": ""}, "web", tmp_path) is False
    assert T._binding_live({"backend": "x", "tui": ""}, "tui", tmp_path) is False
    assert T._binding_live({"backend": "x"}, "bogus", tmp_path) is False
    (tmp_path / "tui.py").write_text("run_plain select:foo")
    assert T._binding_live({"tui": "run_plain"}, "tui", tmp_path) is True
    assert T._binding_live({"tui": "select:foo"}, "tui", tmp_path) is True


def test_check_registry_marks_missing_and_counts(tmp_path):
    from library import tags as T

    (tmp_path / "main.py").write_text("--serve")
    fake = {
        "good": {"surfaces": ["cli"], "cli": "--serve"},
        "bad": {"surfaces": ["cli"], "cli": "--missing-flag"},
    }
    out = T.check_registry(fake, root=tmp_path)
    assert out["covered_count"] == 1 and out["total"] == 2
    assert "bad" in out["uncovered"] and "good" in out["covered"]
    empty = T.check_registry({}, root=tmp_path)
    assert empty == {"covered": {}, "uncovered": {}, "covered_count": 0, "total": 0}


def test_load_module_resolves_canonical_package():
    from library import tags as T

    assert T._load_module("library.tags") is T

