# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Dashboard navigation and harness migration contracts."""

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_browser_bootstrap_imports_current_modules():
    spec = importlib.util.spec_from_file_location("ui_scan", ROOT / ".jcode/tools/ui_scan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.OFFLINE_SERVER.format(root=str(ROOT), tools=str(ROOT / ".jcode/tools"), port=8797)
    # Execute only imports, not the server or its patching, against the real modules.
    imports = [n for n in ast.parse(code).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    imports = [
        n for n in imports if not isinstance(n, ast.ImportFrom) or n.module != "offline_scan"
    ]
    exec(compile(ast.Module(body=imports, type_ignores=[]), "bootstrap", "exec"), {})


def test_workspace_has_real_section_navigation_and_accessible_logs():
    from html.parser import HTMLParser

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.nodes = []

        def handle_starttag(self, tag, attrs):
            self.nodes.append((tag, dict(attrs)))

    parser = Elements()
    parser.feed((ROOT / "static/index.html").read_text())
    ids = [attrs["id"] for _, attrs in parser.nodes if "id" in attrs]
    assert len(ids) == len(set(ids))
    links = [attrs["href"] for tag, attrs in parser.nodes if tag == "a"]
    for section in ("configure", "pipeline-title", "agent-traces", "telemetry-title"):
        assert f"#{section}" in links
        assert section in ids
    for log in ("red-log", "blue-log", "sys-log", "comms-log"):
        attrs = next(attrs for _, attrs in parser.nodes if attrs.get("id") == log)
        assert attrs["tabindex"] == "0"
        assert attrs["role"] == "log"
