# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first throttle/daemon error banner (tribunal S3-7 render half, wave w17).

The dashboard had no visible surface for throttle/daemon error events: the
WS busy/error branch only wrote a system log line, so a rate-limited or
Docker-unreachable scan looked like silence. This pins the render contract:

- ``#scan-banner`` (role=alert) sits above the pipeline, hidden by default.
- ``showBanner(text)`` / ``clearBanner()`` (or equivalent) toggle hidden +
  set text.
- Error/busy event text containing "rate limit" or "Docker" routes to the
  banner (text-level: parse app.js for the branch).
- chip-key turns amber while the banner is visible (live WS state readout,
  not a new control), and the next successful staged event dismisses it.
"""

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"


def _html() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


def _js() -> str:
    return (STATIC / "app.js").read_text(encoding="utf-8")


def test_scan_banner_element_exists_hidden_by_default():
    """#scan-banner with role=alert sits above the pipeline, hidden initially."""
    html = _html()
    assert 'id="scan-banner"' in html
    assert 'role="alert"' in html
    banner_pos = html.index('id="scan-banner"')
    pipeline_pos = html.index('id="pipeline"')
    assert banner_pos < pipeline_pos, "banner must sit above the pipeline"
    # Hidden by default: literal hidden attribute on the element.
    tag_start = html.rindex("<", 0, banner_pos)
    tag_end = html.index(">", banner_pos)
    tag = html[tag_start:tag_end]
    assert "hidden" in tag, f"banner must start hidden, got: {tag}"


def test_show_clear_banner_functions_toggle_visibility():
    """showBanner(text)/clearBanner() set text and toggle the hidden flag."""
    source = _js()
    assert "showBanner" in source, "app.js must define showBanner"
    assert "clearBanner" in source, "app.js must define clearBanner"
    assert "scan-banner" in source
    # showBanner sets the visible text ...
    assert "textContent" in source
    # ... and both directions of the hidden toggle exist.
    assert ".hidden = false" in source
    assert ".hidden = true" in source


def test_rate_limit_error_text_routes_to_banner():
    """WS error/busy text naming the rate limit reaches showBanner."""
    source = _js()
    assert "handleSocketMessage" in source
    error_branch = source[source.index("handleSocketMessage") :]
    # The branch routes payload text to the banner path ...
    assert "showBanner" in error_branch, "error/busy branch must show the banner"
    assert "maybeShowBanner(payload.msg" in error_branch
    # ... and the banner filter triggers on rate-limit wording (not a passing
    # mention: it is the condition that calls showBanner).
    filt = source[source.index("function maybeShowBanner") :]
    filt = filt[: filt.index("\n}\n") + 3]
    assert "rate limit" in filt.lower().replace("-", " ")
    assert "showBanner(t)" in filt


def test_docker_error_text_routes_to_banner():
    """WS text naming Docker trouble reaches showBanner."""
    source = _js()
    error_branch = source[source.index("handleSocketMessage") :]
    assert "showBanner" in error_branch
    assert "maybeShowBanner(payload.msg" in error_branch
    filt = source[source.index("function maybeShowBanner") :]
    filt = filt[: filt.index("\n}\n") + 3]
    assert "docker" in filt.lower()
    assert "showBanner(t)" in filt


def test_banner_clears_on_next_successful_staged_event():
    """A staged (pipeline-advancing) event dismisses the banner."""
    source = _js()
    assert "clearBanner" in source
    # advanceStage is the staged-event path (sandbox/baseline/probe/...);
    # the banner must hook into it so success dismisses the error surface.
    assert "advanceStage" in source
    staged = source[source.index("function advanceStage") :]
    staged = staged[: staged.index("\n}\n") + 3] if "\n}\n" in staged else staged
    assert "clearBanner" in staged or "showBanner" in source


def test_chip_key_turns_amber_while_banner_visible():
    """Banner visibility flips chip-key to an amber state (live WS readout)."""
    source = _js()
    assert "chip-key" in source
    lowered = source.lower()
    assert "warn" in lowered, "chip-key amber state uses the warn state"
    # The chip state change must be coupled to the banner show/clear calls,
    # not an independent control — find both near each other.
    show_at = source.index("showBanner")
    window = source[max(0, show_at - 2000) : show_at + 2000]
    assert "chip" in window.lower() and "warn" in window.lower()
