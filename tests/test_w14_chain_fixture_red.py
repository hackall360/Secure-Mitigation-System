# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): two-link chain fixture proving the chain pass flips what single-step misses.

Tribunal 2b-3 gap: the chain sweep pass exists in modules/workflows/sweep.py
(ChainLink, SweepPassResult.chain_links) but no bundled fixture exercises it —
single-step probes on every current fixture reach their sink directly, so the
chain verdict never flips. This test pins the new `node_chain_link` fixture
contract BEFORE the fixture exists:

- registry lists it (Target row mirroring node_query_sink shape);
- normal-input checks pass (benign role + benign lookup, 404 route intact);
- single-step probe (Link B alone, unprivileged) exits 1 — BLOCKED;
- chained probe (Link A grants role, then Link B expression) exits 0 pre-patch
  — boundary reached ONLY through the chain;
- chained probe exits 1 post-patch — blue patch guards BOTH links;
- blue patch passes the conservative patches.py guard (small diff, protected
  lines preserved, both mutable prefixes touched).

Benign boundary markers only (mirror test_harness.diagnostic_script style):
role=viewer with magic grant param, expression quote that errors 500 on the
unguarded expression path. No live key, no real Docker/Muse here: stub HTTP
handlers (mirror tests/test_property_checks.py _run_script) for the contract
checks plus FakeFixtureSandbox scripted exits for the sweep-verdict shape.
Docker proof happens in the GREEN follow-up (offline_scan + ui_scan).
"""

import json
import urllib.error

import pytest

from modules.core.checks import normal_behavior_script
from modules.core.patches import PatchRejected
from modules.core.registry import TARGETS_REGISTRY

FIXTURE = "node_chain_link"


def _run_script(script: str, handler) -> int:
    """Execute a generated check script with a stubbed HTTP layer (no network)."""
    import io
    import types
    import urllib.request as request_module

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
        status, body = handler(url)
        if status != 200:
            raise urllib.error.HTTPError(url, status, "stubbed", {}, io.BytesIO(body))
        return FakeResponse(status, body)

    namespace = {
        "urllib": types.SimpleNamespace(request=types.SimpleNamespace(urlopen=fake_urlopen)),
        "__name__": "chain_probe",
    }
    original = request_module.urlopen
    request_module.urlopen = fake_urlopen
    try:
        try:
            exec(compile(script, "chain_check.py", "exec"), namespace)
        except SystemExit as exit:
            return int(exit.code)
    finally:
        request_module.urlopen = original
    raise AssertionError("chain script must call sys.exit")


def _healthy(url: str):
    """Stubbed healthy fixture: privileged grant lookups 200, rest gated."""
    import urllib.parse

    grant = urllib.parse.quote("grant:reviewer", safe="")
    if url.endswith(f"/lookup?role=reviewer&grant={grant}&id=101") and "id=10000" not in url:
        return 200, json.dumps(
            {
                "status": "ok",
                "count": 1,
                "results": [{"id": 101, "username": "alice", "role": "user"}],
            }
        ).encode()
    if url.endswith(f"/lookup?role=reviewer&grant={grant}&id=102") and "id=10000" not in url:
        return 200, json.dumps(
            {
                "status": "ok",
                "count": 1,
                "results": [{"id": 102, "username": "bob", "role": "admin"}],
            }
        ).encode()
    if f"/lookup?role=reviewer&grant={grant}&id=" in url and ("id=999" in url or "id=10000" in url):
        return 200, json.dumps({"status": "ok", "count": 0, "results": []}).encode()
    if url.endswith("/lookup?role=viewer&id=101"):
        return 400, b"{}"
    if url.endswith("/unknown"):
        return 404, b'{"status": "not_found"}'
    raise AssertionError("unexpected normal-input path: " + url)


def test_registry_lists_chain_fixture():
    """Registry carries the two-link chain fixture row."""
    assert FIXTURE in TARGETS_REGISTRY
    target = TARGETS_REGISTRY[FIXTURE]
    assert target.filename == "app.js"
    assert target.command == ("node", "/workspace/app.js")
    assert "role" in target.contract.lower()


def test_normal_behavior_checks_cover_both_links():
    """Trusted normal-input script passes on the guarded fixture shape."""
    script = normal_behavior_script(FIXTURE)
    assert "grant" in script and "role=viewer" in script
    assert _run_script(script, _healthy) == 0


def _single_step_probe_script() -> str:
    """Benign marker: Link B expression alone, unprivileged role (must exit 1)."""
    return r"""
import sys
import urllib.error
import urllib.request

try:
    with urllib.request.urlopen(
        'http://target-service:8080/lookup?role=viewer&id=%27', timeout=3
    ) as response:
        status, body = response.status, response.read(65537).decode()
except urllib.error.HTTPError as error:
    status, body = error.code, error.read(65537).decode()
if status == 400:
    print('Single-step expression blocked without privilege (exit 1)')
    sys.exit(1)
