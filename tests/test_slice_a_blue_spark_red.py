# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9) Slice A: balanced profile is Spark/Spark; project workflow escalates blue once.

LAWs 0, 2, 3, 9 govern this file. Written BEFORE the Slice A implementation:
every behavioral test below must FAIL on unpatched code for the expected
functional reason (profile blue is Wonder; no escalation knob/call exists),
then pass after.

Style mirror: tests/test_red_model_swap_red.py (plain asserts, no mocks of
the unit). Escalation tests mock Docker + the model client only (never a live
API call): helpers.FakeProjectMuse/_FakeSandbox doubles, TEST_API_KEY config.
"""

from __future__ import annotations


def test_balanced_profile_blue_is_spark_not_wonder():
    """Balanced must run Spark blue (default economy-grade cost); quality keeps Wonder."""
    from library.core.profiles import META_PROFILES

    balanced = META_PROFILES["balanced"]
    assert balanced.red_model == "muse-spark-1.3-contributor"
    assert balanced.blue_model == "muse-spark-1.3-contributor"
    assert META_PROFILES["quality"].blue_model == "muse-wonder-1.0"


def test_default_profile_still_balanced_on_stock_config():
    """Stock config is Spark/Spark; balanced and economy share the pair, balanced wins first."""
    from modules.core.config import PurpleBoxConfig
    from modules.core.profiles import META_PROFILES, default_profile

    assert (PurpleBoxConfig().red_team_model, PurpleBoxConfig().blue_team_model) == (
        "muse-spark-1.3-contributor",
        "muse-spark-1.3-contributor",
    )
    assert default_profile(PurpleBoxConfig()) in ("economy", "balanced")
    assert META_PROFILES["balanced"].blue_model == "muse-spark-1.3-contributor"


def _keyed_config(monkeypatch, tmp_path, escalation=""):
    """Load config from an isolated cwd so the developer .env can never leak in."""
    from modules.core.config import load_config

    monkeypatch.chdir(tmp_path)
    for name in (
        "META_MUSE_API_KEY",
        "META_MUSE_BASE_URL",
        "META_MUSE_RED_MODEL",
        "META_MUSE_BLUE_MODEL",
        "META_MUSE_BLUE_ESCALATION_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("META_MUSE_API_KEY", "unit-test-key")
    if escalation:
        monkeypatch.setenv("META_MUSE_BLUE_ESCALATION_MODEL", escalation)
    return load_config()


def test_escalation_knob_defaults_off_and_is_fail_closed_without_key(monkeypatch, tmp_path):
    """Knob defaults to empty (off); without a key the workflow errors (LAW 4)."""
    import asyncio

    import helpers

    from modules.core.config import PurpleBoxConfig
    from modules.workflows.project_workflow import (
        ProjectWorkflowInput,
        execute_project_workflow,
    )

    cfg = _keyed_config(monkeypatch, tmp_path)
    assert cfg.blue_escalation_model == ""

    async def go() -> object:
        return await execute_project_workflow(
            ProjectWorkflowInput(
                name="demo",
                files={"src/app.py": "value = input()\nprint(value)\n"},
                regression_command=["pytest", "-q"],
            ),
            helpers.silent_emit,
            cycles=1,
            config=PurpleBoxConfig(),
            sandbox_factory=lambda _settings: helpers.FakeProjectSandbox(
                [helpers.project_verification(1)]
            ),
            muse_factory=lambda _settings: helpers.FakeProjectMuse(red_outcomes=["no_finding"]),
        )

    result = asyncio.run(go())
    assert result.status == "error"
    assert "META_MUSE_API_KEY" in result.message


def test_escalation_env_key_loads_model(monkeypatch, tmp_path):
    """META_MUSE_BLUE_ESCALATION_MODEL keyed value flows into the config knob."""
    cfg = _keyed_config(monkeypatch, tmp_path, escalation="muse-wonder-1.0")
    assert cfg.blue_escalation_model == "muse-wonder-1.0"


def _escalating_muse():
    """Fake client: first blue proposes a guard, second (escalated) proposes a bigger one.

    The first proposal's patched verification still shows the probe reachable
    (rollback), so the workflow must make ONE separate escalated blue call with
    the stronger model — a distinct role, not a silent same-model retry.
    """

    class EscalatingMuse:
        def __init__(self):
            self.calls = []
            self.closed = False
            self.usage = []

        async def _request(self, model, system, payload, schema, role=""):
            from modules.services.project_agents import (
                BlueProposal as _BP,
            )
            from modules.services.project_agents import (
                FileReplacement as _FRpl,
            )
            from modules.services.project_agents import (
                FinalBlueReport as _FR,
            )
            from modules.services.project_agents import (
                RedBatchEvidence as _RBE,
            )
            from modules.services.project_agents import (
                RedCandidate as _RC,
            )
            from modules.services.project_agents import (
                RedEvidenceDigest as _RED,
            )
            from modules.services.project_agents import (
                RedReport as _RR,
            )

            self.calls.append({"model": model, "role": role})
            if schema is _RBE:
                chunks = payload.get("batch", {}).get("chunks", [])
                if not chunks:
                    for item in payload.get("evidence_items", []):
                        for cand in item.get("candidates", []):
                            chunks.append({"path": cand.get("affected_paths", ["src/app.py"])[0]})
                if not chunks:
                    chunks = [{"path": "src/app.py"}]
                return _RBE(
                    candidates=[
                        _RC(
                            vulnerability="injection",
                            affected_paths=[chunk["path"]],
                            evidence="untrusted input reaches a sink",
                            verification_script_python="import sys\nsys.exit(0)",
                            confidence="high",
                        )
                        for chunk in chunks
                    ],
                    observations=["reviewed supplied chunk only"],
                )
            if schema is _RED:
                digested = []
                for item in payload.get("evidence_items", []):
                    for cand in item.get("candidates", []):
                        digested.append(
                            _RC(
                                vulnerability=cand.get("vulnerability", "injection"),
                                affected_paths=cand.get("affected_paths", ["src/app.py"]),
                                evidence=cand.get("evidence", "untrusted input reaches a sink"),
                                verification_script_python=cand.get(
                                    "verification_script_python", "import sys\nsys.exit(0)"
                                ),
                                confidence="high",
                            )
                        )
                return _RED(
                    candidates=digested[:8],
                    summary="A concrete testable input boundary was identified.",
                    limitations=[],
                )
            if schema is _RR:
                candidates = []
                for item in payload.get("evidence_digests", []):
                    candidates.extend(item.get("candidates", []))
                candidate = candidates[0] if candidates else None
                if candidate is None or payload.get("phase") == "verification":
                    return _RR(
                        outcome="no_finding",
                        analysis_summary="No testable finding in the supplied bounded context.",
                        limitations=["test"],
                    )
                return _RR(
                    outcome="finding",
                    vulnerability=candidate["vulnerability"],
                    affected_paths=candidate["affected_paths"],
                    analysis_summary="Untrusted input reaches a sink.",
                    verification_script_python=candidate["verification_script_python"],
                    limitations=["test"],
                )
            if schema is _BP:
                blue_calls = [
                    c
                    for c in self.calls
                    if "blue_proposal" in c["role"] and "escalat" not in c["role"]
                ]
                first = len(blue_calls) == 1 and "escalat" not in role
                matches = [
                    d
                    for d in payload["safe_snapshot_files"]
                    if not d["content"].endswith("# escalated guard\n")
                ]
                source = matches[0] if matches else payload["safe_snapshot_files"][0]
                suffix = (
                    "\n# validated input\n" if first else "\n# validated input\n# escalated guard\n"
                )
                return _BP(
                    strategy="Escalated fix." if not first else "First attempt.",
                    replacements=[
                        _FRpl(
                            path=source["path"],
                            original_sha256=source["sha256"],
                            replacement_content=source["content"] + suffix,
                            rationale="Reject malformed input.",
                            change_kind="input_validation",
                        )
                    ],
                    limitations=[],
                )
            return _FR(
                disposition=payload["stage_evidence"]["disposition"],
                summary="test",
                evidence=[],
                changed_paths=[],
                limitations=[],
            )

        async def aclose(self):
            self.closed = True

    return EscalatingMuse()


def _escalating_runner(cfg):
    """Wrap the recording muse in a real ProjectAgentRunner bound to the keyed config."""
    from modules.services.project_agents import ProjectAgentRunner

    muse = _escalating_muse()

    class _Client:
        def __init__(self, inner):
            self._inner = inner
            self.usage = inner.usage
            self.closed = False

        async def _request(self, model, system, payload, schema, role=""):
            return await self._inner._request(model, system, payload, schema, role=role)

        async def aclose(self):
            self.closed = True
            self._inner.closed = True

    client = _Client(muse)
    return ProjectAgentRunner(client, cfg), muse, client


def test_escalation_retries_once_with_stronger_model_on_rollback(monkeypatch, tmp_path):
    """Rollback (empty first proposal) triggers ONE separate escalated blue call, new role."""
    import asyncio

    import helpers

    cfg = _keyed_config(monkeypatch, tmp_path, escalation="muse-wonder-1.0")
    runner, muse, client = _escalating_runner(cfg)
    sandbox = helpers.FakeProjectSandbox(
        [
            _slice_verification(1),  # baseline
            _slice_verification(0),  # pre probe reachable
            _slice_verification(0),  # first patched probe still reachable -> rollback
            _slice_verification(1),  # escalated patched probe blocked -> retained
        ]
    )

    async def go() -> object:
        from modules.workflows.project_workflow import (
            ProjectWorkflowInput,
            execute_project_workflow,
        )

        project = ProjectWorkflowInput(
            name="demo",
            files={"src/app.py": "value = input()\nprint(value)\n"},
            regression_command=["pytest", "-q"],
        )
        result = await execute_project_workflow(
            project,
            helpers.silent_emit,
            cycles=1,
            config=cfg,
            sandbox_factory=lambda _settings: sandbox,
            muse_factory=lambda _settings: client,
            agent_factory=lambda _muse, _cfg: runner,
        )
        assert client.closed and sandbox.closed
        return result

    result = asyncio.run(go())
    assert result.status in ("verified", "partial")
    blue_roles = [
        c["role"]
        for c in muse.calls
        if "blue_" in c["role"] and ("proposal" in c["role"] or "escalated" in c["role"])
    ]
    escalated = [r for r in blue_roles if "escalat" in r]
    assert len(escalated) == 1, f"expected exactly one escalation call among {blue_roles}"
    models = {
        c["model"]
        for c in muse.calls
        if "blue_" in c["role"] and ("proposal" in c["role"] or "escalated" in c["role"])
    }
    assert "muse-wonder-1.0" in models, f"escalation model never used: {models}"


def test_no_repeat_escalation_second_rollback_stays_rolled_back(monkeypatch, tmp_path):
    """Escalation fires at most once per cycle: a second failure stays rolled back."""
    import asyncio

    import helpers

    cfg = _keyed_config(monkeypatch, tmp_path, escalation="muse-wonder-1.0")
    runner, muse, client = _escalating_runner(cfg)
    sandbox = helpers.FakeProjectSandbox(
        [
            _slice_verification(1),  # baseline
            _slice_verification(0),  # pre probe reachable
            _slice_verification(0),  # first patched probe still reachable
            _slice_verification(0),  # escalated patched probe still reachable
        ]
    )

    async def go() -> object:
        from modules.workflows.project_workflow import (
            ProjectWorkflowInput,
            execute_project_workflow,
        )

        project = ProjectWorkflowInput(
            name="demo",
            files={"src/app.py": "value = input()\nprint(value)\n"},
            regression_command=["pytest", "-q"],
        )
        result = await execute_project_workflow(
            project,
            helpers.silent_emit,
            cycles=1,
            config=cfg,
            sandbox_factory=lambda _settings: sandbox,
            muse_factory=lambda _settings: client,
            agent_factory=lambda _muse, _cfg: runner,
        )
        assert client.closed and sandbox.closed
        return result

    result = asyncio.run(go())
    blue_roles = [
        c["role"]
        for c in muse.calls
        if "blue_" in c["role"] and ("proposal" in c["role"] or "escalated" in c["role"])
    ]
    assert sum("escalat" in r for r in blue_roles) == 1, blue_roles
    assert result.cycle_reports and result.cycle_reports[0].status == "rolled_back"


def test_escalation_disabled_by_default_never_escalates(monkeypatch, tmp_path):
    """Empty knob: rollback stays rolled back, exactly one blue call, no escalat role."""
    import asyncio

    import helpers

    cfg = _keyed_config(monkeypatch, tmp_path)
    runner, muse, client = _escalating_runner(cfg)
    sandbox = helpers.FakeProjectSandbox(
        [
            _slice_verification(1),
            _slice_verification(0),
            _slice_verification(0),
        ]
    )

    async def go() -> object:
        from modules.workflows.project_workflow import (
            ProjectWorkflowInput,
            execute_project_workflow,
        )

        project = ProjectWorkflowInput(
            name="demo",
            files={"src/app.py": "value = input()\nprint(value)\n"},
            regression_command=["pytest", "-q"],
        )
        result = await execute_project_workflow(
            project,
            helpers.silent_emit,
            cycles=1,
            config=cfg,
            sandbox_factory=lambda _settings: sandbox,
            muse_factory=lambda _settings: client,
            agent_factory=lambda _muse, _cfg: runner,
        )
        assert client.closed and sandbox.closed
        return result

    result = asyncio.run(go())
    blue_roles = [
        c["role"]
        for c in muse.calls
        if "blue_" in c["role"] and ("proposal" in c["role"] or "escalated" in c["role"])
    ]
    assert blue_roles and not any("escalat" in r for r in blue_roles), blue_roles
    assert result.cycle_reports and result.cycle_reports[0].status == "rolled_back"


def _slice_verification(probe: int, regression: int = 0, output: str = "evidence"):
    """Slice-local verification with the repeat run recorded (net passes)."""
    import helpers

    from modules.workflows.project_workflow import ExecutionEvidence

    ver = helpers.project_verification(probe, regression, output)
    return ver.model_copy(
        update={"repeat_regression": ExecutionEvidence(exit_code=regression, output="regression")}
    )


def test_no_escalation_without_key_even_on_rollback():
    """Fail closed: no key means error, never a silent upgrade attempt."""
    import asyncio

    from helpers import (
        FakeProjectMuse,
        FakeProjectSandbox,
        project_verification,
        silent_emit,
    )

    from modules.core.config import PurpleBoxConfig
    from modules.workflows.project_workflow import ProjectWorkflowInput, execute_project_workflow

    async def go() -> object:
        return await execute_project_workflow(
            ProjectWorkflowInput(
                name="demo",
                files={"src/app.py": "value = input()\nprint(value)\n"},
                regression_command=["pytest", "-q"],
            ),
            silent_emit,
            cycles=1,
            config=PurpleBoxConfig(),
            sandbox_factory=lambda _settings: FakeProjectSandbox(
                [
                    project_verification(1),
                    project_verification(0),
                    project_verification(0, 0),
                ]
            ),
            muse_factory=lambda _settings: FakeProjectMuse(red_outcomes=["finding", "no_finding"]),
        )

    result = asyncio.run(go())
    assert result.status == "error"
    assert "META_MUSE_API_KEY" in result.message
