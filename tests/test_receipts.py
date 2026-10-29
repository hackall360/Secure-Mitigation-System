# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first: execution-oracle verdict receipts through the real workflow evidence path."""

import hashlib
import json

from helpers import (
    FakeProjectMuse,
    FakeProjectSandbox,
    project_verification,
    run_fixture_workflow,
    run_project_workflow,
)


async def test_fixture_verified_cycle_records_machine_readable_receipt():
    result, _, _ = await run_fixture_workflow([0, 0, 0, 1, 0])
    assert result.status == "verified"
    receipt = result.receipt
    assert receipt is not None
    assert receipt.fixture == "node_query_sink"
    assert receipt.pre_exit_code == 0
    assert receipt.post_exit_code == 1
    assert receipt.regression_passed is True
    assert receipt.differential_passed is True
    assert receipt.property_exit_code is None
    assert receipt.property_passed is None
    # Dead-wire cut (14.9 item 4): receipt carries no verified flag; the
    # ScanResult.status the caller already set is the verdict.
    assert "verified" not in receipt.model_fields_set
    assert "verified" not in json.loads(receipt.model_dump_json())
    expected_sha = hashlib.sha256(result.patch.patched_file_content.encode("utf-8")).hexdigest()
    assert receipt.patch_sha256 == expected_sha
    dumped = json.loads(receipt.model_dump_json())
    assert dumped["fixture"] == "node_query_sink"
    assert dumped["pre_exit_code"] == 0 and dumped["post_exit_code"] == 1


async def test_fixture_non_verified_cycle_records_no_receipt():
    result, _, _ = await run_fixture_workflow([0, 1])
    assert result.status == "not_confirmed"
    assert result.receipt is None


async def test_fixture_failed_cycle_records_no_receipt_and_verdict_unchanged():
    result, _, _ = await run_fixture_workflow([0, 0, 0, 0, 0])
    assert result.status == "failed"
    assert result.receipt is None
    assert result.success is False


async def test_fixture_receipt_exports_alongside_patch():
    result, _, _ = await run_fixture_workflow([0, 0, 0, 1, 0])
    exported = result.model_dump()
    assert exported["receipt"]["patch_sha256"] == result.receipt.patch_sha256
    assert exported["receipt"]["fixture"] == result.target
    assert isinstance(exported["diff"], str) and exported["diff"] != ""


async def test_project_retained_cycle_records_machine_readable_receipt():
    muse = FakeProjectMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeProjectSandbox(
        [project_verification(1), project_verification(0), project_verification(1)]
    )
    result = await run_project_workflow(muse=muse, sandbox=sandbox)
    report = result.cycle_reports[0]
    assert report.status == "retained"
    receipt = report.receipt
    assert receipt is not None
    assert receipt.fixture == "demo"
    assert receipt.pre_probe_exit == 0
    assert receipt.post_probe_exit == 1
    assert receipt.differential_passed is True
    assert receipt.property_passed is None
    # Dead-wire cut (14.9 item 4): receipt carries no property_exit/retained
    # fields; the property verdict lives in the evidence, the retain verdict
    # in the report status.
    assert "property_exit" not in receipt.model_fields_set
    assert "retained" not in receipt.model_fields_set
    assert receipt.patch_sha256 == hashlib.sha256(report.diff.encode("utf-8")).hexdigest()
    dumped = json.loads(receipt.model_dump_json())
    assert dumped["pre_probe_exit"] == 0 and dumped["post_probe_exit"] == 1


async def test_project_rolled_back_cycle_records_no_receipt():
    muse = FakeProjectMuse(red_outcomes=["finding", "finding"])
    sandbox = FakeProjectSandbox(
        [
            project_verification(1),
            project_verification(0),
            project_verification(1, regression=3),
        ]
    )
    result = await run_project_workflow(muse=muse, sandbox=sandbox)
    report = result.cycle_reports[0]
    assert report.status == "rolled_back"
    assert report.receipt is None


async def test_project_receipt_carries_cycle_and_pass_ids():
    """Item 4 RED: CycleReceipt must carry cycle/pass ids of its report."""
    muse = FakeProjectMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeProjectSandbox(
        [project_verification(1), project_verification(0), project_verification(1)]
    )
    result = await run_project_workflow(muse=muse, sandbox=sandbox)
    report = result.cycle_reports[0]
    receipt = report.receipt
    assert receipt is not None
    assert receipt.cycle == report.cycle == 1
    assert receipt.pass_number == report.pass_number == 1


async def test_project_all_cycles_exported_not_first_only():
    """Item 4 RED: exporter must export ALL cycle receipts, not first only."""
    import main as sms_main

    muse = FakeProjectMuse(red_outcomes=["finding", "finding", "finding"])
    sandbox = FakeProjectSandbox(
        [
            # baseline + cycle 1: pre vuln, patched blocked, independent re-finds same
            project_verification(1),
            project_verification(0),
            project_verification(1),
            project_verification(1),
            # cycle 2: pre vuln, patched blocked, independent re-finds same
            project_verification(0),
            project_verification(1),
            project_verification(1),
        ]
    )
    result = await run_project_workflow(muse=muse, sandbox=sandbox, cycles=2)
    assert len(result.cycle_reports) == 2
    assert [r.status for r in result.cycle_reports] == ["retained", "retained"]
    report = result.model_dump()
    receipts = sms_main.extract_cycle_receipts(report)
    # report carries both cycle_reports and cycles alias; dedupe identical dicts.
    unique = {tuple(sorted(r.items())) for r in receipts}
    receipts = [dict(u) for u in unique]
    assert len(receipts) == 2
    assert {r["cycle"] for r in receipts} == {1, 2}
