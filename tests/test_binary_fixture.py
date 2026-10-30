# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first binary fixture + mitigation tests (Subsystem D, Y4).

RED per LAW 9: written BEFORE the registry entry + telemetry extractor
land. Pins: (a) bundled compiled fixture exists and validates through
binary_intake; (b) registry + CLI/TUI/dashboard expose it; (c) mitigation
artifact guards (reject:-only, 8 KiB budget); (d) telemetry extractor shape.
"""

import pytest


def test_fixture_source_exists():
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "targets" / "binary_argv_echo" / "echo.c"
    assert src.exists()
    text = src.read_text()
    assert "argv" in text


def test_fixture_binary_builds_and_validates(tmp_path):
    import shutil
    import subprocess
    from pathlib import Path

    from modules.services.binary_intake import validate_binary_blob

    src = Path(__file__).resolve().parents[1] / "targets" / "binary_argv_echo" / "echo.c"
    out = tmp_path / "echo"
    if shutil.which("gcc") is None:
        pytest.skip("gcc unavailable")
    built = subprocess.run(
        ["gcc", "-O1", "-o", str(out), str(src)], capture_output=True, timeout=120
    )
    assert built.returncode == 0, built.stderr.decode()[:500]
    blob = out.read_bytes()
    spec = validate_binary_blob(
        blob,
        filename="echo",
        contract="Short alnum input echoes; overlong or metachar input is rejected.",
    )
    assert spec.binary_format == "elf"


def test_registry_has_binary_fixture():
    from modules.core.registry import TARGETS_REGISTRY

    assert "binary_argv_echo" in TARGETS_REGISTRY
    target = TARGETS_REGISTRY["binary_argv_echo"]
    assert target.filename == "echo"
    # The ELF bytes are not UTF-8 source: --scan must refuse it loudly,
    # the binary harness path (--binary-target / /ws/binary) serves it.
    with pytest.raises((ValueError, UnicodeDecodeError)):
        target.read_source()
    assert "binary harness" in target.description.lower()


def test_mitigation_artifact_guards():
    from modules.core.patches import PatchRejected
    from modules.workflows.binary_sweep import extract_mitigation_rules

    class _Patch:
        def __init__(self, content):
            self.patched_file_content = content

    with pytest.raises(PatchRejected):
        extract_mitigation_rules(_Patch("no reject lines here"))
    with pytest.raises(PatchRejected):
        extract_mitigation_rules(_Patch("reject:" + "x" * 9000))
    ok = extract_mitigation_rules(_Patch("reject:;\nreject:&\nnote ignored"))
    assert "reject:;" in ok


def test_telemetry_extractor_shape():
    from modules.services import binary_telemetry as telemetry

    assert callable(telemetry.summarize_profile)
    summary = telemetry.summarize_profile("file output\nstrings output\nreadelf output")
    assert "format" in summary or "signals" in summary


def test_binary_sweep_result_carries_compression_and_vault():
    from modules.workflows.sweep import SweepScanResult

    result = SweepScanResult(target="binary:echo")
    dumped = result.model_dump()
    assert "compression" in dumped
    assert "vault_recall" in dumped
    facts_ns = __import__("sms_cli").format_facts(result)
    assert "compression" in facts_ns and "vault_recall" in facts_ns


def test_dashboard_lists_binary_fixture():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text()
    assert "binary" in html.lower()


def test_source_workflows_refuse_binary_fixture():
    """LAW 8 routing: binary_argv_echo fails closed on the source paths."""
    import asyncio

    from modules.workflows.sweep import execute_sweep_scan
    from modules.workflows.workflow import execute_purple_workflow

    async def _collect(coro):
        events = []

        async def emit(team, message):
            events.append(team)

        return await coro(emit)

    for runner in (
        lambda emit: execute_purple_workflow("binary_argv_echo", emit),
        lambda emit: execute_sweep_scan("binary_argv_echo", emit),
    ):
        result = asyncio.run(_collect(runner))
        assert result.status == "error"
        assert "binary harness" in result.message
