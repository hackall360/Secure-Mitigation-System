<!-- Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use. -->
<!-- https://polyformproject.org/licenses/noncommercial/1.0.0 -->
# Static assets (Bonus-3 substrate)

Hand-authored SVG placeholders. No Image/Glimmer model was used to produce
anything in this repo; the prompts below are exact specs for a later
Muse Image generation pass that the final video render will consume.

## Asset table

| File | Purpose / placement | Size | Generation prompt (for later) | Fallback |
|------|---------------------|------|-------------------------------|----------|
| `web/assets/title-card.svg` | Demo title card: `web/demo.html` header brand area (`#demo-title-card`) | 1200x630, < 50 KB | `Dark HUD title card, 1200x630: "SECURE MITIGATION SYSTEM" in monospace, locked-room shield outline motif in teal, red-vs-blue duel dots, 0-to-1-to-dashed-receipt strip along the bottom, near-black navy background, flat vector, no photo, no text other than the title and RECEIPT` | `<img ... onerror="this.remove()">` — the header renders identically without it (offline-safe, no broken-image icon) |
| `web/assets/thumbnail.svg` | Gallery thumbnail: compact variant of the title card for index/gallery surfaces | 640x360, < 50 KB | `Compact 640x360 variant of the SMS title card: same shield motif and red-vs-blue dots left, "SECURE MITIGATION SYSTEM" monospace right, small 0-to-1-to-RECEIPT strip, same navy/teal palette, flat vector, legible at small size` | Same `onerror` removal pattern when wired into a gallery page |

## Pipeline

1. Placeholders live in `web/assets/` and are dependency-free SVG
   (no external fonts, images, `@import`, or `@font-face`).
2. The final video render consumes `title-card.svg` (demo title area) and
   `thumbnail.svg` (gallery/index surfaces).
3. To upgrade: run the generation prompt through Muse Image, save over the
   same filename, keep it under 50 KB, and re-run
   `pytest tests/test_assets_red.py`.

## Proof

- `tests/test_assets_red.py` pins all three clauses (doc, SVG validity, wiring).
