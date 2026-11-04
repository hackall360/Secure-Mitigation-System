# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): project loop runs no local scanners — coverage pass flies blind.

The fixture loop (workflow.py) runs opt-in local scanners (trivy/grype/
osv-scanner/dependency-check) via _run_opt_in_scanners and grounds red
with the hits. The PROJECT loop (project_workflow.py, which serves every
ingest scan) has ZERO scanner calls: grep "scanner" hits nothing. The new
coverage pass asks red to triage dependency pins against "recognizably
vulnerable ranges" — on the project path there is no scanner output to
ground that claim, so red must either guess (wrong) or exit 2 (blind).

Parity contract: when settings.research_scanners is set, the project
loop runs _run_opt_in_scanners against the staged tree and threads the
hits into the red contract (same "Grounded intel" shape as
project_digest), or records scanner-unavailable in the report. Scanner
binaries stay optional (absent => skip with a note, never fail).
"""

from __future__ import annotations


def test_project_loop_runs_opt_in_scanners():
    src = open("library/workflows/project_workflow.py").read()
    assert "_run_project_scanners" in src, (
        "project loop must run local scanners (or record why not) when "
        "research_scanners is set — the coverage pass needs grounded hits"
    )


def test_project_scanners_never_raise_and_skip_empty():
    from types import SimpleNamespace

    from modules.workflows.project_workflow import _run_project_scanners

    assert _run_project_scanners(SimpleNamespace(research_scanners=()), {"a.py": "x"}) == []
    assert _run_project_scanners(SimpleNamespace(research_scanners=("trivy",)), {}) == []
    # Unknown/unsafe paths skipped, absent binaries degrade to [] — never raise.
    out = _run_project_scanners(
        SimpleNamespace(research_scanners=("trivy", "grype")),
        {"../evil.py": "x", "ok.py": "print(1)\n"},
    )
    assert isinstance(out, list)
