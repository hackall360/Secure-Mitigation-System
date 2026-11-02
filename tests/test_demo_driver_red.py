# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (P2-5/Wave 1.2): machine driver for the 3-minute demo beat sheet.

``scripts/demo_driver.py`` does not exist yet; importing it raises
ModuleNotFoundError, which IS the expected FAIL. GREEN lands with the driver.

Contract under test:
(a) parsing ``docs/DEMO_SCRIPT.md`` yields 7 beats, cumulative end 180.0 s;
(b) ``--dry-run`` exits 0 and prints all 7 stems;
(c) ``--check-beats`` exits 0 on the current tree (doc BEATS == scenario BEATS);
(d) ``--check-beats`` against a doctored beats copy (one stem changed) exits
    non-zero.
"""

try:
    import scripts.demo_driver as driver

    HAS_DRIVER = True
except ModuleNotFoundError:
    HAS_DRIVER = False
    driver = None  # type: ignore[assignment]

REQUIRES_DRIVER = "RED: scripts/demo_driver.py not implemented"

EXPECTED_STEMS = [
    "demo-hook",
    "demo-red",
    "demo-blue",
    "demo-flip",
    "demo-replay",
    "demo-honest",
    "demo-close",
]


def test_driver_module_exists():
    assert HAS_DRIVER, REQUIRES_DRIVER


def test_parse_yields_7_beats_cumulative_180s():
    beats = driver.parse_doc_beats()
    assert len(beats) == 7, f"RED: need 7 beats, found {len(beats)}"
    assert [b["stem"] for b in beats] == EXPECTED_STEMS
    assert driver.cumulative_end(beats) == 180.0, (
        f"RED: cumulative end {driver.cumulative_end(beats)}s != 180.0 s"
    )


def test_dry_run_exits_0_prints_all_stems(capsys):
    rc = driver.main(["--dry-run"])
    assert rc == 0, "RED: --dry-run must exit 0"
    out = capsys.readouterr().out
    for stem in EXPECTED_STEMS:
        assert stem in out, f"RED: --dry-run output missing stem {stem}"


def test_check_beats_exits_0_on_current_tree(capsys):
    rc = driver.main(["--check-beats"])
    assert rc == 0, f"RED: --check-beats drifted on clean tree: {capsys.readouterr().out}"


def test_check_beats_tampered_copy_exits_nonzero(tmp_path, capsys):
    doctored = tmp_path / "DEMO_SCRIPT.md"
    doctored.write_text(
        driver.DEFAULT_DOC.read_text(encoding="utf-8").replace(
            "stem: demo-hook", "stem: demo-hoax", 1
        ),
        encoding="utf-8",
    )
    rc = driver.main(["--check-beats", "--doc", str(doctored)])
    assert rc != 0, "RED: --check-beats must exit non-zero on a doctored stem"
