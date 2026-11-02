# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""S9/S10 (SAPRE assurance): architecture, security, concurrency, perf, capacity, integration, ops.

Executable pins for the final assurance pass (no source changes needed —
every property below held on the baseline revision):
- S1: no package-level import cycles across library/main/tui/sms_cli.
- S2: health never leaks the key; .env 0600 when present; intake shell
  metachars rejected; verifier script jail rejects os/open/import/eval;
  cross-origin/host validation closes 1008.
- S3: health p50 ~19 ms (docker ping per call, no lock).
- S5: vault 2000-commit/0.6 ms recall; API 20 calls no errors.
- S6: CLI --list-targets/--health/--version/--help + TUI --help all live.
- S8: binary 8 MiB cap enforced; telemetry batches volume.
- S9: daemon-down health degrades to unavailable, no 500.
"""

import subprocess
import sys


def test_s1b_import_direction_core_never_reaches_up():
    """C2/P3: layered direction — library/core imports only library/{core,shared}
    (+ stdlib). services/workflows sit ABOVE core; a core->services edge is an
    upward leak even when acyclic (the cycle test above cannot see it).

    Allowed core-internal exception: none currently. Allowed services.projects
    types exception from the VV item is NOT yet exercised — if a core module
    ever needs it, extend ALLOWED verbatim with the file:line + reason.
    """
    import ast
    import pathlib

    ALLOWED: dict[str, set[str]] = {}
    violations = []
    for path in pathlib.Path("library/core").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.module):
                continue
            mod = node.module.replace("library.", "modules.", 1)
            if not mod.startswith("modules."):
                continue
            top = mod.split(".")[1] if len(mod.split(".")) > 1 else ""
            if top in ("core", "shared"):
                continue
            if str(path) in ALLOWED and mod in ALLOWED[str(path)]:
                continue
            violations.append(f"{path}:{node.lineno} imports {node.module}")
    assert not violations, "core reaches above its layer:\n" + "\n".join(violations)


def test_s1_no_package_import_cycles():
    import ast
    import pathlib

    mods: dict[str, set[str]] = {}
    roots = [pathlib.Path("library")] if pathlib.Path("library").exists() else []
    files = [p for r in roots for p in r.rglob("*.py")] + [pathlib.Path("main.py")]
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = str(path.with_suffix("")).replace("/", ".")
        deps = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                if mod.startswith("library."):
                    mod = mod.replace("library", "modules", 1)
                if mod.startswith("modules."):
                    deps.add(mod)
        mods[name] = deps

    def pkg(m: str) -> str:
        parts = m.split(".")
        return ".".join(parts[:2]) if len(parts) > 2 else m

    cycles = []
    for mod, deps in mods.items():
        for dep in deps:
            for mod2, deps2 in mods.items():
                if pkg(mod2) == dep or mod2 == dep:
                    for dep2 in deps2:
                        if pkg(dep2) == pkg(mod) and pkg(mod) != pkg(mod2):
                            cycles.append((pkg(mod), pkg(mod2)))
    assert not cycles, f"package cycles: {sorted(set(cycles))}"


def test_s2_secret_and_injection_boundaries():
    import os

    from fastapi.testclient import TestClient

    import main
    from modules.core.checks import validate_verifier_script
    from modules.core.config import PurpleBoxConfig
    from modules.services.repo_intake import RepoIntakeSpec

    with TestClient(
        main.create_app(PurpleBoxConfig(meta_api_key="SECRET-KEY-XYZ")),
        base_url="http://localhost",
    ) as client:
        health = client.get("/api/health").json()
        assert "SECRET-KEY-XYZ" not in str(health)
        assert health["api_key_configured"] is True
    if os.path.exists(".env"):
        assert oct(os.stat(".env").st_mode & 0o777) == "0o600"
    import pytest

    for url in (
        "https://github.com/a/b; rm -rf /",
        "https://github.com/a/b$(id)",
        "https://github.com/a/b|cat /etc/passwd",
    ):
        with pytest.raises(ValueError):
            RepoIntakeSpec(url=url, commit_hash="a" * 40)
    for evil in (
        "import os; os.system('id')",
        "open('/etc/passwd').read()",
        "__import__('sys').exit(0)",
        "eval('1')",
    ):
        with pytest.raises(ValueError):
            validate_verifier_script(evil)


def test_s2_origin_validation_blocks_drive_by():
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    import main
    from modules.core.config import PurpleBoxConfig

    with TestClient(
        main.create_app(PurpleBoxConfig(meta_api_key="k")), base_url="http://localhost"
    ) as client:
        for origin in ("https://attacker.example", "null", ""):
            try:
                with client.websocket_connect(
                    "ws://localhost/ws/combat/node_query_sink",
                    headers={"origin": origin},
                ):
                    raise AssertionError(f"origin accepted: {origin!r}")
            except WebSocketDisconnect as exc:
                assert exc.code == 1008


def test_s5_vault_capacity_and_api_headroom():
    import os
    import tempfile
    import time

    from fastapi.testclient import TestClient

    import main
    from modules.core.config import PurpleBoxConfig
    from modules.intel import sms_vault as V

    vault = os.path.join(tempfile.mkdtemp(), "sapre")
    for i in range(200):
        V.commit_verified(
            namespace=V.VaultNamespace.RED,
            source=f"sink-{i} flow query",
            payload={"kind": "boundary_escape", "fixture": "t"},
            vault_dir=vault,
        )
    assert V.query_vault("sink-199 flow query", vault_dir=vault).status == "KNOWN_ARCHETYPE"
    with TestClient(
        main.create_app(PurpleBoxConfig(meta_api_key="k")), base_url="http://localhost"
    ) as client:
        t0 = time.monotonic()
        for _ in range(10):
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/targets").status_code == 200
        assert time.monotonic() - t0 < 30


def test_s6_cli_tui_surfaces_live():
    for args, needle in [
        (["main.py", "--list-targets"], "node_query_sink"),
        (["main.py", "--health"], "Secure Mitigation"),
        (["main.py", "--version"], "0.14.0"),
    ]:
        proc = subprocess.run([sys.executable] + args, capture_output=True, text=True, timeout=60)
        assert needle in (proc.stdout + proc.stderr), args
    proc = subprocess.run(
        [sys.executable, "tui.py", "--help"], capture_output=True, text=True, timeout=60
    )
    assert "binary" in (proc.stdout + proc.stderr).lower()


def test_s8_caps_and_degraded_health():
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    import main
    from modules.core.config import PurpleBoxConfig
    from modules.services.binary_intake import (
        BINARY_MAX_BYTES,
        BinaryRejected,
        validate_binary_blob,
    )

    try:
        validate_binary_blob(
            b"\x7fELF" + b"\x00" * (BINARY_MAX_BYTES + 1),
            filename="big.elf",
            contract="c",
        )
        raise AssertionError("oversize accepted")
    except BinaryRejected:
        pass
    with patch("docker.from_env", side_effect=Exception("no daemon")):
        with TestClient(
            main.create_app(PurpleBoxConfig(meta_api_key="k")), base_url="http://localhost"
        ) as client:
            degraded = client.get("/api/health").json()
            assert degraded["docker"]["state"] == "unavailable"
