# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED test: --ingest-repo / --commit-hash CLI surface (W1-cli-tui).

Per the W1-cli-tui survey these flags are absent from ``main.py`` today: the
parser is built inline in ``main.main()`` and there is no parser-building
function yet. Every test below goes through the real ``main.build_parser``
(no mocks of the unit under test, LAW 9C), so pre-implementation each test
FAILs with ``AttributeError: module 'main' has no attribute 'build_parser'``.
Post-implementation the GREEN side must provide ``main.build_parser()``
returning the real ``argparse`` parser with:

- ``--ingest-repo <url>`` requiring ``--commit-hash`` (exit 2 when missing),
- ``--commit-hash`` requiring ``--ingest-repo`` (exit 2 when alone),
- ``--ingest-repo`` mutually exclusive with ``--scan`` (exit 2 combined),
- a valid pair parsing to a URL string plus a 40-hex commit hash.

LAW 4: no payloads, keys, or probe material in this file.
"""

import re

import pytest

import main


def _parser():
    """Return the real CLI parser. AttributeError is the RED failure."""
    return main.build_parser()


GOOD_URL = "https://github.com/example/demo"
GOOD_HASH = "a" * 40


def test_ingest_repo_requires_commit_hash():
    parser = _parser()
    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--ingest-repo", GOOD_URL])
    assert error.value.code == 2


def test_commit_hash_requires_ingest_repo():
    parser = _parser()
    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--commit-hash", GOOD_HASH])
    assert error.value.code == 2


def test_ingest_repo_mutually_exclusive_with_scan():
    parser = _parser()
    with pytest.raises(SystemExit) as error:
        parser.parse_args(
            [
                "--scan",
                "node_query_sink",
                "--ingest-repo",
                GOOD_URL,
                "--commit-hash",
                GOOD_HASH,
            ]
        )
    assert error.value.code == 2


def test_valid_pair_parses_to_url_and_40hex_hash():
    parser = _parser()
    args = parser.parse_args(["--ingest-repo", GOOD_URL, "--commit-hash", GOOD_HASH])
    assert args.ingest_repo == GOOD_URL
    assert re.fullmatch(r"[0-9a-fA-F]{40}", args.commit_hash)
