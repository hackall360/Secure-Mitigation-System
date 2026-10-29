# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first: execution-oracle verdict receipts through the real workflow evidence path."""

import hashlib
import json

from helpers import (
    FakeFixtureSandbox,
    FakeProjectMuse,
    FakeProjectSandbox,
    ResearchFakeFixtureMuse,
    project_verification,
    run_fixture_workflow,
    run_project_workflow,
    silent_emit,
)

from modules.core.config import PurpleBoxConfig
from modules.workflows.workflow import execute_purple_workflow


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
    assert receipt.verified is True
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
    sandbox = FakeProjectSandbox([project_verification(1), project_verification(0), project_verification(1)])
    result = await run_project_workflow(muse=muse, sandbox=sandbox)
    report = result.cycle_reports[0]
    assert report.status == "retained"
    receipt = report.receipt
    assert receipt is not None
    assert receipt.fixture == "demo"
    assert receipt.pre_probe_exit == 0
    assert receipt.post_probe_exit == 1
    assert receipt.differential_passed is True
    assert receipt.property_exit is None
    assert receipt.property_passed is None
    assert receipt.retained is True
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
