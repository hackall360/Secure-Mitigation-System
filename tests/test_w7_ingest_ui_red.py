"""LAW 9 RED test: Web UI repo-ingest flow (W7 ingest UI, tribunal 2a-2 gap).

Pins the 6th `.mode` button + ingest form DOM ids + submit function by
parsing static/index.html and static/app.js as text (no browser needed):

- 6th mode button ``mode-ingest`` with ``data-mode="ingest"``,
- ``ingest-form`` cloning the ``binary-form`` pattern with repo URL +
  commit hash fields (``ingest-repo-url``, ``ingest-commit``),
- ``setSourceMode`` ``ingest`` branch toggling the form,
- ``submitIngest`` posting first-frame JSON to ``/ws/project``
  (ingest rides the project flow per W4 dispatch), research flags
  riding free via ``socketQuery()``.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HTML = REPO / "static" / "index.html"
JS = REPO / "static" / "app.js"


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def _js() -> str:
    return JS.read_text(encoding="utf-8")


def test_ingest_mode_button_is_sixth_mode():
    html = _html()
    assert html.count('<button id="mode-') == 6, "dashboard must have 6 .mode buttons"
    assert 'id="mode-ingest"' in html
    assert 'data-mode="ingest"' in html


def test_ingest_form_clones_binary_form_pattern():
    html = _html()
    assert 'id="ingest-form"' in html
    assert 'id="ingest-repo-url"' in html
    assert 'id="ingest-commit"' in html
    assert 'id="ingest-errors"' in html


def test_set_source_mode_handles_ingest():
    js = _js()
    assert "'ingest'" in js
    assert "el('ingest-form').hidden = mode !== 'ingest'" in js


def test_submit_ingest_posts_first_frame_to_ws_project():
    js = _js()
    assert "function submitIngest" in js
    assert "/ws/project" in js
    # ingest rides free on the shared query builder (research flags) ...
    assert js.count("socketQuery()") >= 3
    # ... and the submit path dispatches through startScan like binary does.
    assert "submitIngest()" in js
