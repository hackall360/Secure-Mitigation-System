# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""P2 workflows gap tests (verification sweep, LAW 9 RED-first).

Scope: library/workflows/ (6 files). Targets the lowest-coverage pure
helpers found by .jcode/tools/verify_cov.py on the existing workflow
test sets (receipt building, vault-status classification, gate
predicates, chain-link probe splitting, redaction of results).

Layer 1 (L1): these tests must PASS on the real helpers (mock Muse +
Docker doubles mirrored from tests/helpers.py; no live scans).
Layer 2 (L2): the same assertions were first written against WRONG
expected values and FAILED (RED) — the RED run output is the L2 trap
proof recorded in the sweep report. The file below is the corrected
L1-green form; library/ is never mutated in place.

Mock discipline: FakeMuse/FakeSandbox doubles only at the true
transport boundary (Muse + Docker), mirroring tests/helpers.py.
"""

from tests.helpers import (
    FakeFixtureMuse,
    FakeFixtureSandbox,
    project_verification,
    silent_emit,
)

# --- 1. _sink_keywords grounds the research sidecar on local hints ---


def test_sink_keywords_detects_package_and_pairs():
    from modules.workflows.workflow import _sink_keywords

    packages, pairs = _sink_keywords("app.js", "express query sink with user input")
    assert "express" in packages
    assert pairs, "contract words must yield CIRCL browse pairs"


def test_sink_keywords_unknown_text_stays_empty_packages():
    from modules.workflows.workflow import _sink_keywords

    packages, _ = _sink_keywords("notes.py", "zzz qqq")
    assert packages == []


# --- 2. _classify_vault_statuses: anything-not-KNOWN counts novel ---


def test_classify_vault_statuses_unknown_is_novel():
    from modules.workflows.sweep import _classify_vault_statuses

    novel, known = _classify_vault_statuses(["KNOWN_ARCHETYPE", "NOVEL_SURFACE", ""])
    assert (novel, known) == (2, 1)


def test_classify_vault_statuses_all_known():
    from modules.workflows.sweep import _classify_vault_statuses

    assert _classify_vault_statuses(["KNOWN_ARCHETYPE", "KNOWN_ARCHETYPE"]) == (0, 2)


# --- 3. _chain_link_probes splits the unified chain script ---


def test_chain_link_probes_splits_at_marker():
    from modules.workflows.sweep import _chain_link_probes

    unified = "import sys\nprint('primitive')\n# --- link B ---\nprint('sink')\nsys.exit(0)\n"
    link_a, link_b = _chain_link_probes(unified)
    assert link_b.strip().lower().startswith("# --- link b ---")
    assert "primitive" in link_a
    assert "sink" not in link_a
    assert "sink" in link_b


def test_chain_link_probes_without_marker_returns_unified_twice():
    from modules.workflows.sweep import _chain_link_probes

    script = "import sys\nsys.exit(0)\n"
    link_a, link_b = _chain_link_probes(script)
    assert (link_a, link_b) == (script, script)


# --- 4. receipt chaining preserves sha linkage ---


def test_build_verdict_receipt_links_prev_chain():
    from modules.workflows.workflow import build_verdict_receipt

    first = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="patched-a",
    )
    assert first.prev_receipt_sha is None
    second = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="patched-b",
        prev_receipt=first,
    )
    assert second.prev_receipt_sha == first.patch_sha256


def test_export_cycle_receipt_json_round_trips():
    import json

    from modules.workflows.project_workflow import (
        build_cycle_receipt,
        export_cycle_receipt_json,
    )

    receipt = build_cycle_receipt(
        fixture="demo",
        pre=project_verification(0),
        patched=project_verification(1),
        baseline_regression_exit=0,
        differential_passed=True,
        candidate_diff="diff",
    )
    parsed = json.loads(export_cycle_receipt_json(receipt))
    assert parsed["pre_probe_exit"] == 0
    assert parsed["post_probe_exit"] == 1


# --- 5. normalize_snapshot_verification preserves evidence ---


def test_normalize_snapshot_verification_model_path():
    from modules.workflows.project_workflow import normalize_snapshot_verification

    out = normalize_snapshot_verification(project_verification(0, output="x" * 99), 16_000)
    assert out.probe.exit_code == 0
    assert out.regression.exit_code == 0
    assert out.probe.output == "x" * 99


def test_normalize_snapshot_verification_mapping_path():
    from modules.workflows.project_workflow import normalize_snapshot_verification

    raw = {
        "probe": {"exit_code": 1, "output": "blocked"},
        "regression": {"exit_code": 0, "output": "ok"},
    }
    out = normalize_snapshot_verification(raw, 16_000)
    assert out.probe.exit_code == 1
    assert out.regression.output == "ok"


# --- 6. files_from_snapshot drops undecodable paths ---


def test_files_from_snapshot_skips_binary():
    from types import SimpleNamespace

    from modules.workflows.cve_workflow import files_from_snapshot

    snapshot = SimpleNamespace(files={"a.py": b"x = 1\n", "blob.bin": b"\xff\xfe\x00"})
    out = files_from_snapshot(snapshot)
    assert out == {"a.py": "x = 1\n"}


# --- 7. end-to-end fixture loop with mocked doubles (no live scans) ---


async def test_fixture_loop_verified_with_doubles():
    from modules.workflows.workflow import execute_purple_workflow
    from tests.helpers import TEST_CONFIG

    result = await execute_purple_workflow(
        "node_query_sink",
        silent_emit,
        config=TEST_CONFIG,
        sandbox_factory=lambda settings: FakeFixtureSandbox([0, 0, 0, 1, 0]),
        muse_factory=lambda settings: FakeFixtureMuse(),
    )
    assert result.status == "verified"
    assert result.receipt is not None
    assert result.receipt.differential_passed is result.regression_passed


async def test_fixture_redaction_withholds_probe_source_but_keeps_receipt():
    from modules.workflows.workflow import (
        execute_purple_workflow,
        redact_fixture_result_for_user,
    )
    from tests.helpers import TEST_CONFIG

    result = await execute_purple_workflow(
        "node_query_sink",
        silent_emit,
        config=TEST_CONFIG,
        sandbox_factory=lambda settings: FakeFixtureSandbox([0, 0, 0, 1, 0]),
        muse_factory=lambda settings: FakeFixtureMuse(),
    )
    safe = redact_fixture_result_for_user(result)
    assert safe["finding"]["verification_script_python"] != (
        result.finding.verification_script_python if result.finding else "import sys"
    )
    assert safe["receipt"]["patch_sha256"] == result.receipt.patch_sha256


# --- 8. coerce_project admits intake-shaped mappings ---


def test_coerce_project_accepts_intake_aliases():
    from modules.workflows.project_workflow import coerce_project

    coerced = coerce_project(
        {
            "project_name": "demo",
            "source_files": {"src/app.py": "print(1)\n"},
            "test_command": ["pytest", "-q"],
        }
    )
    assert coerced.name == "demo"
    assert coerced.files == {"src/app.py": "print(1)\n"}
