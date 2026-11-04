# LAWs 0, 8, 9 govern this task (RED-first: failing test before implementation).
"""R2 services gap tests — uncovered validator/parser branches.

Scope: library/services/mcp_bridge.py + repo_intake.py + projects.py +
binary_intake.py (pure validators/parsers/detectors ONLY — never live
Muse/Docker/network). Mirror existing test doubles: real validators, no
mocks of the unit under test.
"""

from __future__ import annotations

import pytest

ELF = b"\x7fELF" + b"\x00" * 60
PE = b"MZ" + b"\x00" * 62
MACHO = b"\xcf\xfa\xed\xfe" + b"\x00" * 60
MACHO_LEGACY = b"\xce\xfa\xed\xfe" + b"\x00" * 60
MACHO_FAT = b"\xca\xfe\xba\xbe" + b"\x00" * 60

GOOD_URL = "https://github.com/example/demo"
GOOD_HASH = "a" * 40


# --- binary_intake: Mach-O legacy/fat magics, boundary caps, unreadable path ---


def test_detect_format_all_macho_magics():
    from modules.services.binary_intake import detect_binary_format

    assert detect_binary_format(ELF) == "elf"
    assert detect_binary_format(PE) == "pe"
    assert detect_binary_format(MACHO) == "macho"
    assert detect_binary_format(MACHO_LEGACY) == "macho"
    assert detect_binary_format(MACHO_FAT) == "macho"
    assert detect_binary_format(b"#!/bin/sh\n") is None
    assert detect_binary_format(b"") is None


def test_validate_blob_long_filename_and_overlong_contract():
    from modules.services.binary_intake import BinaryRejected, validate_binary_blob

    with pytest.raises(BinaryRejected, match="128"):
        validate_binary_blob(ELF, filename="x" * 129, contract="c")
    with pytest.raises(BinaryRejected, match="8 KiB"):
        validate_binary_blob(ELF, filename="t.elf", contract="c" * (8192 + 1))
    ok = validate_binary_blob(ELF, filename="x" * 128, contract="c" * 8192)
    assert ok.size_bytes == len(ELF) and ok.binary_format == "elf"


def test_validate_blob_empty_and_oversize_and_dotfile_and_backslash():
    from modules.services.binary_intake import (
        BINARY_MAX_BYTES,
        BinaryRejected,
        validate_binary_blob,
    )

    with pytest.raises(BinaryRejected, match="empty"):
        validate_binary_blob(b"", filename="t.elf", contract="c")
    with pytest.raises(BinaryRejected, match="8 MiB"):
        validate_binary_blob(
            b"\x7fELF" + b"\x00" * BINARY_MAX_BYTES, filename="t.elf", contract="c"
        )
    with pytest.raises(BinaryRejected, match="bare filename"):
        validate_binary_blob(ELF, filename=".hidden.elf", contract="c")
    with pytest.raises(BinaryRejected, match="bare filename"):
        validate_binary_blob(ELF, filename="sub\\t.elf", contract="c")
    with pytest.raises(BinaryRejected, match="whitespace|contract|behavior"):
        validate_binary_blob(ELF, filename="t.elf", contract="   ")


def test_validate_binary_file_rejects_missing_and_reads_magic(tmp_path):
    from modules.services.binary_intake import BinaryRejected, validate_binary_file

    with pytest.raises(BinaryRejected, match="Cannot read"):
        validate_binary_file(str(tmp_path / "nope.elf"), contract="c")
    target = tmp_path / "ok.elf"
    target.write_bytes(MACHO_FAT)
    spec = validate_binary_file(str(target), contract="c")
    assert spec.binary_format == "macho" and spec.filename == "ok.elf"


# --- projects: secret files/suffixes, snapshot budget guards, binary detection ---


def test_is_secret_file_names_and_suffixes():
    from modules.services.projects import _is_secret_file

    assert _is_secret_file("src/app.py") is False
    assert _is_secret_file(".env") is True
    assert _is_secret_file(".env.production") is True
    assert _is_secret_file(".ENV") is True
    assert _is_secret_file("id_rsa") is True
    assert _is_secret_file("key.PEM") is True
    assert _is_secret_file("archive.tar") is False


def test_contains_secret_material_all_patterns():
    from modules.services.projects import _contains_secret_material

    assert _contains_secret_material(b"-----BEGIN RSA PRIVATE KEY-----\nx") is True
    assert _contains_secret_material(b"key AKIA" + b"A" * 16) is True
    assert _contains_secret_material(b"token ghp_" + b"a" * 36) is True
    assert _contains_secret_material(b"hook xoxb-" + b"a" * 10) is True
    assert _contains_secret_material(b"live sk_live_" + b"a" * 24) is True
    assert _contains_secret_material(b"key sk-ant-" + b"a" * 20) is True
    assert _contains_secret_material(b"mention AKIA and nothing else") is False


