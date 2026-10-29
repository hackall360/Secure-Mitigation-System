# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first binary-intake tests (Milestone 4).

Compiled binaries enter through validated intake (magic bytes, size caps,
no host execution) and route through the same 3-pass sweep as source.
RED until modules/services/binary_intake.py + Dockerfile.binary land.
"""

import pytest

ELF_MAGIC = b"\x7fELF" + b"\x00" * 60
PE_MAGIC = b"MZ" + b"\x00" * 62
MACHO_MAGIC = b"\xcf\xfa\xed\xfe" + b"\x00" * 60


def test_binary_intake_accepts_elf():
    from modules.services.binary_intake import validate_binary_blob

    spec = validate_binary_blob(ELF_MAGIC, filename="target.elf", contract="Only stdin matters.")
    assert spec.binary_format == "elf"
    assert spec.size_bytes == len(ELF_MAGIC)


def test_binary_intake_accepts_pe_and_macho():
    from modules.services.binary_intake import validate_binary_blob

    assert validate_binary_blob(PE_MAGIC, filename="t.exe", contract="c").binary_format == "pe"
    assert (
        validate_binary_blob(MACHO_MAGIC, filename="t.macho", contract="c").binary_format == "macho"
    )


def test_binary_intake_rejects_bad_magic():
    from modules.services.binary_intake import BinaryRejected, validate_binary_blob

    with pytest.raises(BinaryRejected):
        validate_binary_blob(b"#!/bin/sh\n", filename="run.sh", contract="c")


def test_binary_intake_rejects_oversize():
    from modules.services.binary_intake import (
        BINARY_MAX_BYTES,
        BinaryRejected,
        validate_binary_blob,
    )

    with pytest.raises(BinaryRejected):
        validate_binary_blob(
            b"\x7fELF" + b"\x00" * BINARY_MAX_BYTES, filename="big.elf", contract="c"
        )


def test_binary_intake_rejects_path_escape():
    from modules.services.binary_intake import BinaryRejected, validate_binary_blob

    with pytest.raises(BinaryRejected):
        validate_binary_blob(ELF_MAGIC, filename="../evil.elf", contract="c")


def test_binary_intake_rejects_empty_contract():
    from modules.services.binary_intake import BinaryRejected, validate_binary_blob

    with pytest.raises(BinaryRejected):
        validate_binary_blob(ELF_MAGIC, filename="t.elf", contract="")


def test_binary_dockerfile_pinned_base():
    from pathlib import Path

    from modules.core.docker_manager import PINNED_PYTHON_BASE

    content = (Path(__file__).resolve().parents[1] / "docker" / "Dockerfile.binary").read_text(
        encoding="utf-8"
    )
    assert PINNED_PYTHON_BASE in content
    assert "USER 10001:10001" in content
    for tool in ("file", "strings", "binutils", "readelf", "xxd"):
        assert tool in content


def test_binary_sweep_routes_three_passes():
    """Binary sweep runs standard/deep/threat_actor with receipts or clear."""
    import asyncio

    from modules.core.config import PurpleBoxConfig
    from tests.helpers import silent_emit
    from tests.test_sweep_passes import SweepFakeMuse

    async def go():
        from modules.services.binary_intake import validate_binary_blob
        from modules.workflows.binary_sweep import execute_binary_sweep

        spec = validate_binary_blob(ELF_MAGIC, filename="t.elf", contract="Only stdin matters.")

        class FakeBinarySandbox:
            def __init__(self):
                self.closed = False
                self.calls = 0

            def require_base_images(self):
                return None

            def require_binary_image(self):
                return None

            def create_isolated_network(self):
                return "net"

            def binary_static_profile(self, network, blob):
                return "ELF 64-bit (fake profile)"

            def start_binary_harness(self, network, blob, mitigation=""):
                return "container", "snapshot"

            def replace_binary_harness(self, previous, snapshot, network, mitigation=""):
                return "container2", "snapshot2"

            def run_isolated_verifier(self, network, script):
                from modules.core.docker_manager import VerificationResult

                self.calls += 1
                # First call is the harness baseline (must pass); pass probes
                # report blocked so every pass clears without blue calls.
                if self.calls == 1:
                    return VerificationResult(0, "harness baseline passed")
                return VerificationResult(1, "blocked")

            def close(self):
                self.closed = True

        sandbox = FakeBinarySandbox()
        muse = SweepFakeMuse()
        result = await execute_binary_sweep(
            spec,
            silent_emit,
            config=PurpleBoxConfig(meta_api_key="t"),
            sandbox_factory=lambda s: sandbox,
            muse_factory=lambda s: muse,
        )
        assert sandbox.closed and muse.closed
        return result, muse

    result, muse = asyncio.new_event_loop().run_until_complete(go())
    assert [p.pass_id for p in result.pass_results] == ["standard", "deep", "threat_actor"]
    assert result.status == "verified"
    assert all(p.cleared for p in result.pass_results)
    assert muse.red_calls == ["standard", "deep", "threat_actor"]
    assert muse.blue_calls == 0


def test_binary_cli_flag_reaches_runner(monkeypatch, tmp_path):
    """M4 CLI parity: --binary-target PATH reaches binary_sweep_runner."""
    import main as _main

    seen = {}

    async def fake_runner(path, **kwargs):
        seen["path"] = path
        seen.update(kwargs)
        return 0

    target = tmp_path / "t.elf"
    target.write_bytes(b"\x7fELF" + b"\x00" * 64)
    monkeypatch.setattr(_main, "binary_sweep_runner", fake_runner)
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--binary-target", str(target), "--contract", "Hold the line."],
    )
    assert _main.main() == 0
    assert seen["path"] == target
    assert seen["contract"] == "Hold the line."


def test_binary_cli_rejects_non_binary(monkeypatch, tmp_path, capsys):
    """M4 CLI parity: script file refused at intake, exit 1, no scan."""
    import main as _main

    target = tmp_path / "run.sh"
    target.write_bytes(b"#!/bin/sh\necho hi\n")
    monkeypatch.setattr("sys.argv", ["main.py", "--binary-target", str(target)])
    assert _main.main() == 1
    assert "binary" in capsys.readouterr().err.lower()


def test_binary_ws_route_accepts_first_frame(monkeypatch):
    """M4 WS parity: /ws/binary validates the frame and runs the sweep."""
    import base64

    from fastapi.testclient import TestClient

    import main as _main
    from modules.core.config import PurpleBoxConfig

    seen = {}

    async def fake_sweep(spec, emit, **kwargs):
        seen["filename"] = spec.filename
        from modules.workflows.sweep import SweepScanResult

        return SweepScanResult(target="binary:t.elf", status="verified", message="ok")

    monkeypatch.setattr("modules.workflows.binary_sweep.execute_binary_sweep", fake_sweep)
    with TestClient(
        _main.create_app(PurpleBoxConfig(meta_api_key="k")), base_url="http://localhost"
    ) as client:
        with client.websocket_connect(
            "ws://localhost/ws/binary", headers={"origin": "http://localhost"}
        ) as socket:
            socket.send_json(
                {
                    "blob_b64": base64.b64encode(b"\x7fELF" + b"\x00" * 64).decode(),
                    "filename": "t.elf",
                    "contract": "Hold the line.",
                }
            )
            while True:
                event = socket.receive_json()
                if event["type"] == "result":
                    assert event["status"] == "verified"
                    break
    assert seen.get("filename") == "t.elf"


def test_binary_dashboard_controls_exist():
    """M4 dashboard parity: binary mode button + upload form controls render."""
    from html.parser import HTMLParser
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[1]

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = set()

        def handle_starttag(self, tag, attrs):
            found = dict(attrs).get("id")
            if found:
                self.ids.add(found)

    parser = Elements()
    parser.feed((root / "static/index.html").read_text())
    for control in (
        "mode-binary",
        "binary-form",
        "binary-file",
        "binary-filename",
        "binary-contract",
        "binary-errors",
    ):
        assert control in parser.ids, control
