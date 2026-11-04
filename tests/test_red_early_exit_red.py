# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first pins: opt-in red evidence early exit (backpressure on big repos).

With red_early_exit_high=N (>0), once N high-confidence candidates are in,
evidence units that have NOT started yet are skipped (no model call). Default
0 keeps the old behavior: every unit runs. Skips are counted on the artifacts
so the report can say coverage was cut short, never silently.

Mock model client only: no Docker, no network, no secrets.
"""

import dataclasses

import pytest

from modules.core.config import PurpleBoxConfig
from modules.services.project_agents import (
    ProjectAgentRunner,
    RedBatchEvidence,
    RedCandidate,
    RedReport,
    SourceDocument,
)

DOCS = [SourceDocument(path=f"f{i}.py", content=str(i) * 900) for i in range(6)]


class _Muse:
    def __init__(self):
        self.evidence_calls = 0

    async def _request(self, model, system, payload, schema, role=""):
        if schema is RedBatchEvidence:
            self.evidence_calls += 1
            return RedBatchEvidence(
                candidates=[
                    RedCandidate(
                        vulnerability="sqli",
                        affected_paths=["f0.py"],
                        evidence="string-built query",
                        verification_script_python="import sys\nsys.exit(0)\n",
                        confidence="high",
                    )
                ]
            )
        if schema is RedReport:
            return RedReport(outcome="no_finding", analysis_summary="x")
        return schema.model_validate({"candidates": []})


async def _run(early_exit):
    config = dataclasses.replace(
        PurpleBoxConfig(meta_api_key="unit-test-key"), red_early_exit_high=early_exit
    )
    muse = _Muse()
    artifacts = await ProjectAgentRunner(muse, config).analyze_red(
        DOCS,
        project_name="demo",
        cycle=1,
        max_batch_bytes=1024,
        max_parallel_batches=1,
        triage_enabled=False,
    )
    return muse, artifacts


@pytest.mark.asyncio
async def test_default_runs_every_unit():
    muse, artifacts = await _run(0)
    assert muse.evidence_calls == 6
    assert artifacts.skipped_units == 0


@pytest.mark.asyncio
async def test_early_exit_skips_unstarted_units():
    muse, artifacts = await _run(1)
    assert muse.evidence_calls == 1
    assert artifacts.skipped_units == 5
    assert any("early exit" in note for note in artifacts.coverage.notes)


def test_config_rejects_out_of_range():
    from modules.core.config import ConfigurationError

    with pytest.raises(ConfigurationError):
        dataclasses.replace(PurpleBoxConfig(meta_api_key="k"), red_early_exit_high=-1).validate()