def test_snapshot_project_skips_and_caps(tmp_path):
    from modules.services import projects as P
    from modules.services.projects import ProjectSpec, snapshot_project

    (tmp_path / "ok.py").write_text("print(1)\n")
    (tmp_path / "secret.pem").write_text("x")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x")
    spec = ProjectSpec(
        path=tmp_path,
        command=["python3", "ok.py"],
        test_command=["python3", "-m", "unittest"],
        contract="c",
    )
    snap = snapshot_project(spec)
    assert "secret.pem" in snap.skipped
    assert any(str(k).startswith(".git") for k in snap.skipped)
    assert "ok.py" in snap.files

    (tmp_path / "big.bin").write_bytes(b"\x00" * 100)
    bin_snap = snapshot_project(spec, max_files=100)
    assert "big.bin" in bin_snap.binary_files

    with pytest.raises(ValueError, match="more than"):
        snapshot_project(spec, max_files=1)
    with pytest.raises(ValueError, match="exceeds"):
        snapshot_project(spec, max_file_bytes=4)
    tiny = dict(snap.files)
    with pytest.raises(ValueError, match="exceeds"):
        P.replace_snapshot_files(
            snap,
            {"ok.py": b"x" * (sum(map(len, tiny.values())) + 1)},
            max_total_bytes=sum(map(len, tiny.values())),
        )


def test_snapshot_project_rejects_empty_and_special(tmp_path):
    from modules.services.projects import ProjectSpec, snapshot_project

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no included"):
        snapshot_project(ProjectSpec(path=empty, command=["x"], test_command=["y"], contract="c"))
    with pytest.raises(ValueError, match="positive"):
        snapshot_project(
            ProjectSpec(path=tmp_path, command=["x"], test_command=["y"], contract="c"),
            max_files=0,
        )


def test_snapshot_digest_binds_content_and_mode():
    from modules.services.projects import ProjectFileMetadata, _make_snapshot

    files = {"a.py": b"print(1)\n"}
    meta = {"a.py": ProjectFileMetadata(size=9, mode=0o644)}
    first = _make_snapshot(files, meta)
    second = _make_snapshot(files, {"a.py": ProjectFileMetadata(size=9, mode=0o755)})
    assert first.digest != second.digest
    third = _make_snapshot({"a.py": b"print(2)\n"}, meta)
    assert third.digest != first.digest
    assert first.total_bytes == 9


# --- repo_intake: spec guards, normalise branches, precedence, manifest digest ---


def test_repo_spec_rejects_all_bad_shapes():
    from modules.services.repo_intake import RepoIntakeSpec

    good = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    assert good.url == GOOD_URL
    for bad_url in (
        "http://github.com/o/r",
        "git://github.com/o/r",
        "git@github.com:o/r.git",
        "https://github.com/o/r; rm -rf /",
        "https://github.com/o/r`id`",
        "https://",
        "https://a..b/o/r",
        "https:///o/r",
    ):
        with pytest.raises(ValueError, match="https"):
            RepoIntakeSpec(url=bad_url, commit_hash=GOOD_HASH)
    for bad_hash in ("", "abc", "g" * 40, "a" * 39, "a" * 41, 123):
        with pytest.raises(ValueError, match="commit_hash"):
            RepoIntakeSpec(url=GOOD_URL, commit_hash=bad_hash)


def test_normalise_snapshot_mapping_and_bytes_and_errors():
    from modules.services.repo_intake import _normalise_file_entries

    class Snap:
        files = {"app.py": b"print(1)", "bin/x": b"\xff\xfe"}

    assert _normalise_file_entries(Snap()) == (("app.py", "print(1)"), ("bin/x", None))
    assert _normalise_file_entries({"a.py": "x"}) == (("a.py", "x"),)

    class Weird:
        @property
        def files(self):
            return 42

    # Non-mapping .files without .items() normalises to empty (fail closed
    # downstream in detect_runtime), never raises here.
    assert _normalise_file_entries(Weird()) == ()
    with pytest.raises(ValueError, match="non-empty strings"):
        _normalise_file_entries(["  "])
    with pytest.raises(ValueError, match="str, bytes"):
        _normalise_file_entries([("a.py", 123)])


