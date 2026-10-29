# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""SPEC 14.8 item 4 tests: bounded deterministic mutation-count probes (php + mysql + node).

N deterministic seeded mutations per fixture contract, run in the same capped
container as regression, recorded as evidence on SnapshotVerification; any
mutation failure vetoes the retain (fail closed). Unknown fixture id MUST
exit 2. Node matches the JSON-envelope shape; PHP matches the real host-arg shape (status/host/diagnostic text, not
the node JSON envelope); MySQL matches the config re-read shape (/my.cnf).
"""

import json
import re
import urllib.error
import urllib.request

import pytest

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


def _run_script(script: str, handler) -> tuple[int, list[str]]:
    """Execute a generated mutation script with a stubbed HTTP layer (no network)."""
    import types

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
    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        try:
            exec(compile(script, "mutation_check.py", "exec"), namespace)
        except SystemExit as exit:
            return int(exit.code), calls
    finally:
        urllib.request.urlopen = original
    raise AssertionError("mutation script must call sys.exit")


def _php_unquote(url: str) -> str:
    import urllib.parse

    assert "/?host=" in url
    return urllib.parse.unquote(url.rsplit("=", 1)[-1])


def _php_ok(url: str):
    """Healthy service: exact echo for benign hosts, clean 4xx reject for metachars."""
    import urllib.parse

    host = urllib.parse.unquote(url.rsplit("=", 1)[-1])
    assert "/?host=" in url
    if any(c in host for c in (";", "$", "`", "|", "&", " ")):
        return 400, b'{"status":"error"}'
    return 200, json.dumps({"status": "ok", "host": host, "diagnostic": host}).encode()


def _mysql_ok(url: str):
    assert url.split("?")[0].endswith("/my.cnf")
    return 200, b"[mysqld]\nport = 3306\nmax_connections = 100\n"


def test_mutation_php_unknown_fixture_exits_2():
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("no_such_fixture")
    code, _ = _run_script(script, lambda url: (200, b"{}"))
    assert code == 2


def test_mutation_mysql_unknown_fixture_exits_2():
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("no_such_fixture_xyz")
    code, _ = _run_script(script, lambda url: (200, b"{}"))
    assert code == 2


def test_mutation_php_pass_on_healthy_service():
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("php_command_sink")
    code, _ = _run_script(script, _php_ok)
    assert code == 0


def test_mutation_php_fail_on_executing_service():
    """Shell-mangled echo (diagnostic != host) on a metachar mutation exits 1."""
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("php_command_sink")

    def executing(url: str):
        host = _php_unquote(url)
        if any(c in host for c in (";", "$", "`", "|", "&")):
            return 200, json.dumps(
                {"status": "ok", "host": host, "diagnostic": "uid=0(root)"}
            ).encode()
        return _php_ok(url)

    code, _ = _run_script(script, executing)
    assert code == 1


def test_mutation_php_reject_counts_as_pass():
    """A strict allowlist that 400-rejects every metachar mutation still passes."""
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("php_command_sink")

    def strict(url: str):
        host = _php_unquote(url)
        if host in ("localhost", "127.0.0.1"):
            return 200, json.dumps({"status": "ok", "host": host, "diagnostic": host}).encode()
        return 400, b'{"status":"error"}'

    code, _ = _run_script(script, strict)
    assert code == 0


def test_mutation_php_fail_on_server_error():
    """A 5xx crash on a mutation is mishandling, not a clean reject: exit 1."""
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("php_command_sink")

    def crashing(url: str):
        host = _php_unquote(url)
        if host not in ("localhost", "127.0.0.1"):
            return 500, b"boom"
        return _php_ok(url)

    code, _ = _run_script(script, crashing)
    assert code == 1


def test_mutation_php_request_count_is_bounded():
    from modules.core.checks import MUTATION_COUNT, project_mutation_script

    script = project_mutation_script("php_command_sink")
    code, calls = _run_script(script, _php_ok)
    assert code == 0
    assert len(calls) == MUTATION_COUNT


def test_mutation_php_script_is_deterministic():
    from modules.core.checks import project_mutation_script

    assert project_mutation_script("php_command_sink") == project_mutation_script(
        "php_command_sink"
    )


def test_mutation_mysql_pass_on_stable_config():
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("mysql_insecure_conf")
    code, _ = _run_script(script, _mysql_ok)
    assert code == 0


def test_mutation_mysql_fail_on_flapping_config():
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("mysql_insecure_conf")
    seen: list[str] = []

    def flapping(url: str):
        seen.append(url)
        if len(seen) > 1:
            return 200, b"[mysqld]\nport = 3307\nmax_connections = 100\n"
        return _mysql_ok(url)

    code, _ = _run_script(script, flapping)
    assert code == 1


def test_mutation_mysql_fail_on_missing_key():
    from modules.core.checks import project_mutation_script

    script = project_mutation_script("mysql_insecure_conf")

    def missing(url: str):
        assert url.split("?")[0].endswith("/my.cnf")
        return 200, b"[mysqld]\nport = 3306\n"

    code, _ = _run_script(script, missing)
    assert code == 1


def test_mutation_mysql_request_count_is_bounded():
    from modules.core.checks import MUTATION_COUNT, project_mutation_script

    script = project_mutation_script("mysql_insecure_conf")
    code, calls = _run_script(script, _mysql_ok)
    assert code == 0
    assert len(calls) == MUTATION_COUNT


def test_mutation_mysql_script_is_deterministic():
    from modules.core.checks import project_mutation_script

    assert project_mutation_script("mysql_insecure_conf") == project_mutation_script(
        "mysql_insecure_conf"
    )


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


@pytest.mark.parametrize("fixture", ["php_command_sink", "mysql_insecure_conf", "node_query_sink"])
def test_mutation_scripts_bounded_and_explicit_exit(fixture):
    script = project_mutation_script(fixture)
    assert len(script) < 16_384
    assert "sys.exit(0" in script and "sys.exit(1" in script and "sys.exit(2" in script


def test_unknown_fixture_script_is_inconclusive():
    script = project_mutation_script("no_such_fixture")
    code, _ = _run_script(script, lambda url: (200, b"{}"))
    assert code == 2


def test_node_mutations_pass_on_healthy_envelope_service():
    script = project_mutation_script("node_query_sink")
    code, _ = _run_script(script, _node_ok)
    assert code == 0


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

    code, _ = _run_script(script, leaking)
    assert code == 1


def test_node_mutations_inconclusive_on_crashed_service():
    script = project_mutation_script("node_query_sink")

    def crashed(url: str):
        return 500, b"<html>Internal Server Error</html>"

    code, _ = _run_script(script, crashed)
    assert code == 2


def test_mutation_count_is_bounded_deterministic_and_seeded():
    first = project_mutation_script("node_query_sink")
    second = project_mutation_script("node_query_sink")
    assert first == second
    assert len(first) < 16_384
    assert "sys.exit(0" in first and "sys.exit(1" in first and "sys.exit(2" in first
    match = re.search(r"MUTATION_IDS = (\[.*?\])", first)
    assert match is not None
    ids = json.loads(match.group(1).replace("'", '"'))
    assert len(ids) == MUTATION_COUNT == 4
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
    healthy, _ = _run_script(combined, _node_ok)
    standalone_property, _ = _run_script(project_property_script("node_query_sink"), _node_ok)
    standalone_mutation, _ = _run_script(project_mutation_script("node_query_sink"), _node_ok)
    assert (standalone_property, standalone_mutation, healthy) == (0, 0, 0)


def test_combined_script_is_inconclusive_for_unknown_fixture():
    script = project_property_mutation_script("no_such_fixture")
    code, _ = _run_script(script, lambda url: (200, b"{}"))
    assert code == 2


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


# SPEC 14.9 item 2 (Wave 5, Lane 2 keep) RED: frozen-pool determinism guard.
# Fuzz4All/TitanFuzz chase coverage with novel input storms; we pin
# deterministic per-contract mutants byte-identical across runs, proving
# robustness inside the verify loop. Any nondeterminism source fails closed.

FROZEN_POOL_DIGEST = "faf483183d8de114182ebe7cbb92909f00e09f4a19af7920cceaa89ddb27e5cc"


def _fresh_process_pools() -> dict:
    """Recompute mutation pools in a brand-new interpreter (cross-run proof)."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    code = (
        "import json;"
        "from modules.core.checks import mutation_pool_snapshot;"
        "print(json.dumps(mutation_pool_snapshot(), sort_keys=True))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=root,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    return json.loads(proc.stdout)


