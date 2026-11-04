# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Slice C RED pins: red parallel evidence respects a bounded semaphore,
emits per-batch progress, and matches sequential results on fixture data.

LAW 9 red-first: all three fail before the parallel implementation lands
(mock model client + fixture docs only, no Docker, no secrets).

Design under test (to be implemented in library/services/project_agents.py):
- analyze_red gains an optional progress callback (emit-compatible
  ``log(team, message)``) invoked per batch×assignment unit as
  ``[phase red evidence] batch i/N started`` / ``... finished``.
- analyze_red gains a bounded-concurrency knob (config default 4-8):
  at most K evidence calls in flight at once.
"""

import asyncio

import pytest

from modules.core.config import PurpleBoxConfig
from modules.services.project_agents import ProjectAgentRunner, SourceDocument

CONFIG = PurpleBoxConfig(meta_api_key="unit-test-key")

DOCS = [
    SourceDocument(path="a.py", content="a" * 900),
    SourceDocument(path="b.py", content="b" * 900),
]


class _TrackedMuse:
    """Mock model client tracking peak in-flight evidence calls."""

    def __init__(self, delay: float = 0.02):
        from modules.services.project_agents import RedBatchEvidence, RedReport

        self._evidence_cls = RedBatchEvidence
        self._report_cls = RedReport
        self.delay = delay
        self.calls = []
        self.in_flight = 0
        self.peak_in_flight = 0

    async def _request(self, model, system, payload, schema, role=""):
        self.calls.append({"role": role, "schema": schema, "payload": payload})
        if schema is self._evidence_cls:
            self.in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
            try:
                await asyncio.sleep(self.delay)
            finally:
                self.in_flight -= 1
            return self._evidence_cls(candidates=[], observations=["ok"])
        if schema is self._report_cls:
            return self._report_cls(
                outcome="no_finding",
                analysis_summary="No testable finding in fixture scope.",
                limitations=["Not a general security claim."],
            )
        raise AssertionError(f"Unexpected schema: {schema}")


async def _run(calls_log=None, **kwargs):
    muse = _TrackedMuse()
    runner = ProjectAgentRunner(muse, CONFIG)
    progress = []

    async def _progress(team, message):
        progress.append((team, message))
        if calls_log is not None:
            calls_log.append((team, message))

    artifacts = await runner.analyze_red(
        DOCS,
        project_name="demo",
        cycle=1,
        max_batch_bytes=1024,
        on_progress=_progress,
        **kwargs,
    )
    return muse, artifacts, progress


async def test_red_parallelism_respects_configured_bound():
    """Bounded semaphore: peak in-flight evidence calls must stay within the knob."""
    muse, _artifacts, _progress = await _run(max_parallel_batches=1)
    assert muse.peak_in_flight <= 1, (
        f"semaphore bound violated: peak={muse.peak_in_flight} with bound=1"
    )


async def test_red_progress_emits_per_batch_start_and_finish():
    """WS stream never goes dark: one finished line per batch unit.

    Merged contract (slices C+E): progress fires on unit COMPLETION only,
    not start+finish. Start+finish double-spends the shared per-run chatter
    budget (each multiple-of-every done fires twice), breaking E's rate-limit
    pin on real trees. Completion lines arrive throughout the parallel run,
    so the liveness intent is preserved with half the budget spend.
    """
    _muse, _artifacts, progress = await _run(max_parallel_batches=2)
    finished = [m for _t, m in progress if m.startswith("[phase red evidence]") and "finished" in m]
    # Fixture data yields 2 batches x 1 (no leader plan) = 2 units.
    assert len(finished) == 2, f"progress lines missing: {progress!r}"
    for team, _message in progress:
        assert team == "red"


async def test_red_parallel_matches_sequential_on_fixture_data():
    """Same fixture docs: bound=1 (serial) and bound=4 must return identical reports."""
    _m1, a1, _p1 = await _run(max_parallel_batches=1)
    _m2, a2, _p2 = await _run(max_parallel_batches=4)
    assert a1.report.model_dump() == a2.report.model_dump()
    assert [e.model_dump() for e in a1.batch_evidence] == [
        e.model_dump() for e in a2.batch_evidence
    ]
    assert a1.coverage.model_dump() == a2.coverage.model_dump()


def test_red_parallelism_knob_defaults_validates_and_surfaces(monkeypatch):
    """Config knob: default 4, range 1-8 enforced, env reader wired."""
    import importlib
    from dataclasses import replace

    import library.core.config as config_mod

    importlib.reload(config_mod)
    ConfigurationError = config_mod.ConfigurationError
    load_config = config_mod.load_config
    Config = config_mod.PurpleBoxConfig

    assert Config().red_evidence_parallelism == 4
    replace(Config(), red_evidence_parallelism=1).validate()
    replace(Config(), red_evidence_parallelism=8).validate()
    with pytest.raises(ConfigurationError):
        replace(Config(), red_evidence_parallelism=0).validate()
    with pytest.raises(ConfigurationError):
        replace(Config(), red_evidence_parallelism=9).validate()
    monkeypatch.setenv("PURPLEBOX_RED_EVIDENCE_PARALLELISM", "6")
    assert load_config().red_evidence_parallelism == 6


async def test_red_evidence_failure_fails_closed_not_partial():
    """A failed evidence unit raises AgentError; no partial evidence is returned."""

    class _FailingMuse(_TrackedMuse):
        async def _request(self, model, system, payload, schema, role=""):
            if schema is self._evidence_cls and "batch_1" in role:
                from modules.core.agents import AgentError as _AgentError

                raise _AgentError("mock evidence failure; no secrets here")
            return await super()._request(model, system, payload, schema, role=role)

    from modules.core.agents import AgentError

    muse = _FailingMuse()
    runner = ProjectAgentRunner(muse, CONFIG)
    with pytest.raises(AgentError):
        await runner.analyze_red(DOCS, project_name="demo", cycle=1, max_batch_bytes=1024)