def test_detect_runtime_precedence_and_content_forms():
    from modules.services.repo_intake import detect_runtime

    both = {"package.json": '{"scripts": {}}', "requirements.txt": "", "app.py": ""}
    assert detect_runtime(both) == ["npm", "start"]
    both2 = {"composer.json": "{}", "requirements.txt": "", "app.py": ""}
    # _DETECT_PRECEDENCE puts composer.json above python: php wins.
    assert detect_runtime(both2) == ["php", "index.php"]
    php_make = {"composer.json": "{}", "index.php": "", "Makefile": "run:\n\tx\n"}
    assert detect_runtime(php_make) == ["php", "index.php"]
    assert detect_runtime([{"Makefile": "zzz:\n\tx\n"}]) == ["make", "zzz"]
    # app.py is itself an entry candidate: resolves to app.py, not fallback.
    assert detect_runtime([("app.py", "x"), ("pyproject.toml", "")]) == ["python3", "app.py"]
    assert detect_runtime([("other.py", "x"), ("pyproject.toml", "")]) == ["python3", "main.py"]
    # Bare-name fallback: repo-named top-level module (anycam.py in AnyCam),
    # then a lone top-level .py. Old behavior (main.py guess) preserved
    # when neither applies.
    assert detect_runtime([("anycam.py", "x"), ("requirements.txt", "")], "AnyCam") == [
        "python3",
        "anycam.py",
    ]
    assert detect_runtime([("only.py", "x"), ("requirements.txt", "")], "Whatever") == [
        "python3",
        "only.py",
    ]
    # No repo name, no bare fallback: old main.py guess preserved.
    assert detect_runtime([("only.py", "x"), ("requirements.txt", "")]) == [
        "python3",
        "main.py",
    ]
    assert detect_runtime([("a.py", "x"), ("b.py", "y"), ("requirements.txt", "")], "R") == [
        "python3",
        "main.py",
    ]
    with pytest.raises(ValueError, match="could not detect"):
        detect_runtime(["notes.txt"])
    with pytest.raises(ValueError, match="could not detect"):
        detect_runtime([])


def test_package_and_makefile_content_variants():
    from modules.services.repo_intake import _makefile_command, _package_json_command

    assert _package_json_command('{"main": "  "}') == ["npm", "start"]
    assert _package_json_command('{"scripts": {"start": "x"}, "main": "srv.js"}') == [
        "npm",
        "start",
    ]
    assert _package_json_command('{"scripts": "nope"}') == ["npm", "start"]
    assert _package_json_command('["not", "a", "dict"]') == ["npm", "start"]
    assert _makefile_command("") == ["make"]
    assert _makefile_command("run:\n\tx\nrun:\n\ty\n") == ["make", "run"]


def test_safe_relpath_and_basename():
    from modules.services.repo_intake import _basename, _safe_relpath

    # Dot segments are dropped in place (not resolved): a/b/../c -> a/b/c.
    assert _safe_relpath("  a\\b\\..\\c  ") == "a/b/c"
    assert _safe_relpath("/abs/path") == "abs/path"
    assert _basename("src/app.py") == "app.py"
    assert _basename("top.py") == "top.py"


def test_intake_manifest_digest_and_plan_shape():
    import json

    from modules.services.repo_intake import (
        RepoIntakeSpec,
        _manifest_digest,
        intake_repo_to_snapshot,
    )

    spec = RepoIntakeSpec(url=GOOD_URL, commit_hash=GOOD_HASH)
    snap = intake_repo_to_snapshot(spec, ["python3", "main.py"])
    assert snap.digest == _manifest_digest(spec, ("python3", "main.py"))
    assert snap.files["repo.url"] == GOOD_URL.encode()
    assert json.loads(snap.files["repo.runtime_command"]) == ["python3", "main.py"]
    auto = intake_repo_to_snapshot(spec, file_list=["composer.json", "index.php"])
    assert auto.runtime_command == ("php", "index.php")
    with pytest.raises(ValueError, match="file_list"):
        intake_repo_to_snapshot(spec)
    with pytest.raises(ValueError, match="non-empty argv"):
        intake_repo_to_snapshot(spec, runtime_command=[])
    with pytest.raises(ValueError, match="non-empty strings"):
        intake_repo_to_snapshot(spec, runtime_command=["ok", ""])
    with pytest.raises(ValueError, match="RepoIntakeSpec"):
        intake_repo_to_snapshot("nope", ["npm", "start"])
    with pytest.raises(TypeError, match="host paths"):
        intake_repo_to_snapshot(spec, ["npm", "start"], host_path="/tmp/x")


# --- mcp_bridge: schema surface, language map, dispatch samples, validators ---


