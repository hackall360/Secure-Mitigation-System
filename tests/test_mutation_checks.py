# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Wave 2 item 4 tests: bounded deterministic mutation-count probes (node only).

Competitor snapshot fuzzers do open-ended mutation storms outside the verify
loop; we run N deterministic seeded input mutations in the same capped
container as regression, widening the normal-behavior net without new
privileges. Fail-first: unknown fixture id exits 2; any mutation failure or
inconclusive run vetoes both retain decisions (fail-closed).
"""

import json
import re
import urllib.error

from modules.core.checks import (
    MUTATION_COUNT,
    project_mutation_script,
    project_property_mutation_script,
    project_property_script,
)
from modules.workflows.project_workflow import (
    ExecutionEvidence,
    SnapshotVerification,
    mutation_gate_passed,
)


def _run_script(script: str, handler) -> int:
    """Execute a generated mutation script with a stubbed HTTP layer (no network)."""
    import types
    import urllib.request as request_module

    calls: list[str] = []

    class FakeResponse:
        def __init__(self, status: int, body: bytes):
            self.status = status
            self._body = body

        def read(self, limit: int = -1) -> bytes:
            return self._body[:limit] if limit >= 0 else self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(url, timeout=3):
        calls.append(url)
        status, body = handler(url)
        if status != 200:
            raise urllib.error.HTTPError(url, status, "stubbed", {}, None)
        return FakeResponse(status, body)

    namespace = {
        "urllib": types.SimpleNamespace(request=types.SimpleNamespace(urlopen=fake_urlopen)),
        "__name__": "mutation_probe",
    }
    original = request_module.urlopen
    request_module.urlopen = fake_urlopen
    try:
        try:
            exec(compile(script, "mutation_check.py", "exec"), namespace)
        except SystemExit as exit:
            return int(exit.code)
    finally:
        request_module.urlopen = original
    raise AssertionError("mutation script must call sys.exit")


def _node_ok(url: str):
    # Real fixture JSON-envelope shape: {status, count, results}; decimal ids
    # only (101/102 known, anything else pure-decimal is an empty result set).
    assert "/lookup?id=" in url
    raw = url.rsplit("=", 1)[-1]
    rows = {"101": [{"id": 101}], "102": [{"id": 102}]}
    if raw in rows:
        results = rows[raw]
        return 200, json.dumps({"status": "ok", "count": 1, "results": results}).encode()
    if raw.isdecimal():
        return 200, json.dumps({"status": "ok", "count": 0, "results": []}).encode()
    return 400, json.dumps({"status": "error", "detail": "Invalid ID"}).encode()


def test_unknown_fixture_script_is_inconclusive():
    script = project_mutation_script("no_such_fixture")
    assert _run_script(script, lambda url: (200, b"{}")) == 2


def test_node_mutations_pass_on_healthy_envelope_service():
    script = project_mutation_script("node_query_sink")
    assert _run_script(script, _node_ok) == 0


def test_node_mutations_fail_on_row_leak():
    script = project_mutation_script("node_query_sink")

    def leaking(url: str):
        if "/lookup?id=" in url and url.rsplit("=", 1)[-1] not in ("101", "102"):
            return (
                200,
                json.dumps(
                    {"status": "ok", "count": 2, "results": [{"id": 101}, {"id": 102}]}
                ).encode(),
            )
        return _node_ok(url)

    assert _run_script(script, leaking) == 1


def test_node_mutations_inconclusive_on_crashed_service():
    script = project_mutation_script("node_query_sink")

    def crashed(url: str):
        return 500, b"<html>Internal Server Error</html>"

    assert _run_script(script, crashed) == 2


def test_mutation_count_is_bounded_deterministic_and_seeded():
    first = project_mutation_script("node_query_sink")
    second = project_mutation_script("node_query_sink")
    assert first == second
    assert len(first) < 16_384
    assert "sys.exit(0" in first and "sys.exit(1" in first and "sys.exit(2" in first
    match = re.search(r"MUTATION_IDS = (\[.*?\])", first)
    assert match is not None
    ids = json.loads(match.group(1).replace("'", '"'))
    assert len(ids) == MUTATION_COUNT == 8
    assert all(re.fullmatch(r"[0-9]+", item) for item in ids)
    assert "101" in ids
    assert not {"101", "102", "999"} >= set(ids)


def test_mutation_gate_truth_table_is_fail_closed():
    def verification(mutations_exit: int | None) -> SnapshotVerification:
        return SnapshotVerification(
            probe=ExecutionEvidence(exit_code=1, output="blocked"),
            regression=ExecutionEvidence(exit_code=0, output="regression ok"),
            mutations=None
            if mutations_exit is None
            else ExecutionEvidence(exit_code=mutations_exit, output="mutations"),
        )

    assert mutation_gate_passed(verification(0)) is True
    assert mutation_gate_passed(verification(1)) is False
    assert mutation_gate_passed(verification(2)) is False
    assert mutation_gate_passed(verification(None)) is True


def _verification_with_mutations(probe: int, regression: int, mutations: int | None):
    return SnapshotVerification(
        probe=ExecutionEvidence(exit_code=probe, output="evidence"),
        regression=ExecutionEvidence(exit_code=regression, output="regression"),
        fresh_target=True,
        mutations=None
        if mutations is None
        else ExecutionEvidence(exit_code=mutations, output="mutations"),
    )


async def test_mutation_failure_vetoes_main_retain():
    """Fail-first: blocked probe + green regression still rolls back on mutations 1."""
    from helpers import FakeProjectMuse as FakeMuse
    from helpers import FakeProjectSandbox as FakeSandbox
    from helpers import run_project_workflow as run_workflow

    muse = FakeMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeSandbox(
        [
            _verification_with_mutations(1, 0, 0),
            _verification_with_mutations(0, 0, 0),
            # patched snapshot: probe blocked + regression green, mutations failed.
            _verification_with_mutations(1, 0, 1),
        ]
    )
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert result.cycle_reports[0].status == "rolled_back"
    assert result.cycle_reports[0].evidence.patched_verification.mutations.exit_code == 1


async def test_mutation_inconclusive_vetoes_independent_retain():
    """Fail-first: mutations exit 2 on the independent re-verify rolls back too."""
    from helpers import FakeProjectMuse as FakeMuse
    from helpers import FakeProjectSandbox as FakeSandbox
    from helpers import run_project_workflow as run_workflow

    muse = FakeMuse(red_outcomes=["finding", "finding", "no_finding"])
    sandbox = FakeSandbox(
        [
            _verification_with_mutations(1, 0, 0),
            _verification_with_mutations(0, 0, 0),
            # patched snapshot green incl. mutations; independent re-verify inconclusive.
            _verification_with_mutations(1, 0, 0),
            _verification_with_mutations(1, 0, 2),
        ]
    )
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert result.cycle_reports[0].status == "rolled_back"
    assert result.cycle_reports[0].evidence.independent_verification.mutations.exit_code == 2


def test_combined_property_mutation_script_matches_both_contracts():
    """Combined node script passes where both standalone scripts pass, same run count."""
    combined = project_property_mutation_script("node_query_sink")
    assert len(combined) < 16_384
    assert "sys.exit(0" in combined and "sys.exit(1" in combined and "sys.exit(2" in combined
    healthy = _run_script(combined, _node_ok)
    standalone_property = _run_script(project_property_script("node_query_sink"), _node_ok)
    standalone_mutation = _run_script(project_mutation_script("node_query_sink"), _node_ok)
    assert (standalone_property, standalone_mutation, healthy) == (0, 0, 0)


def test_combined_script_is_inconclusive_for_unknown_fixture():
    script = project_property_mutation_script("no_such_fixture")
    assert _run_script(script, lambda url: (200, b"{}")) == 2


async def test_docker_sandbox_records_mutations_on_shared_run(tmp_path):
    """DockerProjectSandbox records mutations evidence without an extra container run."""
    from helpers import TEST_CONFIG as CONFIG

    from modules.core.docker_manager import ProjectCheckResult
    from modules.services.projects import ProjectSpec, snapshot_project
    from modules.workflows.project_workflow import DockerProjectSandbox

    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    spec = ProjectSpec(
        path=tmp_path,
        command=["python", "app.py"],
        test_command=["python", "-m", "pytest"],
        contract="node_query_sink\nGET /lookup fixture.",
    )
    snapshot = snapshot_project(spec)
    scripts: list[str] = []

    class _Manager:
        def start_project(self, network, _spec, _snapshot):
            return object(), "image"

        def run_project_check(self, network, _spec, _snapshot, *, command=None, script=None):
            if script is not None:
                scripts.append(script)
            return ProjectCheckResult(exit_code=0, stdout="ok", stderr="")

        def stop_project(self, _target):
            return None

    sandbox = DockerProjectSandbox.__new__(DockerProjectSandbox)
    sandbox.config = CONFIG
    sandbox.spec = spec
    sandbox.base_snapshot = snapshot
    sandbox.manager = _Manager()
    sandbox.network = "test-network"
    result = sandbox.verify_project_snapshot(
        {"name": "demo"},
        {"app.py": "print('ok')\n"},
        "import sys\nsys.exit(1)",
        ["python", "-m", "pytest"],
        label="mutations-plumbing",
    )
    assert result.properties is not None
    assert result.mutations is not None
    assert result.properties.exit_code == 0
    assert result.mutations.exit_code == 0
    # Probe (1) + one combined properties/mutations run (2): no extra container runs.
    assert len(scripts) == 2
    assert "Mutation checks passed" in scripts[1]
