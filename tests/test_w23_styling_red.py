# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Wave 23: styling-system decision pin, repointed at WebUI v3 (document, don't migrate).

The shipped dashboard uses bespoke token-driven CSS (``web/css/core/tokens.css``
plus ``web/css/core/motion.css`` with ``prefers-reduced-motion``), NOT
Tailwind: no CDN script, no tailwind/postcss config, no ``@apply``/
``@tailwind`` directives, no build step. This is load-bearing for the offline
judge quickstart (no network, no Node build). This test pins the decision so
a future "add Tailwind" drift fails loudly instead of silently forking the
styling system.

Render helpers: v3 renders through ``h()`` in ``web/js/ui/dom.js`` which sets
``textContent`` only — CSP-safe by construction. ``web/js/model/parse-source.js``
MATCHES on the string ``innerHTML`` inside a sink-detection regex (a scan
signature, not a DOM write); it is excluded from the no-innerHTML sweep, which
asserts on assignment patterns instead.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

# parse-source.js matches on the *string* "innerHTML" in a sink regex: it is
# a scanner signature, not a DOM write, so the assignment sweep excludes it.
_PARSE_SOURCE = WEB / "js" / "model" / "parse-source.js"


def _js_sweep_files():
    files = sorted((WEB / "js" / "ui").glob("*.js")) + sorted((WEB / "js" / "pages").glob("*.js"))
    assert files, "v3 ui/pages modules missing"
    return files


def test_no_tailwind_cdn_or_config():
    for page in ("index.html", "console.html", "demo.html", "prod-setup.html", "demo-setup.html"):
        html = (WEB / page).read_text(encoding="utf-8")
        assert "cdn.tailwindcss.com" not in html
        assert "tailwind" not in html.lower(), f"tailwind mention in {page}"
    assert not list(ROOT.glob("tailwind.config.*"))
    assert not list(ROOT.glob("postcss.config.*"))


def test_token_css_system_present():
    css = (WEB / "css" / "core" / "tokens.css").read_text(encoding="utf-8")
    assert "@tailwind" not in css and "@apply" not in css
    for token in (":root", "--bg:", "--red:", "--blue:", "--green:", "--r:"):
        assert token in css, f"design token missing: {token}"
    assert "SMS v3" in css, "tokens.css must carry the v3 header"
    motion = (WEB / "css" / "core" / "motion.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in motion, "motion.css must honor reduced-motion"


def test_render_helpers_still_contract():
    """``h()`` textContent-only: no ``.innerHTML`` assignments in v3 render paths."""
    dom = (WEB / "js" / "ui" / "dom.js").read_text(encoding="utf-8")
    assert "function h(" in dom, "dom.js must define the h() render helper"
    assert "textContent" in dom, "h() must assign through textContent"
    assert ".innerHTML" not in dom.replace("no innerHTML", ""), "dom.js must not assign innerHTML"
    for path in _js_sweep_files():
        if path == _PARSE_SOURCE:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\.innerHTML", text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line = text[line_start : text.index("\n", match.end())]
            stripped = line.strip()
            # Comments documenting the invariant are not writes.
            if stripped.startswith(("//", "*", "<!--")) or "no innerHTML" in stripped:
                continue
            raise AssertionError(f"{path.name} assigns innerHTML: {stripped!r}")
