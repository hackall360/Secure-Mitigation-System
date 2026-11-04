# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""OMNI-INGEST Wave 1: retired refusal pins — superseded, kept as history.

The tests below asserted the OLD behavior: Go/Rust trees raise UNSUPPORTED.
MISSION OMNI-INGEST deprecates that refusal — fail-closed is for security
verdicts, not language support. Go/Rust/C trees now resolve to build/test
argv (`cargo test` / `go test ./...` / `make` / cmake shape) that Wave 2
provisions for, and unknown trees resolve to the thick-image generic probe.

These pins are RETIRED (superseded by tests/test_omni_prescan_red.py).
They remain in-tree as documentation of the behavior change; the live
contract is asserted in test_omni_prescan_red.py::test_no_unsupported_refusal_anywhere.
"""

from __future__ import annotations


def test_go_rust_resolve_to_build_argv_not_refusal():
    from modules.services.repo_intake import detect_runtime

    assert detect_runtime(["go.mod", "main.go"], "someapp") == ["go", "test", "./..."]
    assert detect_runtime(["Cargo.toml", "src/main.rs"], "someapp") == ["cargo", "test"]


def test_bare_js_detects_node_serve():
    from modules.services.repo_intake import detect_runtime

    assert detect_runtime(["server.js"], "someapp") == ["node", "server.js"]
    assert detect_runtime(["tree/index.js"], "") == ["node", "tree/index.js"]


def test_bare_name_beats_polyglot_markers():
    # AnyCam (tree/anycam.py + rust/Cargo.lock): the runnable Python entry
    # still wins over the vestigial manifest — precedence preserved.
    from modules.services.repo_intake import detect_runtime

    assert detect_runtime(["tree/anycam.py", "tree/rust/Cargo.lock"], "AnyCam") == [
        "python3",
        "tree/anycam.py",
    ]
