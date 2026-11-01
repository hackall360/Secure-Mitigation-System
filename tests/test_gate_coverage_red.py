# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED: pin L1 gate holes in `.jcode/tools/dev.py check()`.

Each test below pins one hole: (a) check() must invoke the `dev.py tags`
feature-tag coverage, (b) `node --check` must cover every `web/js/**/*.js`
file (not just static/app.js + the fixture), (c) ruff check+format must
cover `web/tools/` (no pyproject exclusion, vendored script itself clean),
(d) the `test_harness.py` Docker-path skip must be explicit in check()
(never --docker implicitly) and logged with its opt-in pointer.
"""

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / ".jcode" / "tools" / "dev.py"


@pytest.fixture
def gate():
    """Load dev.py hermetically: python()/run() recorded, tags() observed."""
    spec = importlib.util.spec_from_file_location("gate_dev_l1", DEV)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    python_calls, run_calls = [], []
    module.python = lambda *a: python_calls.append(a)
    module.run = lambda *a: run_calls.append(a)
    tags_mock = Mock()
    module.tags = tags_mock
    return module, python_calls, run_calls, tags_mock


def node_checked(run_calls):
    return [c[2] for c in run_calls if c[:2] == ("node", "--check")]


def test_check_invokes_feature_tag_coverage(gate):
    module, _, _, tags_mock = gate
    module.check()
    assert tags_mock.call_count == 1, "check() must invoke dev.py tags coverage"


def test_check_node_checks_every_web_js(gate):
    module, _, run_calls, _ = gate
    module.check()
    checked = set(node_checked(run_calls))
    expected = {"static/app.js", "targets/node_query_sink/app.js"}
    expected |= {str(p.relative_to(ROOT)) for p in (ROOT / "web/js").rglob("*.js")}
    assert expected, "web/js glob must not be empty"
    missing = expected - checked
    assert not missing, f"node --check missing {len(missing)} files: {sorted(missing)[:5]}"


def test_ruff_covers_web_tools(gate):
    module, python_calls, _, _ = gate
    module.check()
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    excluded = config.get("tool", {}).get("ruff", {}).get("exclude", [])
    assert not any("web/tools" in e for e in excluded), (
        f"pyproject still excludes web/tools: {excluded}"
    )
    probe = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "web/tools/sync_assets.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, f"web/tools not ruff-clean:\n{probe.stdout}"
    probe_fmt = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "web/tools/sync_assets.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert probe_fmt.returncode == 0, f"web/tools not format-clean:\n{probe_fmt.stdout}"
    ruff_calls = [c for c in python_calls if c[0:2] == ("-m", "ruff")]
    assert any("." in c for c in ruff_calls), "check() must run ruff over repo root"


def test_docker_skip_explicit_and_logged(gate, capsys):
    module, python_calls, _, _ = gate
    module.check()
    harness_calls = [c for c in python_calls if c[-1] == "test_harness.py"]
    assert harness_calls, "check() must still run test_harness.py"
    for call in harness_calls:
        assert "--docker" not in call and "--api" not in call, "gate must never go live implicitly"
    out = capsys.readouterr().out.lower()
    assert "docker" in out and "skip" in out, "check() must log the Docker-path skip explicitly"
    bare = subprocess.run(
        [sys.executable, "test_harness.py"], cwd=ROOT, capture_output=True, text=True
    )
    assert bare.returncode == 0
    assert "skip" in bare.stdout.lower() and "--docker" in bare.stdout, (
        "bare harness must log its SKIP with the opt-in flag"
    )
    help_text = subprocess.run(
        [sys.executable, "test_harness.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    assert "--docker" in help_text, "--help must document the Docker opt-in"