def test_frozen_pool_digest_marker_byte_identical_across_runs():
    """Pools match the frozen digest in-process AND in a fresh interpreter,
    and every fixture script carries the digest marker (verify-loop evidence).
    TRAP: node = JSON envelope ids, php = plain-text host args,
    mysql = config re-read paths; never mix shapes."""
    import hashlib

    from modules.core.checks import (
        MUTATION_SEED,
        _mutation_mysql_paths,
        _mutation_node_ids,
        _mutation_php_hosts,
        project_mutation_script,
        project_property_mutation_script,
    )

    live = {
        "mysql_insecure_conf": _mutation_mysql_paths(),
        "node_query_sink": _mutation_node_ids(MUTATION_SEED),
        "php_command_sink": _mutation_php_hosts(),
    }
    assert (
        len(live["node_query_sink"])
        == len(live["php_command_sink"])
        == len(live["mysql_insecure_conf"])
        == MUTATION_COUNT
    )
    canon = json.dumps(live, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canon).hexdigest() == FROZEN_POOL_DIGEST
    assert _fresh_process_pools() == json.loads(json.dumps(live, sort_keys=True))
    for fixture in ("node_query_sink", "php_command_sink", "mysql_insecure_conf"):
        assert FROZEN_POOL_DIGEST in project_mutation_script(fixture)
    assert FROZEN_POOL_DIGEST in project_property_mutation_script("node_query_sink")


