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
    assert tags.MODULE_VERSIONS, "MODULE_VERSIONS must not be empty"
    for module_name, version in tags.MODULE_VERSIONS.items():
        assert re.fullmatch(r"0\.\d+\.\d+", version), (module_name, version)
        leaf = tags._load_module(module_name)
        assert getattr(leaf, "__version__", None) == version, module_name


def test_dom_tags_invisible_and_registered():
    console = (ROOT / "web" / "console.html").read_text(encoding="utf-8")
    setup = (ROOT / "web" / "prod-setup.html").read_text(encoding="utf-8")
    html = console + setup
    css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "web" / "css").rglob("*.css"))
    js = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "web" / "js").rglob("*.js"))
    # Audit hooks only: no styling, no behavior reads. v3 keeps audit hooks
    # as data-f attributes (console.html team-filter buttons); grep confirms
    # zero data-feature hooks across web/.
    assert "data-feature" not in css, "DOM tags must never be styled"
    assert "data-feature" not in js, "DOM tags must never drive behavior"
    assert "data-feature" not in html, "v3 carries no data-feature hooks"
    # The data-f hook system is team filters (all/red/blue/purple/green/
    # yellow/orange), NOT feature tags: assert it separately and never conflate
    # it with the registry check below.
    hook_values: set[str] = set()
    for match in re.finditer(r'data-f="([^"]+)"', html):
        hook_values.update(match.group(1).split())
    assert hook_values == {"all", "red", "blue", "purple", "green", "yellow", "orange"}, hook_values
    # Registry anchors: every surviving v3 id must be present, every retired
    # v2-flat-dashboard id must be absent (fail-first against re-adding v2 ids).
    live_ids = set(re.findall(r'id="([^"]+)"', html))
    all_ids = set(live_ids)
    for page in ("index.html", "demo.html", "demo-setup.html", "visualizer.html"):
        all_ids |= set(re.findall(r'id="([^"]+)"', (ROOT / "web" / page).read_text()))
    registry_web = {str(entry["ui"]) for entry in tags.FEATURE_TAGS.values() if entry["ui"]}
    present = registry_web & all_ids
    absent = registry_web - all_ids
    # 19 anchors survive in v3 (chips, comms/log rails, result sheet, setup);
    # 23 v2-flat-dashboard anchors are retired with static/.
    assert present == {
        "cfg-errors",
        "chip-docker",
        "chip-key",
        "chip-server",
        "comms",
        "cp-diff",
        "dl-json",
        "dl-patch",
        "fixture-list",
        "launch",
        "legend",
        "r-cycles",
        "r-diff",
        "r-facts",
        "r-usage",
        "result",
        "stagebar",
        "stop",
        "timeline",
    }, sorted(present)
    assert len(absent) == 23, sorted(absent)
    # v2-flat-dashboard ids live in the delegated-needle map, not as ui
    # anchors: their v3 equivalents (launch, timeline, c-fx, ...) are
    # asserted present above; here the retired raw ids must stay gone.
    import library.tags as _tags

    retired = {"run-btn", "scan-timeline", "target-list", "usage", "telemetry-log"}
    assert retired <= set(_tags.WEB_DELEGATED_NEEDLES), sorted(retired)
    for dom_id in retired:
        assert f'id="{dom_id}"' not in html and f"id='{dom_id}'" not in js, (
            f"retired v2 id #{dom_id} leaked back into web/"
        )
    for dom_id in absent:
        assert f'id="{dom_id}"' not in html and f"id='{dom_id}'" not in js, (
            f"retired v2 anchor #{dom_id} leaked back into web/"
        )
