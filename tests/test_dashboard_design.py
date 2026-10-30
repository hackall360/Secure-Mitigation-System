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


def test_pass_chip_present_in_scan_status_area():
    """RED: live pass chip renders next to the scan status element."""
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
    parser.feed((ROOT / "static/index.html").read_text())
    chip = next(
        (attrs for _, attrs in parser.nodes if attrs.get("id") == "pass-chip"),
        None,
    )
    assert chip is not None, "static/index.html must contain #pass-chip"
    assert "Pass" in chip.get("_text", "")
    status_index = next(
        i for i, (_, attrs) in enumerate(parser.nodes) if attrs.get("id") == "status"
    )
    chip_index = next(
        i for i, (_, attrs) in enumerate(parser.nodes) if attrs.get("id") == "pass-chip"
    )
    assert abs(chip_index - status_index) < 12


def test_app_js_updates_pass_chip_on_sweep_lines():
    """RED: app.js render path handles sweep pass start/done strings."""
    js = (ROOT / "static/app.js").read_text()
    assert "pass-chip" in js
    assert "sweep (standard|deep|threat_actor)" in js or "[sweep " in js
    assert "threat_actor" in js
    assert "Pass done" in js


def test_app_js_directs_binary_fixture_to_binary_mode():
    """RED: binary_argv_echo in demo/fixture mode shows Binary sweep notice."""
    js = (ROOT / "static/app.js").read_text()
    assert "binary_argv_echo" in js
    assert "Binary sweep mode" in js
