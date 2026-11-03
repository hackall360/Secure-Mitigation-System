#!/usr/bin/env python3
# Measure stdlib-trace line coverage of one pytest target set over library/ (no new deps).

"""Usage: verify_cov.py <pytest-args...> -- run pytest under sys.monitoring,
print per-file line-coverage for library/main/tui/sms_cli/docker, list the
lowest-coverage files (gap-test targets), exit 1 if any file < THRESHOLD."""

import ast
import json
import subprocess
import sys
from pathlib import Path

THRESHOLD = (
    float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].replace(".", "").isdigit() else 0.0
)
PYTEST_ARGS = [
    a for a in sys.argv[1:] if not (a.replace(".", "").isdigit() and float(a) == THRESHOLD)
]

TRACER = """
import sys
_cov = {}
def _handler(code, line):
    _cov.setdefault(code.co_filename, set()).add(line)
    return sys.monitoring.DISABLE
sys.monitoring.use_tool_id(3, "verifycov")
sys.monitoring.register_callback(3, sys.monitoring.events.LINE, _handler)
sys.monitoring.set_events(3, sys.monitoring.events.LINE)
import json, atexit
atexit.register(lambda: open("/tmp/verify_cov.json", "w").write(json.dumps({k: sorted(v) for k, v in _cov.items() if "/repo" in k or "/Secure-Mitigation" in k})))
"""

r = subprocess.run(
    [sys.executable, "-c", TRACER + "import pytest,sys;sys.exit(pytest.main(%r))" % (PYTEST_ARGS,)],
    capture_output=True,
    text=True,
)
print(r.stdout[-2000:])
print(r.stderr[-1000:], file=sys.stderr)

try:
    cov = json.load(open("/tmp/verify_cov.json"))
except FileNotFoundError:
    print("no coverage data collected")
    sys.exit(2)

ROOT = Path(".").resolve()
gaps = []
for fname, lines in sorted(cov.items()):
    try:
        rel = str(Path(fname).resolve().relative_to(ROOT))
    except ValueError:
        continue
    if not (rel.startswith(("library/", "main.py", "tui.py", "sms_cli.py", "docker/"))):
        continue
    if "__pycache__" in rel:
        continue
    try:
        tree = ast.parse(Path(fname).read_text())
    except Exception:
        continue
    code_lines = {n.lineno for n in ast.walk(tree) if isinstance(n, (ast.stmt,))} - {
        n.lineno
        for n in ast.walk(tree)
        if isinstance(n, (ast.Expr,)) and isinstance(getattr(n, "value", None), (ast.Constant,))
    }
    code_lines = {ln for ln in code_lines if ln}
    hit = set(lines) & code_lines
    pct = 100.0 * len(hit) / len(code_lines) if code_lines else 100.0
    if pct < 100.0:
        gaps.append((pct, rel, len(code_lines - hit)))
gaps.sort()
print(f"\nfiles with <100% line coverage: {len(gaps)}")
for pct, rel, missing in gaps[:40]:
    print(f"  {pct:5.1f}%  {rel}  ({missing} lines missed)")
below = [g for g in gaps if g[0] < THRESHOLD]
if below:
    print(f"\n{len(below)} files below threshold {THRESHOLD}%")
    sys.exit(1)
sys.exit(r.returncode)
