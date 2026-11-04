# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): MISSION OMNI-INGEST Wave 1 — PreScanObserver kills UNSUPPORTED.

Fail-closed is for security verdicts, not language support. The intake
matrix must detect C/Rust/Go ecosystems, map them to required toolchains,
and emit a runnable/buildable command — never raise UNSUPPORTED.

Contract:
- `observe_ecosystem(names) -> EcosystemReport`: pure function on staged
  relpaths. Detects rust (Cargo.toml/lock), go (go.mod/go.sum),
  c (CMakeLists.txt, *.c/*.h, Kconfig), python, node, php, make.
- `required_toolchains(report) -> tuple[str, ...]`: e.g. rust -> (cargo,
  rustc), go -> (go,), c -> (gcc or clang, make/cmake).
- `detect_runtime` NEVER raises "unsupported runtime": Go/Rust/C trees
  resolve to a build-or-serve argv (cargo test / go test / make / cmake
  build, or thick-image generic `sh` probe when nothing matches).
- LAW 3 fallback: unknown trees resolve to the thick-image generic probe,
  never ValueError.
"""

from __future__ import annotations


def test_observer_detects_polyglot_ecosystems():
    from modules.services.repo_intake import observe_ecosystem

    assert observe_ecosystem(["Cargo.toml", "src/main.rs"]).ecosystem == "rust"
    assert observe_ecosystem(["go.mod", "main.go"]).ecosystem == "go"
    assert observe_ecosystem(["CMakeLists.txt", "src/main.c"]).ecosystem == "c-cmake"
    assert observe_ecosystem(["src/main.c"]).ecosystem == "c"
    assert observe_ecosystem(["Makefile", "app.py"]).ecosystem in ("python", "make")
    assert observe_ecosystem(["package.json"]).ecosystem == "node"


def test_observer_maps_toolchains():
    from modules.services.repo_intake import observe_ecosystem, required_toolchains

    assert "cargo" in required_toolchains(observe_ecosystem(["Cargo.toml"]))
    assert "go" in required_toolchains(observe_ecosystem(["go.mod"]))
    c_tools = required_toolchains(observe_ecosystem(["src/main.c", "Makefile"]))
    assert "make" in c_tools and ("gcc" in c_tools or "clang" in c_tools)


def test_no_unsupported_refusal_anywhere():
    from modules.services.repo_intake import detect_runtime

    for names, repo in [
        (["go.mod", "main.go"], "go-app"),
        (["Cargo.toml", "src/main.rs"], "rust-app"),
        (["CMakeLists.txt", "src/main.c"], "c-app"),
        (["src/main.c"], "c-bare"),
        (["notes.txt"], "mystery"),
    ]:
        got = detect_runtime(names, repo)  # must not raise
        assert isinstance(got, list) and len(got) >= 1, (names, got)


def test_polyglot_fallback_is_thick_image_probe():
    from modules.services.repo_intake import detect_runtime

    got = detect_runtime(["notes.txt"], "")
    assert got[0] in ("sh", "python3", "make"), got
