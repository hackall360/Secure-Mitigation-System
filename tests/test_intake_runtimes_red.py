# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): intake detect covers every runtime the target image can run — or refuses honestly.

The target image runs python3 + node + php (Dockerfile.target). But
detect_runtime only knows package.json/composer/python/makefile. A Go
repo (go.mod + main.go), a Rust repo (Cargo.toml), or a repo whose JS
entry is server.js instead of npm-start gets ValueError "pass an
explicit runtime_command" even though the harness CANNOT run go/cargo
at all and CAN serve .js over the wrapper. Two gaps:

1. Go/Rust repos fail with "pass explicit argv" — but no argv can work
   (no toolchain in image). The refusal must say the runtime is
   UNSUPPORTED, not ask for argv that cannot succeed.
2. JS repos without package.json scripts (server.js, index.js bare) fall
   through to ValueError instead of a node serve argv the image CAN run.
"""

from __future__ import annotations


def test_go_rust_refuse_as_unsupported_not_missing_argv():
    from modules.services.repo_intake import detect_runtime

    for names in (["go.mod", "main.go"], ["Cargo.toml", "src/main.rs"]):
        try:
            detect_runtime(names, "someapp")
        except ValueError as exc:
            assert "nnot detect" not in str(exc), (
                f"{names}: must not ask for argv for an unrunnable toolchain"
            )
            assert "nsupported" in str(exc), f"{names}: must name UNSUPPORTED, got: {exc}"
            continue
        raise AssertionError(f"{names}: unexpectedly detected (no toolchain in image)")


def test_bare_js_detects_node_serve():
    from modules.services.repo_intake import detect_runtime

    assert detect_runtime(["server.js"], "someapp") == ["node", "server.js"]
    assert detect_runtime(["tree/index.js"], "") == ["node", "tree/index.js"]


def test_bare_name_beats_unsupported_manifest():
    # AnyCam regression (Q17): tree/anycam.py + rust/Cargo.lock must
    # resolve to the runnable entry — the unsupported manifest only wins
    # when NO runnable entry exists.
    from modules.services.repo_intake import detect_runtime

    assert detect_runtime(["tree/anycam.py", "tree/rust/Cargo.lock"], "AnyCam") == [
        "python3",
        "tree/anycam.py",
    ]
