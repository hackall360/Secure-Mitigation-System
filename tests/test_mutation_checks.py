# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""SPEC 14.8 item 4 tests (PHP + MySQL portion): bounded mutation-count probes.

N deterministic seeded mutations per fixture contract, run in the same capped
container as regression, recorded as evidence on SnapshotVerification; any
mutation failure vetoes the retain (fail closed). Unknown fixture id MUST
exit 2. PHP matches the real host-arg shape (status/host/diagnostic text, not
the node JSON envelope); MySQL matches the config re-read shape (/my.cnf).
"""

import json
import urllib.error
import urllib.request

import pytest


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

    script = project_mutation_script("node_query_sink")
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


@pytest.mark.parametrize("fixture", ["php_command_sink", "mysql_insecure_conf"])
def test_mutation_php_mysql_scripts_bounded_and_explicit_exit(fixture):
    from modules.core.checks import project_mutation_script

    script = project_mutation_script(fixture)
    assert len(script) < 16_384
    assert "sys.exit(0" in script and "sys.exit(1" in script and "sys.exit(2" in script


def _php_verification(mutations_exit: int | None):
    from modules.workflows.project_workflow import ExecutionEvidence, SnapshotVerification

    return SnapshotVerification(
        probe=ExecutionEvidence(exit_code=1, output="blocked"),
        regression=ExecutionEvidence(exit_code=0, output="regression ok"),
        fresh_target=True,
        mutations=None
        if mutations_exit is None
        else ExecutionEvidence(exit_code=mutations_exit, output="mutations"),
    )


def test_mutation_php_gate_truth_table_is_fail_closed():
    from modules.workflows.project_workflow import mutation_gate_passed

    assert mutation_gate_passed(_php_verification(0)) is True
    assert mutation_gate_passed(_php_verification(1)) is False
    assert mutation_gate_passed(_php_verification(2)) is False
    assert mutation_gate_passed(_php_verification(None)) is True


async def test_mutation_php_workflow_rolls_back_on_mutation_failure():
    """Fail-first: blocked probe + green regression still rolls back on mutations 1."""
    from helpers import FakeProjectMuse as FakeMuse
    from helpers import FakeProjectSandbox as FakeSandbox
    from helpers import run_project_workflow as run_workflow

    from modules.workflows.project_workflow import ExecutionEvidence, SnapshotVerification

    def verification(probe: int, regression: int, mutations: int | None):
        return SnapshotVerification(
            probe=ExecutionEvidence(exit_code=probe, output="evidence"),
            regression=ExecutionEvidence(exit_code=regression, output="regression"),
            fresh_target=True,
            mutations=None
            if mutations is None
            else ExecutionEvidence(exit_code=mutations, output="mutations"),
        )

    muse = FakeMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeSandbox(
        [
            verification(1, 0, None),
            verification(0, 0, None),
            # patched snapshot: probe blocked + regression green, mutations failed.
            verification(1, 0, 1),
        ]
    )
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert result.cycle_reports[0].status == "rolled_back"
    assert result.cycle_reports[0].evidence.patched_verification.mutations.exit_code == 1


async def test_mutation_mysql_workflow_retains_on_mutation_pass():
    """Blocked probe + green regression + mutations 0 retains."""
    from helpers import FakeProjectMuse as FakeMuse
    from helpers import FakeProjectSandbox as FakeSandbox
    from helpers import run_project_workflow as run_workflow

    from modules.workflows.project_workflow import ExecutionEvidence, SnapshotVerification

    def verification(probe: int, regression: int, mutations: int | None):
        return SnapshotVerification(
            probe=ExecutionEvidence(exit_code=probe, output="evidence"),
            regression=ExecutionEvidence(exit_code=regression, output="regression"),
            fresh_target=True,
            mutations=None
            if mutations is None
            else ExecutionEvidence(exit_code=mutations, output="mutations"),
        )

    muse = FakeMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeSandbox(
        [
            verification(1, 0, None),
            verification(0, 0, None),
            verification(1, 0, 0),
        ]
    )
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert result.cycle_reports[0].status == "retained"
    assert result.cycle_reports[0].evidence.patched_verification.mutations.exit_code == 0
