# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (Bonus-3): documented static-asset pipeline for the final video render.

Pre-change the repo has zero Image/Glimmer references and no asset manifest:
`docs/ASSETS.md` does not exist and no `web/assets/*` placeholders exist, so
the final video render has no documented title-card/thumbnail substrate.

GREEN pins the honest substrate (placeholders + exact generation prompts,
no fake Image-model credit):

(a) `docs/ASSETS.md` exists and names each asset file, its exact generation
    prompt (for a later Muse Image run), and its placement (demo title card,
    gallery thumbnail).
(b) Each `web/assets/*` file referenced exists, is < 50 KB, and parses as
    SVG (xml.etree check, no external fonts/images).
(c) `web/demo.html` (or `web/index.html`) references the title-card asset
    with a graceful `onerror` fallback (no broken image when offline).
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DOC = ROOT / "docs" / "ASSETS.md"
ASSETS_DIR = ROOT / "web" / "assets"
MAX_SVG_BYTES = 50 * 1024

EXPECTED = ("title-card.svg", "thumbnail.svg")


def _doc_text():
    assert ASSETS_DOC.is_file(), f"missing asset manifest: {ASSETS_DOC}"
    return ASSETS_DOC.read_text(encoding="utf-8")


def test_assets_doc_names_files_prompts_placement():
    text = _doc_text()
    for name in EXPECTED:
        assert name in text, f"docs/ASSETS.md does not name {name}"
    assert re.search(r"(?i)prompt", text), "docs/ASSETS.md names no generation prompt"
    assert "demo" in text.lower(), "docs/ASSETS.md names no placement (demo)"
    placement_hits = sum(
        1
        for needle in ("title card", "thumbnail", "title-card", "gallery")
        if needle in text.lower()
    )
    assert placement_hits >= 2, "docs/ASSETS.md must document placement for both assets"


def test_asset_svgs_exist_small_and_valid():
    assert ASSETS_DIR.is_dir(), f"missing asset dir: {ASSETS_DIR}"
    for name in EXPECTED:
        path = ASSETS_DIR / name
        assert path.is_file(), f"missing referenced asset: {path}"
        size = path.stat().st_size
        assert 0 < size < MAX_SVG_BYTES, f"{name} size {size} not in (0, {MAX_SVG_BYTES})"
        raw = path.read_bytes()
        assert b"<svg" in raw, f"{name} is not an SVG document"
        root = ET.fromstring(raw.decode("utf-8", errors="strict"))
        assert root.tag.endswith("svg"), f"{name} root element is not <svg>"
        lowered = raw.lower()
        assert b"http" not in lowered or b"xmlns" in lowered, f"{name} must be dependency-free"
        for banned in (b"<image", b"@import", b"@font-face"):
            assert banned not in lowered, f"{name} must not depend on {banned!r}"


def test_demo_references_title_card_with_fallback():
    candidates = [ROOT / "web" / "demo.html", ROOT / "web" / "index.html"]
    pages = [p for p in candidates if p.is_file()]
    assert pages, "neither web/demo.html nor web/index.html exists"
    hit = None
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if "title-card.svg" in html and "onerror" in html:
            hit = page
            break
    assert hit is not None, (
        "no page references the title-card asset with a graceful onerror fallback"
    )