def test_mcp_language_filename_and_suffix_maps():
    from modules.services.mcp_bridge import SNIPPET_FILENAME_BY_LANGUAGE, SNIPPET_LANGUAGE_BY_SUFFIX

    assert SNIPPET_FILENAME_BY_LANGUAGE == {
        "javascript": "app.js",
        "python": "app.py",
        "php": "index.php",
    }
    assert SNIPPET_LANGUAGE_BY_SUFFIX[".mjs"] == "javascript"
    assert SNIPPET_LANGUAGE_BY_SUFFIX[".py"] == "python"


def test_snippet_schema_definitions():
    from modules.services import mcp_bridge as B

    schema = B.snippet_input_schema()
    assert schema["properties"]["language"]["enum"] == ["javascript", "python", "php"]
    assert schema["additionalProperties"] is False
    out = B.snippet_output_schema()
    assert {"status", "pre_probe_exit", "post_probe_exit"} <= set(out["required"])
    tool = B.snippet_tool_definition()
    assert tool["name"] == "submit_code_snippet"
    assert B.MCP_TOOLS and len(B.MCP_TOOLS) == 11
    src = B.sms_scan_source_tool_definition()
    assert src["inputSchema"]["properties"]["max_passes"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 5,
    }
    binary = B.sms_scan_binary_tool_definition()
    assert "blob_b64" in binary["inputSchema"]["properties"]
    stats = B.sms_query_vault_stats_tool_definition()
    assert stats["outputSchema"]["properties"] == {"stats": {"type": "object"}}
    verify = B.sms_verify_receipt_tool_definition()
    assert "patch_sha256" in verify["inputSchema"]["required"]
    status = B.sms_scan_status_tool_definition()
    assert status["inputSchema"]["properties"] == {"scan_id": {"type": "string", "maxLength": 64}}


def test_snippet_validation_language_case_and_source_bytes():
    from modules.services import mcp_bridge as B

    args = B.validate_snippet_arguments(
        {"filename": "a.js", "language": "  JavaScript ", "source": "x", "contract": "c"}
    )
    assert args.normalized_language() == "javascript"
    assert B.snippet_baseline_key(args) == "node_query_sink"
    assert B.snippet_target(args).command[0] == "node"
    assert B.snippet_target(args).filename == "app.js"
    # Char count fits but UTF-8 bytes exceed the cap: hits the byte-budget
    # branch (not the pydantic char-length branch).
    with pytest.raises(ValueError, match="exceeds the 64 KiB"):
        B.validate_snippet_arguments(
            {
                "filename": "ok.py",
                "language": "python",
                "source": "\u00e9" * (B.MCP_SNIPPET_MAX_BYTES // 2 + 1),
                "contract": "c",
            }
        )


def test_structured_result_and_wrap_samples():
    from modules.services import mcp_bridge as B
    from modules.services.mcp_bridge import McpSnippetArguments

    args = McpSnippetArguments(filename="a.py", language="python", source="print(1)", contract="c")
    reg = B.mcp_registry_with_snippet(args)
    assert "mcp_snippet" in reg and reg["mcp_snippet"].filename == "app.py"

    class R:
        status = "verified"
        message = "ok"
        pre_exit_code = 0
        post_exit_code = 1
        regression_passed = True
        cleanup_ok = False
        receipt = None

    out = B.structured_result(R())
    assert (out["pre_probe_exit"], out["post_probe_exit"]) == (0, 1)
    assert out["cleanup_ok"] is False and out["receipt"] is None
    wrapped = B._wrap_tool_result(3, {"k": "v", "gone": None})
    assert "gone" not in wrapped["result"]["content"][0]["text"]


def test_handle_mcp_status_and_vault_samples():
    import modules.services.mcp_bridge as B

    B._SCAN_REGISTRY.clear()
    B.scan_status_register("s-9", phase="blue")
    got = B.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "sms_scan_status", "arguments": {"scan_id": "s-9"}},
        }
    )
    assert got["result"]["structuredContent"]["phase"] == "blue"
    long_id = B.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "sms_scan_status", "arguments": {"scan_id": "x" * 100}},
        }
    )
    assert long_id["result"]["structuredContent"]["scan_id"] == "x" * 64
    stats = B.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "sms_query_vault_stats"},
        }
    )
    assert "stats" in stats["result"]["structuredContent"]
    receipt = B.handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "sms_verify_receipt", "arguments": {"fixture": "x"}},
        }
    )
    assert receipt["result"]["structuredContent"]["valid"] is False
    B._SCAN_REGISTRY.clear()
