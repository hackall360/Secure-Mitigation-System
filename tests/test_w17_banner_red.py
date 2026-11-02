# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""v3 error-surface contract: cfg-errors + toast + chip-key (tribunal S3-7 render half, wave w17).

v2 pinned ``#scan-banner`` / ``showBanner`` / ``clearBanner`` /
``maybeShowBanner``. v3 has no banner element: error text routes to the
``#cfg-errors`` ``role=alert`` node (``hidden`` by default) plus a ``toast()``
notification, and ``chip-key`` flips to its ``warn`` state on key/connectivity
trouble. The next successful start clears ``#cfg-errors`` via ``errors([])``.

v2 distinguished rate-limit vs Docker copy in the banner filter. v3 narrows to
one generic equivalent: the ``onLine`` branch writes the offending message
(``/rate limit|429/`` or ``/docker daemon/``) into ``#cfg-errors`` — the
docstrings note where the per-cause copy lived in v2 and what v3 asserts
instead. LAW 9B: keep assertions sharp; each test fails if its anchor is
removed.
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


def _console_js() -> str:
    return (WEB / "js" / "pages" / "console.js").read_text(encoding="utf-8")


def test_error_node_exists_hidden_by_default():
    """``#cfg-errors`` (role=alert) sits in the run rail, hidden initially."""
    nodes = _nodes(WEB / "console.html")
    by_id = {attrs["id"]: (tag, attrs) for tag, attrs in nodes if "id" in attrs}
    assert "cfg-errors" in by_id, "#cfg-errors missing from console.html"
    tag, attrs = by_id["cfg-errors"]
    assert attrs.get("role") == "alert", "#cfg-errors must keep role=alert"
    assert "hidden" in attrs or attrs.get("hidden") == "", "#cfg-errors must start hidden"
    assert "setup" in by_id or "r-target" in by_id, "#cfg-errors must live in the run-rail context"
    # The setup pages carry the same surface for pre-launch validation errors.
    assert 'id="cfg-errors"' in (WEB / "prod-setup.html").read_text(encoding="utf-8")


def test_error_text_routes_to_toast_and_cfg_errors():
    """Error paths write the message to ``#cfg-errors`` and fire ``toast()``."""
    source = _console_js()
    assert "toast(" in source, "console.js must surface errors via toast()"
    assert "cfg-errors" in source, "console.js must write error text into #cfg-errors"
    assert "$('cfg-errors').textContent" in source, (
        "cfg-errors text must be assigned (textContent-only)"
    )
    onrefuse = source[source.index("onRefuse") :]
    assert "toast(" in onrefuse[:1200], (
        "refusal path must toast ('Server busy' / 'Request rejected')"
    )


def test_rate_limit_text_reaches_error_surface():
    """Stream text naming the rate limit reaches the error surface.

    v2 narrowing: ``maybeShowBanner`` branch-filtered on "rate limit" copy
    for a dedicated banner. v3 asserts the generic equivalent: the ``onLine``
    branch matches ``/rate limit|429/`` and writes the offending message via
    ``errors([msg])``.
    """
    source = _console_js()
    assert "rate limit" in source.lower().replace("-", " "), (
        "rate-limit wording missing from console.js"
    )
    assert "429" in source, "429 wording missing from console.js"
    branch = source[source.index("onLine(team, msg, payload)") :]
    branch = branch[: branch.index("if (graph.selected)")]
    assert "errors([msg])" in branch, "rate-limit branch must write the message via errors([msg])"


def test_docker_text_reaches_error_surface():
    """Stream text naming Docker trouble reaches the error surface.

    v2 narrowing: same as the rate-limit test — v2 banner copy distinguished
    Docker wording; v3 asserts the generic equivalent (``/docker daemon/``
    writes the message via ``errors([msg])``).
    """
    source = _console_js()
    assert "docker daemon" in source.lower(), "docker-daemon wording missing from console.js"
    branch = source[source.index("onLine(team, msg, payload)") :]
    branch = branch[: branch.index("if (graph.selected)")]
    assert "errors([msg])" in branch


def test_next_success_start_clears_errors():
    """A fresh start dismisses the error surface (``errors([])`` in ``start()``)."""
    source = _console_js()
    assert "function resetRun()" in source
    start = source[source.index("async function start()") :]
    start = start[: start.index("state.session = ")]
    assert "errors([])" in start, "start() must clear #cfg-errors before streaming"


def test_chip_key_turns_warn_on_key_trouble():
    """Live WS snapshot flips chip-key to the warn state when the key is missing."""
    source = _console_js()
    assert "chip-key" in source, "console.js must drive the chip-key readout"
    assert "'warn'" in source or '"warn"' in source, "chip-key warn state missing"
    snapshot = source[source.index("function onSnapshot") :]
    snapshot = snapshot[: snapshot.index("function onGraph")]
    assert "chip-key" in snapshot and "warn" in snapshot, "snapshot path must set chip-key to warn"
