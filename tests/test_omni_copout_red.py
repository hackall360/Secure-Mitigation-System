# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): cop-out audit leftovers — snippet gate + compiled source in wrapper.

Two REAL language cop-outs survive Wave 1 (Wave 1 fixed detect_runtime;
these are adjacent gates with the same "wrong language, no security" shape):

1. `submit_code_snippet` rejects every language except javascript/python/php
   (MCP_ALLOWED_LANGUAGES). A C/Rust/Go snippet cannot even enter the loop —
   same refusal shape as the deprecated UNSUPPORTED, one surface over.
2. The ingest service wrapper serves ONLY UTF-8-decodable text and raises
   ValueError when a tree has no servable text. A compiled repo whose tree
   carries .c/.rs/.go SOURCES is fine (sources are text), but the wrapper
   is still the only probe surface: red can fetch sources over HTTP but has
   no performed-build artifact to probe (no compiled binary behavior).

Contract:
- Snippet gate admits c, rust, go (verifier runs `gcc`/`cargo`/`go` where
  present; absent toolchain => exit 2 inconclusive, never a refusal).
- Wrapper keeps serving text sources AND records an `eco` manifest entry
  (`repo.ecosystem` + `repo.toolchains`) so Wave 2/v3 probes know what to
  provision — no behavior change to the serve path itself.
"""

from __future__ import annotations


def test_snippet_gate_admits_compiled_languages():
    from modules.services import mcp_bridge as B

    assert "c" in B.MCP_ALLOWED_LANGUAGES
    assert "rust" in B.MCP_ALLOWED_LANGUAGES
    assert "go" in B.MCP_ALLOWED_LANGUAGES


def test_wrapper_records_ecosystem_manifest():
    from types import MappingProxyType

    from modules.services.repo_intake import (
        RepoIntakeSnapshot,
        build_service_wrapper,
    )

    snap = RepoIntakeSnapshot(
        files=MappingProxyType(
            {
                "repo.url": b"https://github.com/e/d.git",
                "tree/main.c": b"int main(){return 0;}",
                "tree/README.md": b"hi",
            }
        ),
        url="https://github.com/e/d.git",
        commit_hash="a" * 40,
        runtime_command=("make",),
        digest="x",
    )
    wrapped = build_service_wrapper(snap)
    files = dict(wrapped.files)
    assert "main.c" in {k[5:] for k in files if k.startswith("tree/")}
    assert files.get("repo.ecosystem") == b"c"
    assert b"gcc" in files.get("repo.toolchains", b"")
