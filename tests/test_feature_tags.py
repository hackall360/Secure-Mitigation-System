# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED: the feature-tag checker must flag uncovered bindings.

Pre-implementation this module fails to import (no library/tags.py yet).
Post-implementation: a bogus web binding is reported uncovered, while the
real registry is fully covered and every DOM data-feature hook is invisible.
"""

import re
from pathlib import Path

import library.tags as tags

ROOT = Path(__file__).resolve().parents[1]


def test_checker_flags_uncovered_web_binding():
    fake = {
        "zz-bogus-capability": {
            "surfaces": ["web"],
            "backend": "main.py:does_not_exist",
            "ui": "nonexistent-dom-id-zz",
            "cli": None,
            "tui": None,
        }
    }
    result = tags.check_registry(fake, root=ROOT)
    assert "zz-bogus-capability" in result["uncovered"]
    assert result["uncovered"]["zz-bogus-capability"] == ["web"]


def test_registry_bindings_all_live():
    result = tags.check_registry(root=ROOT)
    assert result["uncovered"] == {}, f"uncovered tags: {result['uncovered']}"
    assert result["covered_count"] == len(tags.FEATURE_TAGS)
    assert result["covered_count"] > 50, "registry must inventory ALL capabilities"


def test_registry_entries_have_required_shape():
    for tag_id, entry in tags.FEATURE_TAGS.items():
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", tag_id), tag_id
        assert set(entry) >= {"surfaces", "backend", "ui", "cli", "tui"}, tag_id
        assert entry["surfaces"], tag_id
        for surface in entry["surfaces"]:
            assert surface in ("cli", "web", "tui", "api"), (tag_id, surface)
        if "web" in entry["surfaces"]:
            assert entry["ui"], f"{tag_id} claims web with no DOM control"


def test_module_versions_match_leaf_constants():
    import importlib

    assert tags.MODULE_VERSIONS, "MODULE_VERSIONS must not be empty"
    for module_name, version in tags.MODULE_VERSIONS.items():
        assert re.fullmatch(r"0\.\d+\.\d+", version), (module_name, version)
        leaf = importlib.import_module(module_name)
        assert getattr(leaf, "__version__", None) == version, module_name


def test_dom_tags_invisible_and_registered():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    # Audit hooks only: no styling, no behavior reads.
    assert "data-feature" not in css, "DOM tags must never be styled"
    assert "data-feature" not in js, "DOM tags must never drive behavior"
    hook_re = re.compile(r'data-feature="([^"]+)"')
    dom_tags: set[str] = set()
    for match in hook_re.finditer(html):
        dom_tags.update(match.group(1).split())
    assert len(dom_tags) > 20, "every control/panel needs an audit hook"
    registry_web = {str(entry["ui"]) for entry in tags.FEATURE_TAGS.values() if entry["ui"]}
    # Shared hooks (space-separated tags on one element) carry every tag
    # bound to that DOM id.
    hook_map: dict[str, list[str]] = {}
    for match in re.finditer(r'id="([a-z0-9-]+)"[^>]*data-feature="([^"]+)"', html):
        hook_map[match.group(1)] = match.group(2).split()
    for dom_id in registry_web:
        assert dom_id in hook_map, f"no data-feature hook for #{dom_id}"
    for tag_id, entry in tags.FEATURE_TAGS.items():
        if entry["ui"]:
            assert tag_id in hook_map[str(entry["ui"])], (
                f"{tag_id} missing from #{entry['ui']} hook"
            )
    assert dom_tags <= set(tags.FEATURE_TAGS), "DOM tag with no registry entry"
