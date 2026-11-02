# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""WebUI v3 contracts for the guidance layer (page chain, engine, scoreboard, run options).

v2 was a single-shell hash router (``static/index.html`` with ``#/demo`` /
``#/live`` routes, ``static/graph.js`` SMSGraph, ``hud-toggle-*`` ids). v3 is
a multi-page flow under ``web/`` (start -> setup -> visual) with the
``SMS.*`` kit modules, a canvas ``#graph``, a ``dl`` scoreboard, and run
options driven by ``web/js/options/schema.js``. These tests pin the v3
surface. Each fails if its anchor is removed (LAW 9B: sharp assertions).
"""

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def _nodes(path: Path):
    parser = Elements()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.nodes


def _ids(path: Path):
    return [attrs["id"] for _, attrs in _nodes(path) if "id" in attrs]


def _links(path: Path):
    return [attrs["href"] for tag, attrs in _nodes(path) if tag == "a" and "href" in attrs]


# --- Subsystem A: multi-page chain (start -> setup -> visual) ---


def test_start_cards_link_to_setup_pages():
    """Start cards navigate to the setup pages, not hash routes."""
    links = _links(WEB / "index.html")
    assert "demo-setup.html" in links, "demo card link missing"
    assert "prod-setup.html" in links, "production card link missing"
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "#/demo" not in html and "#/live" not in html, "v2 hash routes must not survive in v3 start page"


def test_setup_launch_saves_handoff_to_visual_page():
    """Setup Launch/Start persists the run via SMS.launch and navigates to the visual page."""
    prod = (WEB / "js" / "pages" / "setup-prod.js").read_text(encoding="utf-8")
    assert "L.save(" in prod, "prod setup must persist the launch via SMS.launch.save"
    assert "location.href = 'console.html'" in prod, "prod Launch must navigate to console.html"
    demo = (WEB / "js" / "pages" / "setup-demo.js").read_text(encoding="utf-8")
    assert "L.save(" in demo, "demo setup must persist the launch via SMS.launch.save"
    assert "location.href = 'demo.html'" in demo, "demo Start must navigate to demo.html"


# --- Subsystem B: SpiderGraph engine (canvas #graph + SMS kit) ---


def test_engine_kit_and_graph_modules_exist():
    """The v3 engine ships the shared kit plus the SpiderGraph module."""
    assert (WEB / "js" / "engine" / "kit.js").read_text(encoding="utf-8").count("SMS.engine") >= 1
    graph = (WEB / "js" / "engine" / "graph.js").read_text(encoding="utf-8")
    assert "SpiderGraph" in graph, "engine/graph.js must define SpiderGraph"
    assert "SMS.SpiderGraph" in graph, "SpiderGraph must publish on the SMS namespace"


def test_graph_mount_and_team_language_wired():
    """Canvas mount exists on the visual pages; team color language present in the palette."""
    assert "graph" in _ids(WEB / "console.html"), "#graph canvas missing on console.html"
    assert "graph" in _ids(WEB / "demo.html"), "#graph canvas missing on demo.html"
    console = (WEB / "console.html").read_text(encoding="utf-8")
    assert "js/engine/graph.js" in console, "console.html must load the engine graph module"
    palette = (WEB / "js" / "core" / "palette.js").read_text(encoding="utf-8")
    for token in ("red", "blue", "purple", "green", "yellow", "orange"):
        assert token in palette.lower(), f"team color token {token!r} missing from palette.js"


def test_timeline_strip_remains_as_fallback():
    """The log-derived timeline marker strip stays mounted beside the canvas map."""
    assert "timeline" in _ids(WEB / "console.html"), "#timeline strip missing on console.html"
    activity = (WEB / "js" / "ui" / "activity.js").read_text(encoding="utf-8")
    assert "Timeline" in activity, "activity.js must define the Timeline marker strip"


# --- Subsystem C: session scoreboard + schema-driven run options ---


def test_scoreboard_aggregates_session_telemetry():
    """Header scoreboard (dl#c-score) carries Messages/Findings/Patches/Verified aggregates."""
    nodes = _nodes(WEB / "console.html")
    boards = [
        (tag, attrs)
        for tag, attrs in nodes
        if tag == "dl" and attrs.get("aria-label") == "Session scoreboard"
    ]
    assert boards, "scoreboard dl[aria-label='Session scoreboard'] missing"
    assert any("c-score" in attrs.get("class", "") for _, attrs in boards)
    ids = _ids(WEB / "console.html")
    for slot in ("sc-msgs", "sc-find", "sc-patch", "sc-ver", "sc-time"):
        assert slot in ids, f"#{slot} missing from the session scoreboard"


def test_schema_fields_cover_backend_capability_families():
    """Run-options schema FIELDS cover the backend capability families."""
    schema = (WEB / "js" / "options" / "schema.js").read_text(encoding="utf-8")
    for field in (
        "sweep_passes:",
        "scan_profile:",
        "research:",
        "research_scanners:",
        "binary:",
        "ingest_repo:",
    ):
        assert field in schema, f"schema field {field!r} missing (capability family uncovered)"
    # ORPHAN (narrowed 2026-11-02): v3 has NO hud-toggle-compression /
    # hud-toggle-vault / hud-toggle-differential surface. Compression and
    # vault-recall render as result facts when the payload carries them
    # (result-view.js ``Compression``/``Vault recall``), and differential
    # wording lives in the stream narration (narrator.js); none of the
    # three is a schema toggle. Do NOT add a schema field to satisfy this.
    lowered = schema.lower()
    assert "compression" not in lowered.replace("comp(", "x"), "compression must stay a payload fact, not a schema field"
    assert "differential" not in lowered, "differential must stay narration-only, not a schema field"


def test_terminal_semantics_preserved_csp_safe():
    """Comms + activity logs keep role=log; no inline handlers anywhere in v3 pages."""
    for page in ("console.html", "demo.html"):
        nodes = _nodes(WEB / page)
        by_id = {attrs["id"]: (tag, attrs) for tag, attrs in nodes if "id" in attrs}
        assert "comms" in by_id, f"#comms missing on {page}"
        assert by_id["comms"][1].get("role") == "log", f"#comms on {page} must keep role=log"
        html = (WEB / page).read_text(encoding="utf-8")
        assert "onclick" not in html and "onchange" not in html, f"no inline handlers on {page} (CSP)"
    by_id = {attrs["id"]: (tag, attrs) for tag, attrs in _nodes(WEB / "console.html") if "id" in attrs}
    assert "log" in by_id, "#log activity pane missing on console.html"
    assert by_id["log"][1].get("role") == "log", "#log must keep role=log"
    assert by_id["log"][1].get("tabindex") == "0", "#log must stay focusable"
    assert "term" in _ids(WEB / "demo.html"), "#term stdout stream missing on demo.html (demo-only)"


# --- Docs parity (LAW 5): README describes the v3 page flow; reference maps the layers ---


def test_readme_describes_v3_page_flow():
    """README guides Start -> setup -> console/demo; stale v2 hash routes are gone."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for marker in ("prod-setup.html", "demo-setup.html", "console.html", "scoreboard", "stagebar"):
        assert marker in text, f"README missing {marker!r}"
    assert "#/demo" not in text and "#/live" not in text, "stale v2 hash routes must not survive in README"


def test_dashboard_reference_covers_v3_guidance_layer():
    """DASHBOARD.md maps web/js/pages, the stagebar, and the CommsFeed."""
    text = (ROOT / "docs" / "reference" / "DASHBOARD.md").read_text(encoding="utf-8")
    for marker in ("web/js/pages", "stagebar", "CommsFeed"):
        assert marker in text, f"DASHBOARD.md missing {marker!r}"
