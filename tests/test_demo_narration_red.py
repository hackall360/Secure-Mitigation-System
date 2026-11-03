# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (rubric 4B): narration toggle on the demo presenter (text-first, audio opt-in).

- `web/js/pages/demo.js` carries a `narrationToggle` handler that reads the
  current beat's stem id + narration text (BEATS mirror of docs/DEMO_SCRIPT.md)
  and best-effort fetches the stub contract `fetch('/api/narration/<stem>')`.
  No TTS server calls: a 404/missing stem must degrade gracefully (silent
  catch + non-ok guard) while the caption text update stays unconditional.
- `web/demo.html` carries one toggle button with the matching id.
- The toggle defaults OFF: untouched runs behave exactly as before.

RED proof: pre-change run fails (no toggle anywhere).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_JS = ROOT / "web" / "js" / "pages" / "demo.js"
DEMO_HTML = ROOT / "web" / "demo.html"

BTN_ID = "nar-toggle"


def _js():
    return DEMO_JS.read_text(encoding="utf-8")


def _html():
    return DEMO_HTML.read_text(encoding="utf-8")


def _handler_body():
    js = _js()
    m = re.search(r"function narrationToggle\(.*?\)\s*\{(.*?)\n  \}", js, re.S)
    assert m, "demo.js must define a narrationToggle handler"
    return m.group(1)


def test_toggle_button_exists_with_matching_id():
    html = _html()
    assert f'id="{BTN_ID}"' in html, "demo.html must contain the narration toggle button"
    assert f"$('{BTN_ID}')" in _js() or f'$("{BTN_ID}")' in _js(), (
        "demo.js must wire the button via the matching id"
    )


def test_handler_reads_beat_stem_and_narration():
    body = _handler_body()
    assert ".stem" in body, "handler must read the current beat's stem id"
    assert ".narration" in body, "handler must read the current beat's narration text"


def test_handler_fetches_stub_endpoint():
    body = _handler_body()
    assert "fetch('/api/narration/" in body or 'fetch("/api/narration/' in body, (
        "handler must issue fetch('/api/narration/<stem>') (stub endpoint contract)"
    )
    assert "stem" in body.split("fetch", 1)[1], "fetch URL must carry the beat stem id"


def test_graceful_fallback_branch_exists():
    body = _handler_body()
    assert ".catch(" in body, "handler must silently catch a failed stem fetch"
    assert "r.ok" in body or "res.ok" in body or ".ok" in body, (
        "handler must guard non-ok (e.g. 404) responses: caption still updates"
    )


def test_caption_text_update_is_unconditional():
    js = _js()
    m = re.search(r"function caption\(.*?\)\s*\{(.*?)\n  \}", js, re.S)
    assert m, "demo.js must still define caption()"
    cap = m.group(1)
    assert "cap-title" in cap, "caption() must still update the caption text unconditionally"
    assert "narrationOn" not in cap or "narrationToggle(" in cap, (
        "caption text must not be gated on the narration flag"
    )


def test_toggle_defaults_off():
    js = _js()
    assert re.search(r"narrationOn\s*=\s*false", js), "narration flag must default OFF"
    assert "narrationOn = true" not in js, "nothing may enable narration without a click"
    body = _handler_body()
    assert "narrationOn" in body, "handler must no-op while the toggle is OFF"
    html = _html()
    m = re.search(rf'<[^>]*id="{BTN_ID}"[^>]*>', html)
    assert m, "toggle button must exist"
    assert 'aria-pressed="false"' in m.group(0), "toggle button must render OFF"
