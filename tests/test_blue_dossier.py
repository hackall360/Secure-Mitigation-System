# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Slice B: blue receives a finding dossier, not the full red context.

The dossier carries the winning finding (vulnerability, affected paths,
condensed evidence, probe script plus probe/regression exit codes as the
grounding signal) with ONLY the affected source files, the contract, and
the limits. The full red report dump, the full pre-verification dump, and
the multi-group fanout must not reach the model.
"""

import inspect
import json

import pytest
from helpers import TEST_CONFIG as CONFIG
from helpers import (
    FakeProjectMuse as FakeMuse,
)

from modules.core.agents import AgentError
from modules.services.project_agents import (
    ProjectAgentRunner,
    RedReport,
    SourceDocument,
    build_blue_dossier,
)


def _report(affected=("src/app.py",)):
    return RedReport(
        outcome="finding",
        vulnerability="unsanitized input reaches sink",
        affected_paths=list(affected),
        analysis_summary="Untrusted input reaches a sensitive boundary without validation.",
        verification_script_python="import sys\nsys.exit(0)",
        limitations=["Only supplied source was reviewed."],
    )


def _pre_verification(probe_output="probe-confirm-marker"):
    return {
        "probe": {"exit_code": 0, "output": probe_output},
        "regression": {"exit_code": 0, "output": "ok"},
        "fresh_target": True,
    }


def _documents():
    return [
        SourceDocument(path="src/app.py", content="value = input()\nprint(value)\n"),
        SourceDocument(path="src/util.py", content="helper = 1\n"),
        SourceDocument(path="src/other.py", content="unrelated = 1\n"),
    ]


def test_build_blue_dossier_selects_only_affected_unprotected_files():
    dossier, selected = build_blue_dossier(
        _report(affected=["src/app.py", "src/util.py"]),
        _pre_verification(),
        _documents(),
        contract="validate only",
        protected_paths=["src/util.py"],
        max_changed_files=2,
        max_changed_bytes=10_000,
    )
    assert [document.path for document in selected] == ["src/app.py"]
    blob = json.dumps(dossier, ensure_ascii=False)
    assert "unrelated" not in blob
    assert "helper = 1" not in blob
    assert dossier["finding"]["vulnerability"] == "unsanitized input reaches sink"
    assert dossier["finding"]["verification_script_python"] == "import sys\nsys.exit(0)"
    assert dossier["finding"]["probe_exit_code"] == 0
    assert dossier["finding"]["regression_exit_code"] == 0
    assert dossier["project_contract"] == "validate only"
    assert dossier["limits"] == {"max_changed_files": 2, "max_changed_bytes": 10_000}


def test_blue_dossier_payload_is_smaller_than_full_context():
    big_source = "x = input()\n" * 2000
    documents = [
        SourceDocument(path="src/app.py", content=big_source),
        SourceDocument(path="src/other.py", content="y = 1\n" * 2000),
    ]
    report = _report()
    report = report.model_copy(update={"analysis_summary": "summary-context " * 1000})
    pre = _pre_verification(probe_output="o" * 16_000)
    pre["properties"] = {"exit_code": 0, "output": "p" * 8000}
    pre["mutations"] = {"exit_code": 0, "output": "m" * 8000}
    pre["repeat_regression"] = {"exit_code": 0, "output": "r" * 8000}

    dossier, _selected = build_blue_dossier(
        report,
        pre,
        documents,
        contract="validate only",
        max_changed_files=2,
        max_changed_bytes=10_000,
    )
    full_context = {
        "red_report": report.model_dump(),
        "pre_verification": pre,
        "safe_snapshot_files": [
            document.model_dump() | {"sha256": document.sha256} for document in documents
        ],
    }
    dossier_size = len(json.dumps(dossier, ensure_ascii=False).encode("utf-8"))
    full_size = len(json.dumps(full_context, ensure_ascii=False).encode("utf-8"))
    assert dossier_size < full_size


async def test_propose_blue_sends_dossier_with_only_affected_files():
    muse = FakeMuse()
    runner = ProjectAgentRunner(muse, CONFIG)
    proposal = await runner.propose_blue(
        _documents(),
        project_name="demo",
        cycle=1,
        red_report=_report(affected=["src/app.py"]),
        pre_verification=_pre_verification(),
        contract="validate only",
        max_changed_files=2,
        max_changed_bytes=10_000,
    )
    assert proposal.replacements
    blue_calls = [call for call in muse.calls if call["schema"].__name__ == "BlueProposal"]
    assert len(blue_calls) == 1
    payload = blue_calls[0]["payload"]
    assert "red_report" not in payload
    assert "pre_verification" not in payload
    assert payload["finding_dossier"]["finding"]["vulnerability"] == (
        "unsanitized input reaches sink"
    )
    assert [item["path"] for item in payload["safe_snapshot_files"]] == ["src/app.py"]
    assert blue_calls[0]["role"] == "project_blue_proposal_cycle_1_batch_0"


def test_blue_payload_budget_is_separate_and_smaller_than_red_default():
    from modules.workflows.project_workflow import ProjectWorkflowLimits

    parameters = inspect.signature(ProjectAgentRunner.propose_blue).parameters
    assert parameters["max_blue_payload_bytes"].default == 64_000
    assert parameters["max_blue_payload_bytes"].default < 256_000
    limits = ProjectWorkflowLimits()
    assert limits.max_blue_payload_bytes == 64_000
    assert limits.max_blue_payload_bytes < limits.max_payload_bytes


async def test_blue_dossier_over_budget_fails_closed_without_truncation():
    muse = FakeMuse()
    runner = ProjectAgentRunner(muse, CONFIG)
    big = SourceDocument(path="src/app.py", content="x = input()\n" * 20_000)
    with pytest.raises(AgentError, match="no content was silently truncated"):
        await runner.propose_blue(
            [big],
            project_name="demo",
            cycle=1,
            red_report=_report(),
            pre_verification=_pre_verification(),
            contract="validate only",
            max_changed_files=2,
            max_changed_bytes=10_000,
            max_blue_payload_bytes=16_384,
        )
    assert muse.calls == []
