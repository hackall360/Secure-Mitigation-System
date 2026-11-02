"""LAW 9 RED test: Web UI repo-ingest flow (W7 ingest UI, tribunal 2a-2 gap).

Pins the 7th `.c-mode` button + schema-driven ingest fields by parsing
web/prod-setup.html and web/js as text (no browser needed):

- 7th source button with ``data-mode="ingest"``,
- schema ``SOURCES.ingest`` with ``ingest_repo`` + ``commit_hash`` fields
  riding ``/ws/project`` (ingest rides the project flow),
- ``link.js`` ingest entry posting ``{ingest_repo, commit_hash}`` first,
- research flags riding free via the shared ``query()`` builder.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HTML = REPO / "web" / "prod-setup.html"
SCHEMA = REPO / "web" / "js" / "options" / "schema.js"
LINK = REPO / "web" / "js" / "stream" / "link.js"


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def _schema() -> str:
    return SCHEMA.read_text(encoding="utf-8")


def _link() -> str:
    return LINK.read_text(encoding="utf-8")


def test_ingest_mode_button_is_seventh_mode():
    html = _html()
    assert html.count('data-mode="') == 7, "setup must have 7 source buttons"
    assert 'data-mode="ingest"' in html


def test_ingest_form_clones_binary_form_pattern():
    schema = _schema()
    block = schema[schema.index("ingest: {") :]
    block = block[: block.index("},") + 1]
    assert "ingest_repo" in block and "commit_hash" in block
    assert "'/ws/project'" in block or '"/ws/project"' in block
    assert "ingest_repo" in schema[schema.index("REQUIRED") :]


def test_set_source_mode_handles_ingest():
    setup = (REPO / "web" / "js" / "pages" / "setup-prod.js").read_text(encoding="utf-8")
    assert "'ingest'" in setup or '"ingest"' in setup


def test_submit_ingest_posts_first_frame_to_ws_project():
    link = _link()
    assert "ingest: (repo, commit, opts, h)" in link
    assert "/ws/project" in link
    # ingest rides free on the shared query builder (research flags) ...
    assert "query(opts)" in link
    # ... and posts the pinned-commit first frame.
    assert "ingest_repo: repo, commit_hash: commit" in link
