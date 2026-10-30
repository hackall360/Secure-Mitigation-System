# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first contracts for the UI guidance-matrix upgrades (A/B/C).

LAW 9: these tests define the desired behavior BEFORE implementation. Each
fails for the expected functional reason (missing elements/APIs), not syntax.
Implementation must satisfy them without weakening assertions (LAW 9B).
"""

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def _parse_index():
    parser = Elements()
    parser.feed((ROOT / "static/index.html").read_text())
    return parser.nodes


def _ids(nodes):
    return [attrs["id"] for _, attrs in nodes if "id" in attrs]


def _links(nodes):
    return [attrs["href"] for tag, attrs in nodes if tag == "a" and "href" in attrs]


# --- Subsystem A: split routes (landing + #/demo + #/live, shared core) ---


def test_route_shell_has_landing_demo_live_links():
    """RED A: index.html exposes landing + #/demo + #/live navigation."""
    nodes = _parse_index()
    links = _links(nodes)
    assert "#/" in links, "landing route link #/ missing"
    assert "#/demo" in links, "demo route link #/demo missing"
    assert "#/live" in links, "live route link #/live missing"


def test_route_views_exist_with_shared_core_mounts():
    """RED A: demo/live views exist and keep the shared viz core mounts."""
    nodes = _parse_index()
    ids = _ids(nodes)
    assert "view-landing" in ids, "#view-landing missing"
    assert "view-demo" in ids, "#view-demo missing"
    assert "view-live" in ids, "#view-live missing"
    # Shared core is DRY: exactly one set of core mounts, not per-view clones.
    for mount in ("red-log", "blue-log", "sys-log", "scan-timeline", "pipeline"):
        assert ids.count(mount) == 1, f"shared core mount #{mount} must appear exactly once"


def test_app_js_hash_router_syncs_modes_to_routes():
    """RED A: app.js routes hash <-> source modes without duplicating the core."""
    js = (ROOT / "static/app.js").read_text()
    assert "#/demo" in js
    assert "#/live" in js
    assert "view-demo" in js
    assert "view-live" in js
    assert "hashchange" in js


# --- Subsystem B: cinematic force-directed graph engine ---


def test_graph_engine_file_exports_sms_graph_api():
    """RED B: static/graph.js exposes SMSGraph init/update/fallback."""
    path = ROOT / "static/graph.js"
    assert path.exists(), "static/graph.js missing"
    js = path.read_text()
    assert "SMSGraph" in js
    assert "init" in js
    assert "update" in js
    assert "isFallback" in js or "fallback" in js


def test_graph_mount_and_team_language_wired():
    """RED B: canvas mount exists; team color language + wiring present."""
    nodes = _parse_index()
    assert "phase-graph" in _ids(nodes), "#phase-graph canvas missing"
    graph_js = (ROOT / "static/graph.js").read_text()
    for token in ("probe", "patch", "verified", "green", "red", "blue", "purple"):
        assert token in graph_js.lower(), f"team language token {token!r} missing in graph.js"
    app_js = (ROOT / "static/app.js").read_text()
    assert "SMSGraph" in app_js, "app.js must feed events into SMSGraph"
    index_js = (ROOT / "static/index.html").read_text()
    assert "graph.js" in index_js, "index.html must load graph.js (CSP-safe, same-origin)"


def test_timeline_strip_remains_as_fallback():
    """RED B: the log-derived timeline strip stays as the degraded path."""
    nodes = _parse_index()
    assert "scan-timeline" in _ids(nodes)
    graph_js = (ROOT / "static/graph.js").read_text()
    assert "scan-timeline" in graph_js or "fallback" in graph_js.lower()


# --- Subsystem C: telemetry HUD + feature surfacing ---


def test_scoreboard_aggregates_session_telemetry():
    """RED C: header scoreboard with agents/vulns/patches/verified aggregates."""
    nodes = _parse_index()
    ids = _ids(nodes)
    assert "scoreboard" in ids, "#scoreboard missing"
    for slot in ("score-agents", "score-vulns", "score-patches", "score-verified"):
        assert slot in ids, f"#{slot} missing"


def test_hud_toggles_cover_backend_capabilities():
    """RED C: HUD toggles exist for every backend capability family."""
    nodes = _parse_index()
    ids = _ids(nodes)
    for toggle in (
        "hud-toggle-sweep",
        "hud-toggle-profile",
        "hud-toggle-research",
        "hud-toggle-compression",
        "hud-toggle-vault",
        "hud-toggle-differential",
        "hud-toggle-binary",
    ):
        assert toggle in ids, f"#{toggle} missing"


def test_terminal_semantics_preserved_csp_safe():
    """RED C: red/blue logs keep terminal semantics; no inline handlers."""
    nodes = _parse_index()
    by_id = {attrs["id"]: (tag, attrs) for tag, attrs in nodes if "id" in attrs}
    for log in ("red-log", "blue-log"):
        assert log in by_id, f"#{log} missing"
        tag, attrs = by_id[log]
        assert attrs.get("role") == "log", f"#{log} must keep role=log"
        assert attrs.get("tabindex") == "0", f"#{log} must stay focusable"
    html = (ROOT / "static/index.html").read_text()
    assert "onclick" not in html and "onchange" not in html, "no inline handlers (CSP)"
