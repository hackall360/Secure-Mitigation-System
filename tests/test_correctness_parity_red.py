# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""X6 (correctness deep-validation round 4): binary/MCP/API/TUI parity pins.

Live-proven gaps from the round-4 survey:
1. Binary intake adversarial matrix (text/missing/empty/path-contract/filename).
2. Blob magic: ELF/Mach-O/PE detected; shell/empty rejected.
3. MCP verify_receipt: good receipt valid, malformed -> valid=False (never raises).
4. MCP vault-stats shape: red/blue/green/known_archetypes keys.
5. Dashboard /api/* contracts: /api/health + /api/targets shapes live.
6. TUI routing: all four scan modes reach their workflow (no bypass).
"""

from fastapi.testclient import TestClient

import main
from modules.core.config import PurpleBoxConfig
from modules.services import binary_intake as BI
from modules.services import sms_api as A


def test_binary_intake_elf_passes_text_missing_rejected():
    spec = BI.validate_binary_file("targets/binary_argv_echo/echo", contract="c")
    assert spec.binary_format == "elf"
    assert spec.size_bytes > 0
    for bad, frag in [
        ("targets/node_query_sink/app.js", "Not a recognized compiled binary"),
        ("nonexistent.bin", "Cannot read binary file"),
    ]:
        try:
            BI.validate_binary_file(bad, contract="c")
            raise AssertionError(f"{bad} accepted")
        except BI.BinaryRejected as exc:
            assert frag in str(exc)


def test_binary_intake_filename_contract_bounds():
    elf = open("targets/binary_argv_echo/echo", "rb").read()
    for kw, frag in [
        ({"filename": "../evil", "contract": "c"}, "bare filename"),
        ({"filename": "x" * 129, "contract": "c"}, "128 characters"),
        ({"filename": "a.bin", "contract": ""}, "contract"),
        ({"filename": "a.bin", "contract": "x" * (BI.BINARY_CONTRACT_MAX_CHARS + 1)}, "8 KiB"),
        ({"filename": "a.bin", "contract": "c"}, "empty"),
    ]:
        blob = b"" if frag == "empty" else elf
        try:
            BI.validate_binary_blob(blob, **kw)
            raise AssertionError(f"{kw} accepted")
        except BI.BinaryRejected as exc:
            assert frag in str(exc), f"{kw}: {exc}"


def test_blob_magic_matrix():
    elf = open("targets/binary_argv_echo/echo", "rb").read()
    assert BI.detect_binary_format(elf) == "elf"
    assert BI.detect_binary_format(b"MZ" + b"\x90" * 64) == "pe"
    assert BI.detect_binary_format(b"\x7fELF" + b"\x00" * 16) == "elf"
    assert BI.detect_binary_format(b"#!/bin/sh\necho hi") is None
    assert BI.detect_binary_format(b"") is None
    for magic in BI._MACHO_MAGICS:
        assert BI.detect_binary_format(magic + b"\x00" * 64) == "macho"


def test_mcp_verify_receipt_good_bad():
    good = {
        "fixture": "node_query_sink",
        "pre_exit_code": 0,
        "post_exit_code": 1,
        "regression_passed": True,
        "differential_passed": True,
        "patch_sha256": "a" * 64,
    }
    out = A.verify_receipt(good)
    assert out["valid"] is True
    bad = A.verify_receipt({"fixture": "x"})
    assert bad["valid"] is False
    assert "reason" in bad


def test_mcp_vault_stats_shape():
    stats = A.query_vault_stats()
    assert isinstance(stats, dict)
    assert {"red", "blue", "green", "known_archetypes"} <= set(stats)


def test_dashboard_api_contracts():
    app = main.create_app(PurpleBoxConfig(meta_api_key="k"))
    with TestClient(app, base_url="http://localhost") as client:
        health = client.get("/api/health").json()
        assert health["version"] == "0.14.0"
        assert health["inference_ready"] is True
        assert health["api_key_configured"] is True
        assert health["docker"]["state"] == "ready"
        assert set(health["profiles"][0]) >= {"key", "label"}
        targets = client.get("/api/targets").json()
        assert set(targets) == {
            "node_query_sink",
            "node_chain_link",
            "php_command_sink",
            "mysql_insecure_conf",
            "binary_argv_echo",
        }


def test_snippet_filename_map_single_sourced():
    """C1 identity pin: TUI default snippet filenames ARE the bridge canonicals.

    Two maps with the same keys but different values (snippet.* vs app.*)
    are a drift vector: the executor runs /workspace/<baseline filename>,
    so any surface inventing its own default filename silently misnames the
    executed file. Both surfaces must resolve through
    mcp_bridge.SNIPPET_FILENAME_BY_LANGUAGE.
    """
    from modules.services import mcp_bridge

    assert mcp_bridge.SNIPPET_FILENAME_BY_LANGUAGE == {
        "javascript": "app.js",
        "python": "app.py",
        "php": "index.php",
        # OMNI-INGEST: compiled snippet filenames (single-sourced).
        "c": "snippet.c",
        "rust": "snippet.rs",
        "go": "snippet.go",
    }
    import tui

    assert tui._SNIPPET_FILENAME_BY_LANGUAGE is mcp_bridge.SNIPPET_FILENAME_BY_LANGUAGE


def test_tui_all_modes_reach_workflows():
    import inspect

    import tui

    src = inspect.getsource(tui)
    for mode, fn in [
        ("fixture", "execute_purple_workflow"),
        ("sweep", "execute_sweep_scan"),
        ("binary", "execute_binary_sweep"),
        ("project", "execute_project_workflow"),
    ]:
        assert fn in src, f"TUI {mode} bypasses {fn}"
