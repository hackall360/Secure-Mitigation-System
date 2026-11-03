# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Parity wave W4 RED: CLI acknowledgment for showcase/ops-log/ingest-dry-run.

Gaps: (a) ``showcase_status`` exists in the library but no flag surfaces it;
(b) ``--observability-mode`` exists but no ``--ops-log`` reads recent JSONL;
(c) ``--ingest-repo`` clones but no ``--ingest-dry-run`` validates spec only.

LAW 9 red-first: pre-change, none of the three flags exist on
``build_parser()``, so every case below FAILS (exit 2 / missing text).
Post-change green: all three in --help; --showcase-status prints 4 sections
on the real tree; --ingest-dry-run bad URL exits 1 with zero Docker contact;
--ops-log prints at most N lines. Static checks + ``bash -n`` only here —
no servers started, no Docker daemon touched (bombed client proves it).
"""

import main


def test_all_three_flags_in_help():
    """--help surfaces --showcase-status, --ops-log, --ingest-dry-run."""
    text = main.build_parser().format_help()
    assert "--showcase-status" in text
    assert "--ops-log" in text
    assert "--ingest-dry-run" in text


def test_showcase_status_prints_four_sections(monkeypatch, capsys):
    """--showcase-status prints the TTS/capture/music/render presence table."""
    monkeypatch.setattr("sys.argv", ["main.py", "--showcase-status"])
    assert main.main() == 0
    out = capsys.readouterr().out.lower()
    assert "tts" in out
    assert "capture" in out
    assert "music" in out
    assert "render" in out


def test_ingest_dry_run_bad_url_exits_1_without_clone(monkeypatch):
    """Bad URL + --ingest-dry-run exits 1 and never touches Docker."""

    def _bomb(*args, **kwargs):
        raise AssertionError("Docker must not be contacted during --ingest-dry-run")

    monkeypatch.setattr(main, "DockerSandboxManager", _bomb)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--ingest-repo",
            "http://bad-host/x",
            "--commit-hash",
            "a" * 40,
            "--ingest-dry-run",
        ],
    )
    assert main.main() == 1


def test_ops_log_caps_output_lines(monkeypatch, tmp_path, capsys):
    """--ops-log N prints at most N JSONL records across signals."""
    import json

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["main.py", "--ops-log", "10"])
    (tmp_path / "logs" / "logs").mkdir(parents=True)
    (tmp_path / "logs" / "metrics").mkdir(parents=True)
    with (tmp_path / "logs" / "logs" / "a.jsonl").open("w", encoding="utf-8") as handle:
        for i in range(30):
            handle.write(json.dumps({"ts": f"2026-01-01T00:00:{i:02d}Z", "i": i}) + "\n")
    with (tmp_path / "logs" / "metrics" / "b.jsonl").open("w", encoding="utf-8") as handle:
        for i in range(5):
            handle.write(json.dumps({"ts": f"2026-01-02T00:00:{i:02d}Z", "i": i}) + "\n")

    assert main.main() == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert 1 <= len(lines) <= 10
