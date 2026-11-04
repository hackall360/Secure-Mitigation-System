# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first pins: one bounded repair when red's probe is not valid Python.

Gate-2 failure (2026-11-04, insecure-web): Spark returned a finding whose
verification_script_python had "unexpected indent (line 37)". The sandbox
verifier rejected it and the whole run errored after 1:51 and $0.0027, before
blue ran. analyze_red now re-asks the report step ONCE with the parse error.
A second bad probe still fails closed (the sandbox guard is unchanged).

Mock model client only: no Docker, no network, no secrets.
"""

import pytest

from modules.core.config import PurpleBoxConfig
from modules.services.project_agents import (
    ProjectAgentRunner,
    RedBatchEvidence,
    RedReport,
    SourceDocument,
)

CONFIG = PurpleBoxConfig(meta_api_key="unit-test-key")
DOCS = [SourceDocument(path="app/app.py", content="x = 1\n" * 20)]
BAD = "import sys\n  sys.exit(0)\n"
GOOD = "import sys\nsys.exit(0)\n"


class _Muse:
    def __init__(self, probes):
        self.probes = list(probes)
        self.report_payloads = []

    async def _request(self, model, system, payload, schema, role=""):
        if schema is RedBatchEvidence:
            return RedBatchEvidence(candidates=[], observations=["ok"])
        if schema is RedReport:
            self.report_payloads.append(payload)
            return RedReport(
                outcome="finding",
                vulnerability="SQL injection in login",
                affected_paths=["app/app.py"],
                analysis_summary="String-built query.",
                verification_script_python=self.probes.pop(0),
            )
        raise AssertionError(schema)


async def _run(muse):
    return await ProjectAgentRunner(muse, CONFIG).analyze_red(
        DOCS, project_name="demo", cycle=1, max_batch_bytes=4096, triage_enabled=False
    )


@pytest.mark.asyncio
async def test_bad_probe_is_repaired_once():
    muse = _Muse([BAD, GOOD])
    artifacts = await _run(muse)
    assert artifacts.report.verification_script_python == GOOD
    assert len(muse.report_payloads) == 2
    assert "probe_syntax_error" in muse.report_payloads[1]["review"]


@pytest.mark.asyncio
async def test_valid_probe_makes_no_extra_call():
    muse = _Muse([GOOD])
    await _run(muse)
    assert len(muse.report_payloads) == 1


@pytest.mark.asyncio
async def test_second_bad_probe_is_returned_unchanged_for_fail_closed_guard():
    muse = _Muse([BAD, BAD])
    artifacts = await _run(muse)
    assert artifacts.report.verification_script_python == BAD
    assert len(muse.report_payloads) == 2