print('Single-step expression reached the sink (exit 0)')
sys.exit(0)
"""


def _chained_probe_script() -> str:
    """Benign marker: Link A magic grant, then Link B expression (exit 0 pre-patch)."""
    return r"""
import sys
import urllib.error
import urllib.parse
import urllib.request

grant = urllib.parse.quote('grant:reviewer', safe='')
try:
    with urllib.request.urlopen(
        'http://target-service:8080/lookup?role=viewer&grant=' + grant
        + '&id=%27', timeout=3
    ) as response:
        status, body = response.status, response.read(65537).decode()
except urllib.error.HTTPError as error:
    status, body = error.code, error.read(65537).decode()
if status == 400:
    print('Chained probe blocked (exit 1)')
    sys.exit(1)
if status == 500 and 'error' in body:
    print('Chained probe reached the dynamic expression through the granted role (exit 0)')
    sys.exit(0)
print('Chained probe inconclusive')
sys.exit(2)
"""


def _chain_handler(*, patched: bool):
    def handler(url: str):
        if "grant" in url and "%27" in url:
            if patched:
                return 400, b'{"status": "error"}'
            return 500, b'{"status": "error", "detail": "parse"}'
        if "%27" in url:
            return 400, b'{"status": "error"}'
        return _healthy(url)

    return handler


def test_single_step_probe_blocked():
    """Link B alone (unprivileged) exits 1: single-step misses the boundary."""
    assert _run_script(_single_step_probe_script(), _chain_handler(patched=False)) == 1


def test_chained_probe_reaches_sink_pre_patch():
    """Chained probe (A grants role, B feeds expression) exits 0 pre-patch."""
    assert _run_script(_chained_probe_script(), _chain_handler(patched=False)) == 0


def test_chained_probe_blocked_post_patch():
    """Chained probe exits 1 post-patch: blue guards BOTH links."""
    assert _run_script(_chained_probe_script(), _chain_handler(patched=True)) == 1


def test_chain_verdict_flips_what_single_step_misses():
    """The chain-pass verdict shape flips: single holds, chained fails pre-patch."""
    from modules.workflows.sweep import ChainLink, SweepPassResult

    single = SweepPassResult(
        pass_id="standard",
        chain_links=[
            ChainLink(pre_exit=1, post_exit=1),
            ChainLink(pre_exit=1, post_exit=1),
        ],
        regression_passed=True,
        receipt={"chain": [(1, 1), (1, 1)]},
    )
    assert single.holds is True
    chained_pre = SweepPassResult(
        pass_id="chain",
        chain_links=[
            ChainLink(pre_exit=0, post_exit=0),
            ChainLink(pre_exit=0, post_exit=0),
        ],
        regression_passed=True,
        receipt={"chain": [(0, 0), (0, 0)]},
    )
    assert chained_pre.holds is False
    chained_post = SweepPassResult(
        pass_id="chain",
        chain_links=[
            ChainLink(pre_exit=0, post_exit=1),
            ChainLink(pre_exit=0, post_exit=1),
        ],
        regression_passed=True,
        receipt={"chain": [(0, 1), (0, 1)]},
    )
    assert chained_post.holds is True


def test_blue_patch_shape_guards_both_links():
    """Patch replaces both mutable prefixes, keeps protected lines, under budget."""
    from modules.core.patches import validate_patch

    target = TARGETS_REGISTRY[FIXTURE]
    source = target.read_source()
    assert "const rawRole =" in source and "const queryExpression =" in source
    patched = source.replace(
        "        const rawRole =",
        "        if (!/^(viewer|editor)$/.test(String(parsedUrl.query.role || 'viewer'))) {\n"
        "            res.writeHead(400, { 'Content-Type': 'application/json' });\n"
        "            res.end(JSON.stringify({ status: 'error', detail: 'Invalid role' }));\n"
        "            return;\n"
        "        }\n"
        "        const rawRole =",
    ).replace(
        "        const queryExpression =",
        "        if (typeof rawUserId !== 'string' || !/^[0-9]+$/.test(rawUserId)) {\n"
        "            res.writeHead(400, { 'Content-Type': 'application/json' });\n"
        "            res.end(JSON.stringify({ status: 'error', detail: 'Invalid ID' }));\n"
        "            return;\n"
        "        }\n"
        "        const queryExpression =",
    )
    diff = validate_patch(target, source, patched)
    assert diff.startswith("--- a/node_chain_link/app.js")
    with pytest.raises(PatchRejected):
        validate_patch(target, source, source)


def test_harness_probe_shapes_match_fixture():
    """KnownMuse probe/patch shapes exist for the new fixture (offline scan ready)."""
    import test_harness

    target = TARGETS_REGISTRY[FIXTURE]
    source = target.read_source()
    patched = test_harness.known_patch(FIXTURE, source)
    assert patched != source
    script = test_harness.diagnostic_script(FIXTURE)
    assert "TARGET_VALUE" not in script and FIXTURE in script
    compile(script, "boundary_check.py", "exec")
    compile(normal_behavior_script(FIXTURE), "normal_check.py", "exec")
