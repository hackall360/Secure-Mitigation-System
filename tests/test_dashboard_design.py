# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Dashboard navigation and harness migration contracts (v3-only)."""

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


def _elements(page):
    from html.parser import HTMLParser

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.nodes = []

        def handle_starttag(self, tag, attrs):
            self.nodes.append((tag, dict(attrs)))

        def handle_data(self, data):
            if self.nodes:
                tag, attrs = self.nodes[-1]
                attrs["_text"] = attrs.get("_text", "") + data

    parser = Elements()
    parser.feed((ROOT / "web" / page).read_text())
    return parser.nodes


def test_workspace_has_real_section_navigation_and_accessible_logs():
    nodes = _elements("console.html")
    ids = [attrs["id"] for _, attrs in nodes if "id" in attrs]
    assert len(ids) == len(set(ids))
    # Section rail + tabs navigate the workspace.
    tabs = [attrs["id"] for _, attrs in nodes if attrs.get("role") == "tab"]
    for tab in ("tab-comms", "tab-log", "tab-result"):
        assert tab in tabs
    for pane in ("pane-comms", "pane-log", "pane-result"):
        assert pane in ids
    # Stream panes are live regions, focusable and labelled.
    for log in ("comms", "log"):
        attrs = next(attrs for _, attrs in nodes if attrs.get("id") == log)
        assert attrs["role"] == "log"
        assert attrs["tabindex"] == "0"


def test_pass_state_renders_in_scoreboard_summary():
    """Sweep pass state renders in the run-summary sheet next to the verdict."""
    js = (ROOT / "web/js/ui/result-view.js").read_text()
    assert "pass_results" in js
    assert "passes hold" in js
    schema = (ROOT / "web/js/options/schema.js").read_text()
    assert "sweep_passes" in schema
    assert "+ threat-actor pass" in schema


def test_app_js_updates_pass_chip_on_sweep_lines():
    """Scoreboard verdict sheet renders per-pass hold counts from pass_results."""
    js = (ROOT / "web/js/ui/result-view.js").read_text()
    assert "pass_results" in js
    assert "passes hold" in js
    schema = (ROOT / "web/js/options/schema.js").read_text()
    assert "sweep_passes" in schema
    assert "threat-actor" in schema


def test_app_js_directs_binary_fixture_to_binary_mode():
    """binary_argv_echo in fixture mode shows the ELF badge and binary lens."""
    demo = (ROOT / "web/js/pages/setup-demo.js").read_text()
    assert "binary_argv_echo" in demo
    assert "ELF" in demo
    prod = (ROOT / "web/js/pages/setup-prod.js").read_text()
    assert "binary_argv_echo" in prod and "ELF" in prod
