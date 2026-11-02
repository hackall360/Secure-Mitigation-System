"""v3-only cutover: v3 is the site, v2 is gone, every web pin has a v3 home.

RED-first (ZZ): proves the cutover contract before implementation.
V3_HOME maps each web-surface tag to its real v3 equivalent:
(page-or-js, needle present in that file). The v2 flat-dashboard widgets
(panel bars, log panes, download buttons, setup boot) have no v3 counterpart
because the v3 engine/pages/console flow owns those jobs; their tags keep the
pin with surfaces narrowed to the non-web surface that still expresses them
(recorded in V3_GAP, asserted in test).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def _client():
    from main import create_app

    return create_app()


# tag -> (v3 file holding the equivalent, needle)
V3_HOME = {
    "scan-fixture": ("web/prod-setup.html", "launch"),
    "stop-scan": ("web/js/pages/console.js", "Session"),
    "ws-combat": ("web/js/options/schema.js", "/ws/combat"),
    "fixture-picker": ("web/js/pages/setup-prod.js", "c-fx"),
    "list-targets": ("web/js/stream/link.js", "/api/targets"),
    "health-report": ("web/js/stream/link.js", "/api/health"),
    "orchestrator-chip": ("web/console.html", "chip-server"),
    "api-key-chip": ("web/console.html", "chip-key"),
    "docker-status": ("web/console.html", "chip-docker"),
    "mode-switch": ("web/prod-setup.html", "data-mode"),
    "mode-demo-build": ("web/js/options/schema.js", "/ws/demo"),
    "mode-project": ("web/js/options/schema.js", "/ws/project"),
    "project-path": ("web/js/options/schema.js", "path:"),
    "project-image": ("web/js/options/schema.js", "image:"),
    "project-command": ("web/js/options/schema.js", "command:"),
    "project-test-command": ("web/js/options/schema.js", "test_command:"),
    "project-contract": ("web/js/options/schema.js", "contract:"),
    "scan-intensity": ("web/js/options/schema.js", "scan_profile"),
    "project-cycles": ("web/js/options/schema.js", "cycles:"),
    "red-team-size": ("web/js/options/schema.js", "red_agents"),
    "blue-team-size": ("web/js/options/schema.js", "blue_agents"),
    "context-budget": ("web/js/options/schema.js", "context_budget"),
    "allow-remote": ("web/js/options/schema.js", "allow_remote_inference"),
    "ws-project": ("web/js/options/schema.js", "/ws/project"),
    "demo-build-brief": ("web/js/options/schema.js", "build_brief"),
    "demo-vulns": ("web/js/options/schema.js", "vulns:"),
    "demo-theme": ("web/js/options/schema.js", "theme:"),
    "ws-demo": ("web/js/pages/setup-demo.js", "launch"),
    "green-build-run": ("web/js/pages/setup-demo.js", "launch"),
    "research-toggle": ("web/js/options/schema.js", "research:"),
    "research-scanners": ("web/js/options/schema.js", "research_scanners"),
    "model-profile": ("web/js/pages/setup-prod.js", "scanProfiles"),
    "output-format": ("web/js/stream/link.js", "download"),
    "output-dir": ("web/js/stream/link.js", "download"),
    "show-usage": ("web/js/ui/result-view.js", "r-usage"),
    "result-usage": ("web/js/ui/result-view.js", "r-usage"),
    "panel-comms": ("web/console.html", "comms"),
    "panel-result": ("web/console.html", "result"),
    "result-cycles": ("web/console.html", "r-cycles"),
    "result-diff": ("web/console.html", "r-diff"),
    "panel-telemetry": ("web/console.html", "comms"),
    "telemetry-filters": ("web/console.html", "filter"),
    "mcp-http": ("web/js/stream/link.js", "mcpSnippet"),
    "binary-target": ("web/js/options/schema.js", "/ws/binary"),
    "panel-pipeline": ("web/js/pages/console.js", "StageBar"),
    "panel-timeline": ("web/js/pages/console.js", "timeline"),
    "result-download": ("web/js/pages/console.js", "dl-json"),
    "result-download-patch": ("web/js/pages/console.js", "dl-patch"),
    "result-copy-diff": ("web/js/pages/console.js", "cp-diff"),
    "result-facts": ("web/js/ui/result-view.js", "fact("),
    "project-errors": ("web/prod-setup.html", "cfg-errors"),
    "target-description": ("web/js/pages/setup-demo.js", "description"),
    "run-setup": ("web/js/pages/console.js", "probe"),
}

# v2-only widgets with no v3 counterpart: tag -> surviving non-web surfaces.
# The legend filter + roster agents live in the v3 engine canvas (palette.js /
# legend.js filter the SpiderGraph, not DOM log panes), so these pins move to
# the surfaces that still express them as text: the WS stream (api) and TUI.
V3_GAP = {
    "panel-red": ["tui", "api"],
    "panel-blue": ["tui", "api"],
    "panel-arena": ["api"],
    "panel-arena-blue": ["api"],
    "panel-arena-green": ["api"],
}


def test_v2_retired_from_routes_and_disk():
    assert not (ROOT / "static").exists(), "static/ v2 still on disk"
    with TestClient(_client(), base_url="http://localhost") as client:
        assert client.get("/v2/", follow_redirects=False).status_code == 404
        assert client.get("/static/app.js", follow_redirects=False).status_code == 404
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 307 and resp.headers["location"] == "/web/index.html"


def test_every_web_pin_has_a_v3_home():
    missing = [
        f"{tag}: {needle!r} not in {path}"
        for tag, (path, needle) in V3_HOME.items()
        if needle not in (ROOT / path).read_text()
    ]
    assert missing == [], "\n".join(missing)


def test_registry_web_bindings_point_at_v3():
    import re

    tags_src = (ROOT / "library/tags.py").read_text()
    assert "static/app.js" not in tags_src, "registry still pins v2 backends"
    assert 'root / "static"' not in tags_src, "checker still searches static/"
    assert re.search(r'root / "web"', tags_src), "checker must search web/"
    for tag, surfaces in V3_GAP.items():
        m = re.search(rf'"{tag}": \{{[^}}]*?"surfaces": (\[[^\]]*\])', tags_src, re.S)
        assert m, f"{tag} entry missing"
        assert json.loads(m.group(1)) == surfaces, f"{tag} surfaces must be {surfaces}"
    for tag in V3_HOME:
        m = re.search(rf'"{tag}": \{{[^}}]*?"surfaces": (\[[^\]]*\])', tags_src, re.S)
        assert m and "web" in json.loads(m.group(1)), f"{tag} lost its web surface"
