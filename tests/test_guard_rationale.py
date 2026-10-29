# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first: sanitization-guard rationale export (SPEC 14.8 item 2, Lane 2).

Competitor Semgrep/Snyk Code does [AI draft fixes validated by humans or
rescan], but we are doing [structured guard-firing rationales bound to each
rejected patch], which advances the field by [making safe-patch review
auditable in minutes on day zero].
"""

import hashlib

import pytest

from modules.core.patches import (
    EDIT_BUDGET_LINES,
    PatchRejected,
    guard_rationale,
    is_solver_synthesized_shape,
    validate_patch,
)
from modules.core.registry import TARGETS_REGISTRY
from modules.services.project_agents import BlueProposal, FileReplacement
from modules.shared.sms_redact import EXPLOIT_REDACTED, redact_cycle_evidence
from modules.workflows.project_workflow import (
    GuardRationale,
    ReplacementValidation,
    validate_replacements,
)


def _proposal(path, original, replacement):
    return BlueProposal(
        strategy="sanitize",
        replacements=[
            FileReplacement(
                path=path,
                original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                replacement_content=replacement,
                rationale="add allowlist",
                change_kind="input_validation",
            )
        ],
    )


def test_protected_path_rejection_exports_guard_rationale():
    content = "assert True\n"
    proposal = _proposal("tests/test_app.py", content, "assert True  # bypassed\n")
    validation, _ = validate_replacements(
        proposal,
        {"tests/test_app.py": content},
        max_changed_files=2,
        max_changed_bytes=10_000,
        protected_paths=["tests/test_app.py"],
    )
    assert not validation.accepted
    assert isinstance(validation.guard_rationale, GuardRationale)
    assert validation.guard_rationale.guard_id == "protected_path"
    assert "tests/test_app.py" in validation.guard_rationale.trigger


def test_hash_mismatch_rejection_exports_guard_rationale():
    original = "x = input()\n"
    proposal = BlueProposal(
        strategy="sanitize",
        replacements=[
            FileReplacement(
                path="app.py",
                original_sha256="0" * 64,
                replacement_content="x = 'safe'\n",
                rationale="sanitize",
                change_kind="input_validation",
            )
        ],
    )
    validation, _ = validate_replacements(
        proposal,
        {"app.py": original},
        max_changed_files=2,
        max_changed_bytes=10_000,
    )
    assert not validation.accepted
    assert validation.guard_rationale is not None
    assert validation.guard_rationale.guard_id == "hash_mismatch"
    assert "app.py" in validation.guard_rationale.trigger


def test_forbidden_sink_rejection_names_sink():
    original = "value = sanitize(raw)\n"
    proposal = _proposal("app.py", original, "value = eval(raw)\n")
    validation, _ = validate_replacements(
        proposal,
        {"app.py": original},
        max_changed_files=2,
        max_changed_bytes=10_000,
    )
    assert not validation.accepted
    assert validation.guard_rationale is not None
    assert validation.guard_rationale.guard_id == "forbidden_sink_introduced"
    assert "eval(" in validation.guard_rationale.trigger


def test_edit_budget_rejection_exports_guard_rationale():
    original = "".join(f"line{i} = {i}\n" for i in range(100))
    replacement = "".join(f"changed{i} = {i!r}\n" for i in range(100))
    proposal = _proposal("app.py", original, replacement)
    validation, _ = validate_replacements(
        proposal,
        {"app.py": original},
        max_changed_files=2,
        max_changed_bytes=10_000,
    )
    assert not validation.accepted
    assert validation.guard_rationale is not None
    assert validation.guard_rationale.guard_id == "edit_budget_exceeded"


def test_accepted_validation_has_no_guard_rationale():
    original = "x = input()\nprint(x)\n"
    proposal = _proposal("app.py", original, "x = 'safe'\nprint(x)\n")
    validation, changed = validate_replacements(
        proposal,
        {"app.py": original},
        max_changed_files=2,
        max_changed_bytes=10_000,
    )
    assert validation.accepted and changed
    assert validation.guard_rationale is None


def test_fixture_protected_line_rejection_exports_guard_rationale():
    target = TARGETS_REGISTRY["node_query_sink"]
    source = target.read_source()
    with pytest.raises(PatchRejected) as excinfo:
        validate_patch(target, source, source.replace("'/lookup'", "'/removed'"))
    assert excinfo.value.guard_id == "protected_line_removed"
    assert excinfo.value.trigger != ""


def test_fixture_license_rejection_exports_guard_rationale():
    target = TARGETS_REGISTRY["node_query_sink"]
    source = target.read_source()
    with pytest.raises(PatchRejected) as excinfo:
        validate_patch(
            target,
            source,
            source.replace("Copyright (c) 2026 hackall360", "Copyright Someone Else"),
        )
    assert excinfo.value.guard_id == "license_notice_removed"


def test_guard_rationale_helper_returns_structured_dict():
    target = TARGETS_REGISTRY["node_query_sink"]
    source = target.read_source()
    with pytest.raises(PatchRejected) as excinfo:
        validate_patch(target, source, source)
    rationale = guard_rationale(excinfo.value)
    assert rationale["guard_id"] == "empty_or_unchanged"
    assert rationale["reason"] != ""
    assert "verification_script_python" not in rationale


def test_rationale_survives_evidence_dump_and_redaction():
    content = "assert True\n"
    proposal = _proposal("tests/test_app.py", content, "assert True  # bypassed\n")
    validation, _ = validate_replacements(
        proposal,
        {"tests/test_app.py": content},
        max_changed_files=2,
        max_changed_bytes=10_000,
        protected_paths=["tests/test_app.py"],
    )
    dumped = validation.model_dump()
    assert dumped["guard_rationale"]["guard_id"] == "protected_path"
    round_tripped = ReplacementValidation.model_validate(dumped)
    assert round_tripped.guard_rationale is not None
    assert round_tripped.guard_rationale.guard_id == "protected_path"
    redacted = redact_cycle_evidence(
        {
            "replacement_validation": dumped,
            "red": {"report": {"verification_script_python": "evil-bytes"}},
        }
    )
    assert redacted["replacement_validation"]["guard_rationale"]["guard_id"] == "protected_path"
    # LAW 4 unchanged: probe bytes never leak into user-facing evidence.
    assert redacted["red"]["report"]["verification_script_python"] == EXPLOIT_REDACTED


# ---- SPEC 14.9 item 3 (Lane 4): Guard-discipline template inputs ----
# Competitor SemFix/DirectFix does [constraint-solved synthesis], but we are
# doing [template-shaped inputs accepted only inside the existing 60-line
# sanitization guards with GuardRationale export], which advances the field by
# [widening safe-patch shapes without widening the trust boundary].


_TEMPLATE_GUARD = (
    "        if (!/^[0-9]+$/.test(rawUserId)) {\n"
    "            res.writeHead(400, { 'Content-Type': 'application/json' });\n"
    "            res.end(JSON.stringify({ status: 'error', detail: 'Invalid ID' }));\n"
    "            return;\n"
    "        }\n"
)


def _node_template_patch(source: str) -> str:
    return source.replace(
        "        const queryExpression =",
        _TEMPLATE_GUARD + "        const queryExpression =",
    )


def test_template_shaped_allowlist_accepted_inside_budget():
    target = TARGETS_REGISTRY["node_query_sink"]
    source = target.read_source()
    patched = _node_template_patch(source)
    assert not is_solver_synthesized_shape(patched)
    diff = validate_patch(target, source, patched)
    assert diff.startswith("--- a/node_query_sink/app.js")
    assert EDIT_BUDGET_LINES == 60


def test_template_shaped_over_budget_rejected_budget_never_widened():
    target = TARGETS_REGISTRY["node_query_sink"]
    source = target.read_source()
    anchor = "        const queryExpression ="
    blocks = "".join(f"        // template allowlist {i}\n{_TEMPLATE_GUARD}" for i in range(15))
    patched = source.replace(anchor, blocks + anchor)
    assert not is_solver_synthesized_shape(patched)
    with pytest.raises(PatchRejected) as excinfo:
        validate_patch(target, source, patched)
    assert excinfo.value.guard_id == "edit_budget_exceeded"
    assert EDIT_BUDGET_LINES == 60
    rationale = guard_rationale(excinfo.value)
    assert rationale["guard_id"] == "edit_budget_exceeded"
    assert "verification_script_python" not in rationale


def test_solver_synthesized_shape_rejected_with_guard_rationale():
    target = TARGETS_REGISTRY["node_query_sink"]
    source = target.read_source()
    probe_sentinel = "PROBE-BYTES-SENTINEL-9f3c"
    patched = source.replace(
        "        const queryExpression =",
        "        // solver model: (check-sat) (declare-const x Int)\n"
        "        const queryExpression =",
    )
    assert is_solver_synthesized_shape(patched)
    assert probe_sentinel not in patched
    with pytest.raises(PatchRejected) as excinfo:
        validate_patch(target, source, patched)
    assert excinfo.value.guard_id == "solver_synthesized_shape"
    rationale = guard_rationale(excinfo.value)
    assert rationale["guard_id"] == "solver_synthesized_shape"
    assert rationale["trigger"] != ""
    assert probe_sentinel not in rationale["trigger"]
    assert "verification_script_python" not in rationale


def test_solver_markers_never_accepted_even_when_small():
    assert is_solver_synthesized_shape("(check-sat)\n")
    assert is_solver_synthesized_shape("from z3 import Solver\n")
    target = TARGETS_REGISTRY["node_query_sink"]
    source = target.read_source()
    assert not is_solver_synthesized_shape(source)
    assert not is_solver_synthesized_shape(_node_template_patch(source))


def test_guard_rationale_rejects_empty_reason():
    """Item 5 RED: GuardRationale must require a non-empty reason."""
    import pytest as _pytest
    from pydantic import ValidationError as _ValidationError

    with _pytest.raises(_ValidationError):
        GuardRationale(guard_id="unsafe_path", reason="")


def test_guard_rationale_default_reason_names_guard():
    """Item 5 RED: default reason must name the guard, never be empty."""
    rationale = GuardRationale(guard_id="unsafe_path")
    assert rationale.reason != ""
    assert "unsafe_path" in rationale.reason


def test_rejected_cycle_links_guard_rationale_to_cycle():
    """Item 5 RED: GuardRationale must carry the rejected cycle/pass link."""
    rationale = GuardRationale(
        guard_id="unsafe_path",
        cycle=1,
        pass_number=1,
    )
    assert rationale.cycle == 1
    assert rationale.pass_number == 1


async def test_rejected_cycle_report_carries_linked_rationale():
    """Item 5 RED: rolled-back cycle evidence rationale names its cycle/pass."""
    from helpers import (
        FakeProjectMuse,
        FakeProjectSandbox,
        project_verification,
        run_project_workflow,
    )

    muse = FakeProjectMuse(red_outcomes=["finding"], invalid_path="../escape.py")
    sandbox = FakeProjectSandbox([project_verification(1), project_verification(0)])
    result = await run_project_workflow(muse=muse, sandbox=sandbox)
    report = result.cycle_reports[0]
    assert report.status == "rolled_back"
    rationale = report.evidence.replacement_validation.guard_rationale
    assert rationale is not None
    assert rationale.reason != ""
    assert rationale.cycle == report.cycle == 1
    assert rationale.pass_number == report.pass_number == 1
