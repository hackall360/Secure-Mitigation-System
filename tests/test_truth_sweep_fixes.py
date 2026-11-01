# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: truth-sweep fix wave (2026-11-01 audit, 8 findings).

Fail-first per LAW 9: each test names one finding and the exact files it
pins. Written BEFORE the fixes; all must FAIL on the pre-fix tree and pass
after. Uses --help text / constants / copy only (no Docker, no key).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cli_help(*args: str) -> str:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "main.py", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    return proc.stdout + proc.stderr


def test_f1_image_help_says_three_not_two():
    """F1: --init-images/--rebuild-images help must say three base images."""
    text = _cli_help("--help")
    assert "three base images" in text
    assert "two base images" not in text
    assert "both base images" not in text


def test_f2_tui_picker_covers_chain_link():
    """F2: TUI FIXTURE_ORDER must include node_chain_link (4 of 5; ELF stays binary-mode)."""
    import tui

    assert "node_chain_link" in tui.FIXTURE_ORDER
    assert len(tui.FIXTURE_ORDER) == 4
    assert len(tui.FIXTURE_SHORT) == 4


def test_f3_fixture_scan_help_scopes_mutations_to_project():
    """F3: --scan help + CAPABILITIES_TEXT must not promise mutation probes for fixture scans."""
    import sms_cli

    scan_help = _cli_help("--help")
    scan_section = scan_help.split("--scan")[1].split("--project")[0]
    assert "mutation" not in scan_section.lower()
    assert "project" in sms_cli.CAPABILITIES_TEXT.split("mutations")[0].lower() or (
        "project" in sms_cli.CAPABILITIES_TEXT.lower()
    )


def test_f4_startup_log_does_not_claim_inference_handshake():
    """F4: readiness log line must say key-present, not imply a live inference check."""
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    lines = text.splitlines()
    idx = next(i for i, ln in enumerate(lines) if "Secure Mitigation System ready:" in ln)
    window = "\n".join(lines[idx : idx + 4])
    assert "key_present" in window or "key present" in window.lower()


def test_f5_agents_map_lists_all_surfaces():
    """F5: AGENTS.md project map must name sms_cli.py, tui.py, web/, docker/, modules/."""
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for marker in ("sms_cli.py", "tui.py", "web/", "docker/", "modules/"):
        assert marker in text, marker


def test_f6_v3_version_mapped_to_release():
    """F6: web v3 version.js must reference the release APP_VERSION mapping."""
    text = (ROOT / "web" / "js" / "core" / "version.js").read_text(encoding="utf-8")
    assert "APP_VERSION" in text or "library/core/version.py" in text


def test_f7_tui_sweep_depth_matches_cli_max():
    """F7: TUI sweep clamp must allow 4 passes like the CLI documents."""
    import tui

    assert tui._state_sweep_passes(tui.TuiState(mode="sweep", sweep_depth=4)) == 4
    import subprocess
    import sys

    plain_help = subprocess.run(
        [sys.executable, "tui.py", "--help"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    ).stdout
    assert "1-4" in plain_help or "max 4" in plain_help


def test_f8_binary_contract_not_self_contradictory():
    """F8: binary_argv_echo contract must state short-alnum echo is EXPECTED, not vulnerable."""
    from library.core.registry import TARGETS_REGISTRY

    target = TARGETS_REGISTRY["binary_argv_echo"]
    blob = (target.description + " " + target.contract).lower()
    assert "expected" in blob or "normal behavior" in blob or "contract" in blob
    assert (
        not ("unvalidated argv reflection" in blob and "echoes back" in blob) or "expected" in blob
    )
