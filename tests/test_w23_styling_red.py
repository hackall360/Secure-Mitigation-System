# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Wave 23: styling-system decision pin (document, don't migrate).

The shipped dashboard uses bespoke token-driven CSS (static/app.css
"design system v2"), NOT Tailwind: no CDN script, no tailwind/postcss
config, no @apply/@tailwind directives, no build step. This is load-bearing
for the offline judge quickstart (no network, no Node build). This test pins
the decision so a future "add Tailwind" drift fails loudly instead of
silently forking the styling system.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_tailwind_cdn_or_config():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "cdn.tailwindcss.com" not in html
    assert "tailwind" not in html.lower()
    assert not list(ROOT.glob("tailwind.config.*"))
    assert not list(ROOT.glob("postcss.config.*"))


def test_token_css_system_present():
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    assert "@tailwind" not in css and "@apply" not in css
    for token in (":root", "--bg:", "--surface", "--red:", "--blue:", "--green:", "--radius"):
        assert token in css, f"design token missing: {token}"
    assert "design system v2" in css


def test_render_helpers_still_contract():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    for symbol in ("buildEntry", "writeLine", "handleSocketMessage", "showBanner", "renderUsage"):
        assert symbol in js, f"render contract missing: {symbol}"