def test_mutation_guard_fails_closed_on_pool_drift(monkeypatch):
    """Any nondeterminism source (here: drifted php pool) fails script build."""
    import modules.core.checks as checks

    monkeypatch.setattr(checks, "_mutation_php_hosts", lambda: ["localhost"])
    with pytest.raises(ValueError, match="[Ff]rozen|[Nn]ondeterminism|[Dd]rift"):
        checks.project_mutation_script("php_command_sink")


# ZERO_DAY_BLUEPRINT item 2 (wolf) RED: combined-path build failure must
# fail closed. A frozen-pool ValueError while building the node
# property+mutation script must set BOTH properties_ev and mutations_ev
# to exit-2 evidence; mutations None would pass the gate vacuously.
async def test_combined_build_failure_sets_both_evidences_exit_2(tmp_path, monkeypatch):
    """Frozen pool drift on the node combined path vetoes via both gates."""
    from helpers import TEST_CONFIG as CONFIG

    import modules.core.checks as checks
    from modules.core.docker_manager import ProjectCheckResult
    from modules.services.projects import ProjectSpec, snapshot_project
    from modules.workflows.project_workflow import (
        DockerProjectSandbox,
        mutation_gate_passed,
        property_gate_passed,
    )

    monkeypatch.setattr(checks, "_mutation_node_ids", lambda seed: ["101"])
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    spec = ProjectSpec(
        path=tmp_path,
        command=["python", "app.py"],
        test_command=["python", "-m", "pytest"],
        contract="node_query_sink\nGET /lookup fixture.",
    )
    snapshot = snapshot_project(spec)

    class _Manager:
        def start_project(self, network, _spec, _snapshot):
            return object(), "image"

        def run_project_check(self, network, _spec, _snapshot, *, command=None, script=None):
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
        label="combined-build-failure",
    )
    assert result.properties is not None
    assert result.mutations is not None
    assert result.properties.exit_code == 2
    assert result.mutations.exit_code == 2
    # Both fail-closed gates must veto, never pass vacuously.
    assert property_gate_passed(result) is False
    assert mutation_gate_passed(result) is False
