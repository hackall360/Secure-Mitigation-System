# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Wave 8 R1 tests: seeded property normal-contract checks.

Per-fixture property scripts pass on a stubbed healthy service, fail on a
stubbed broken one, exit 2 for unknown fixtures; a fail-closed retain gate
vetoes retains when recorded properties are non-zero.
"""

import json

import pytest

from checks import project_property_script
from project_workflow import (
    ExecutionEvidence,
    SnapshotVerification,
    property_gate_passed,
)


def _run_script(script: str, handler) -> int:
    """Execute a generated property script with a stubbed HTTP layer (no network)."""
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

    module = types.ModuleType("property_probe")
    module.__dict__["urllib"] = __import__("urllib.request"), __import__("urllib.error")
    import urllib.request

    module.__dict__["urllib_request"] = urllib.request
    module.__dict__["urllib_error"] = urllib.error
    namespace = {
        "urllib": types.SimpleNamespace(request=types.SimpleNamespace(urlopen=fake_urlopen)),
        "__name__": "property_probe",
    }
    # The script imports urllib.request/urllib.error itself; patch urlopen underneath.
    import urllib.request as request_module

    original = request_module.urlopen
    request_module.urlopen = fake_urlopen
    try:
        try:
            exec(compile(script, "property_check.py", "exec"), namespace)
        except SystemExit as exit:
            return int(exit.code)
    finally:
        request_module.urlopen = original
    raise AssertionError("property script must call sys.exit")


def _node_ok(url: str):
    if url.endswith("/lookup?id=101"):
        return 200, json.dumps(
            {"status": "ok", "count": 1, "results": [{"id": 101, "username": "alice"}]}
        ).encode()
    if url.endswith("/lookup?id=102"):
        return 200, json.dumps(
            {"status": "ok", "count": 1, "results": [{"id": 102, "username": "bob"}]}
        ).encode()
    if "/lookup?id=" in url:
        # Seeded random ids: unknown accounts return an empty result set
        # (vulnerable fixtures return 500/200-with-rows; both fail the property).
        return 200, json.dumps({"status": "ok", "count": 0, "results": []}).encode()
    return 404, b"{}"


def _php_ok(url: str):
    assert "/?host=" in url
    host = url.rsplit("=", 1)[-1]
    assert host in ("localhost", "127.0.0.1")
    return 200, json.dumps({"status": "ok", "host": host, "diagnostic": host}).encode()


def _mysql_ok(url: str):
    assert url.endswith("/my.cnf")
    return 200, b"[mysqld]\nport = 3306\nmax_connections = 100\n"


def test_node_properties_pass_on_healthy_service():
    script = project_property_script("node_eval_service")
    assert _run_script(script, _node_ok) == 0


def test_node_properties_fail_on_broken_service():
    script = project_property_script("node_eval_service")

    def broken(url: str):
        if "/lookup?id=" in url and not url.endswith(("101", "102")):
            return 200, json.dumps({"status": "ok", "count": 5, "results": [{"id": 1}]}).encode()
        return _node_ok(url)

    assert _run_script(script, broken) == 1


def test_php_properties_pass_and_repeat_stably():
    script = project_property_script("php_command_sink")
    assert _run_script(script, _php_ok) == 0


def test_php_properties_fail_on_injected_host():
    script = project_property_script("php_command_sink")

    def broken(url: str):
        status, body = _php_ok(url)
        payload = json.loads(body)
        payload["diagnostic"] = "tampered"
        return status, json.dumps(payload).encode()

    assert _run_script(script, broken) == 1


def test_mysql_properties_pass_on_reread():
    script = project_property_script("mysql_config_audit")
    assert _run_script(script, _mysql_ok) == 0


def test_mysql_properties_fail_on_missing_key():
    script = project_property_script("mysql_config_audit")

    def broken(url: str):
        return 200, b"[mysqld]\nport = 3306\n"

    assert _run_script(script, broken) == 1


def test_unknown_fixture_script_is_inconclusive():
    script = project_property_script("no_such_fixture")
    assert _run_script(script, lambda url: (200, b"{}")) == 2


def _verification(properties_exit: int | None) -> SnapshotVerification:
    return SnapshotVerification(
        probe=ExecutionEvidence(exit_code=1, output="blocked"),
        regression=ExecutionEvidence(exit_code=0, output="regression ok"),
        properties=None
        if properties_exit is None
        else ExecutionEvidence(exit_code=properties_exit, output="properties"),
    )


@pytest.mark.parametrize("fixture", ["node_eval_service", "php_command_sink", "mysql_config_audit"])
def test_property_scripts_are_bounded_and_explicit_exit(fixture):
    script = project_property_script(fixture)
    assert len(script) < 16_384
    assert "sys.exit(0" in script and "sys.exit(1" in script and "sys.exit(2" in script


def test_property_gate_truth_table_is_fail_closed():
    assert property_gate_passed(_verification(0)) is True
    assert property_gate_passed(_verification(1)) is False
    assert property_gate_passed(_verification(2)) is False
    assert property_gate_passed(_verification(None)) is True


async def test_property_failure_rolls_back_verified_patch():
    """Fail-first: blocked probe + green regression still rolls back on properties 1."""
    from helpers import (
        FakeProjectMuse as FakeMuse,
    )
    from helpers import (
        FakeProjectSandbox as FakeSandbox,
    )
    from helpers import (
        run_project_workflow as run_workflow,
    )

    def verification_with_properties(probe: int, regression: int, properties: int | None):
        from project_workflow import ExecutionEvidence, SnapshotVerification

        return SnapshotVerification(
            probe=ExecutionEvidence(exit_code=probe, output="evidence"),
            regression=ExecutionEvidence(exit_code=regression, output="regression"),
            fresh_target=True,
            properties=None
            if properties is None
            else ExecutionEvidence(exit_code=properties, output="properties"),
        )

    muse = FakeMuse(red_outcomes=["finding", "no_finding"])
    sandbox = FakeSandbox(
        [
            verification_with_properties(1, 0, 0),
            verification_with_properties(0, 0, 0),
            # patched snapshot: probe blocked + regression green, properties failed.
            verification_with_properties(1, 0, 1),
        ]
    )
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert result.cycle_reports[0].status == "rolled_back"
    assert result.cycle_reports[0].evidence.patched_verification.properties.exit_code == 1


async def test_docker_sandbox_attaches_property_evidence(tmp_path):
    """DockerProjectSandbox runs the property script after regression green."""
    from helpers import TEST_CONFIG as CONFIG

    from docker_manager import ProjectCheckResult
    from project_workflow import DockerProjectSandbox
    from projects import ProjectSpec, snapshot_project

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
        label="properties-plumbing",
    )
    assert result.properties is not None
    assert result.properties.exit_code == 0
    assert len(scripts) == 2
    assert "Property checks passed" in scripts[1]
