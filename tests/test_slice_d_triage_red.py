# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (Slice D): entrypoint-first triage pins. LAWs 0, 9 govern.

Mocked model client only (local fake at the MetaMuseClient boundary);
no Docker, no secrets, no URLs. Each test FAILS until Slice D lands
(functional absence: AttributeError/TypeError in the body, not import).
"""

import json

import modules.services.project_agents as pa
from modules.core.agents import AgentError
from modules.core.config import PurpleBoxConfig

TEST_CONFIG = PurpleBoxConfig(meta_api_key="test-key")

ENTRY_JS = (
    "const http = require('http');\n"
    "const server = http.createServer((req, res) => { res.end('ok'); });\n"
    "server.listen(8080);\n"
)
HELPER_JS = "function add(a, b) { return a + b; }\nmodule.exports = { add };\n"
PACKAGE_JSON = '{"name": "demo", "main": "app.js"}\n'
README_MD = "# demo\nNothing executable here.\n"
TEST_JS = "const assert = require('assert');\nassert(true);\n"


def _docs():
    return [
        pa.SourceDocument(path="lib/helper.js", content=HELPER_JS),
        pa.SourceDocument(path="README.md", content=README_MD),
        pa.SourceDocument(path="app.js", content=ENTRY_JS),
        pa.SourceDocument(path="package.json", content=PACKAGE_JSON),
        pa.SourceDocument(path="test/app.test.js", content=TEST_JS),
    ]


class _RankFake:
    """Model double: fixed rank order (entrypoint first) or rank error."""

    def __init__(self, *, rank_order=None, rank_error=None):
        self.rank_order = rank_order
        self.rank_error = rank_error
        self.calls = []

    async def _request(self, model, system, payload, schema, role=""):
        self.calls.append(
            {"model": model, "system": system, "payload": payload, "schema": schema, "role": role}
        )
        assert "messages" not in payload and "conversation" not in payload
        if schema is pa.ManifestRankOrder:
            if self.rank_error is not None:
                raise self.rank_error
            manifest = payload["manifest"]
            order = self.rank_order or [row["path"] for row in manifest]
            return pa.ManifestRankOrder(
                ranks=[
                    pa.RankedFile(path=path, rank=index, score=1.0 / (index + 1), reason="triage")
                    for index, path in enumerate(order)
                ]
            )
        if schema is pa.RedBatchEvidence:
            path = payload["batch"]["chunks"][0]["path"]
            return pa.RedBatchEvidence(
                candidates=[
                    pa.RedCandidate(
                        vulnerability="injection",
                        affected_paths=[path],
                        evidence="untrusted input reaches a sink",
                        verification_script_python="import sys\nsys.exit(0)",
                        confidence="high",
                    )
                ],
                observations=["reviewed supplied chunk only"],
            )
        if schema is pa.RedReport:
            return pa.RedReport(
                outcome="no_finding",
                analysis_summary="No testable finding in the supplied bounded context.",
                limitations=["Not a general security claim."],
            )
        raise AssertionError(f"Unexpected response schema: {schema}")

    async def aclose(self):
        return None


async def test_ranker_orders_fixture_entrypoints_first():
    """Pin 1: one rank call over manifest-only rows; batches follow rank order."""
    muse = _RankFake(
        rank_order=["app.js", "lib/helper.js", "package.json", "test/app.test.js", "README.md"]
    )
    runner = pa.ProjectAgentRunner(muse, TEST_CONFIG)
    artifacts = await runner.analyze_red(
        _docs(), project_name="demo", cycle=1, max_batch_bytes=1024, triage_enabled=True
    )
    rank_calls = [call for call in muse.calls if call["role"] == "project_red_triage_rank_cycle_1"]
    assert len(rank_calls) == 1, "triage must cost exactly one ranker call"
    manifest = rank_calls[0]["payload"]["manifest"]
    assert {row["path"] for row in manifest} == {
        "app.js",
        "lib/helper.js",
        "package.json",
        "test/app.test.js",
        "README.md",
    }
    entry = next(row for row in manifest if row["path"] == "app.js")
    assert any("createServer" in marker for marker in entry["entrypoint_markers"])
    assert any("http" in imp for imp in entry["imports"])
    blob = json.dumps(rank_calls[0]["payload"])
    assert ENTRY_JS not in blob and HELPER_JS not in blob, (
        "ranker payload must carry no source content"
    )
    evidence_paths = [item.candidates[0].affected_paths[0] for item in artifacts.batch_evidence]
    assert evidence_paths[0] == "app.js", f"rank order not honored: {evidence_paths}"
    assert set(artifacts.coverage.covered_paths) == {
        "app.js",
        "lib/helper.js",
        "package.json",
        "test/app.test.js",
        "README.md",
    }


async def test_deferral_cap_respected():
    """Pin 2: triage_max_files defers low-rank files; coverage stays honest."""
    muse = _RankFake(
        rank_order=["app.js", "lib/helper.js", "package.json", "test/app.test.js", "README.md"]
    )
    runner = pa.ProjectAgentRunner(muse, TEST_CONFIG)
    artifacts = await runner.analyze_red(
        _docs(),
        project_name="demo",
        cycle=1,
        max_batch_bytes=1024,
        triage_enabled=True,
        triage_max_files=2,
    )
    covered = set(artifacts.coverage.covered_paths)
    assert covered == {"app.js", "lib/helper.js"}, f"cap not respected: {covered}"
    assert set(artifacts.coverage.omitted_paths) == {
        "package.json",
        "test/app.test.js",
        "README.md",
    }
    assert artifacts.coverage.complete is False
    assert any("defer" in note.lower() for note in artifacts.coverage.notes)


async def test_fallback_triggers_on_ranker_error():
    """Pin 3: ranker failure fails closed to a full scan, never to no-scan."""
    muse = _RankFake(rank_error=AgentError("ranker blew up"))
    runner = pa.ProjectAgentRunner(muse, TEST_CONFIG)
    documents = _docs()
    artifacts = await runner.analyze_red(
        documents, project_name="demo", cycle=1, max_batch_bytes=1024, triage_enabled=True
    )
    covered_bytes = artifacts.coverage.covered_bytes
    assert covered_bytes == sum(len(doc.content.encode()) for doc in documents)
    assert artifacts.coverage.complete is True
    assert artifacts.coverage.omitted_paths == []
    assert any("full scan" in note.lower() for note in artifacts.coverage.notes)


async def test_backtrack_expands_to_importers_and_neighbors():
    """Pin 4: affected_paths expand to importing + neighbor files for next pass."""
    documents = [
        pa.SourceDocument(path="src/db.py", content="def get(uid):\n    return uid\n"),
        pa.SourceDocument(path="src/app.py", content="from src.db import get\nprint(get(1))\n"),
        pa.SourceDocument(path="src/util.py", content="def noop():\n    return None\n"),
        pa.SourceDocument(path="README.md", content="# docs\n"),
    ]
    expanded = pa.expand_backtrack_paths(["src/db.py"], documents)
    assert "src/app.py" in expanded, f"importer missing: {expanded}"
    assert "src/util.py" in expanded, f"neighbor missing: {expanded}"
    assert "README.md" not in expanded
    assert "src/db.py" not in expanded


async def test_triage_opt_out_restores_exact_legacy_call_sequence():
    """Flag OFF = legacy behavior: no rank call, original sequence preserved."""
    from modules.services.project_agents import ProjectAgentRunner, SourceDocument
    from tests.helpers import FakeProjectMuse

    muse = FakeProjectMuse(red_outcomes=["no_finding"])
    runner = ProjectAgentRunner(muse, TEST_CONFIG)
    await runner.analyze_red(
        [SourceDocument(path="a.py", content="x=1")],
        project_name="demo",
        cycle=1,
        max_batch_bytes=1024,
        triage_enabled=False,
    )
    assert [call["role"] for call in muse.calls] == [
        "project_red_initial_evidence_cycle_1_batch_0",
        "project_red_initial_report_cycle_1",
    ]


async def test_workflow_backtrack_carries_findings_into_next_cycle():
    """Workflow loop: cycle-1 affected_paths thread into the cycle-2 rank order."""
    from modules.workflows.project_workflow import ProjectWorkflowInput
    from tests.helpers import (
        FakeProjectMuse,
        FakeProjectSandbox,
        project_verification,
        run_project_workflow,
    )

    class _BacktrackMuse(FakeProjectMuse):
        def __init__(self):
            super().__init__(red_outcomes=["finding", "no_finding", "no_finding"])
            self.rank_manifests = []

        async def _request(self, model, system, payload, schema, role=""):
            if schema is pa.ManifestRankOrder:
                self.rank_manifests.append([row["path"] for row in payload["manifest"]])
                order = ["src/app.py", "src/db.py", "src/util.py"]
                return pa.ManifestRankOrder(
                    ranks=[
                        pa.RankedFile(path=path, rank=index, score=1.0 / (index + 1), reason="t")
                        for index, path in enumerate(order)
                    ]
                )
            return await super()._request(model, system, payload, schema, role=role)

    project = ProjectWorkflowInput(
        name="demo",
        files={
            "src/db.py": "def get(uid):\n    return uid\n",
            "src/app.py": "from src.db import get\nprint(get(1))\n",
            "src/util.py": "def noop():\n    return None\n",
        },
        regression_command=["pytest", "-q"],
    )
    muse = _BacktrackMuse()
    sandbox = FakeProjectSandbox(
        [project_verification(1), project_verification(0), project_verification(1)]
    )
    result = await run_project_workflow(muse=muse, sandbox=sandbox, project=project, cycles=2)
    assert result.status in ("verified", "partial", "no_findings")
    assert len(muse.rank_manifests) >= 2
    assert muse.rank_manifests[0][0] == "src/db.py" or muse.rank_manifests[0][0] == "src/app.py"
    # Cycle 2 manifest leads with the backtracked importer set from cycle 1.
    assert "src/app.py" in muse.rank_manifests[1][:2]
