# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Writer-A additive tests: cve key, digit->fixture-mode path, chips, help, capabilities.

LAW 4: state holds only user-typed metadata, never scan output. No
probe/payload content appears in rendered text or in these assertions.
"""

import tui


def test_parse_key_c_selects_cve_mode():
    assert tui.parse_key("c") == "mode:cve"
    assert tui.parse_key("C") == "mode:cve"


def test_digits_select_fixture_index_and_fixture_mode():
    for digit, index in (("1", 0), ("2", 1), ("3", 2)):
        assert tui.parse_key(digit) == f"select:{index}"
    for index in range(3):
        state = tui.TuiState()
        tui.apply_action(state, "mode:sweep")
        assert state.mode == "sweep"
        assert tui.apply_action(state, f"select:{index}") == f"select:{index}"
        assert state.fixture_index == index
        assert state.mode == "fixture"


def test_render_panes_mode_depth_chips_all_modes_within_80_cols():
    for mode in ("fixture", "sweep", "mcp", "binary", "project", "demo", "cve"):
        for depth in (1, 2, 3):
            state = tui.TuiState()
            tui.apply_action(state, f"mode:{mode}")
            for _ in range(depth - 1):
                tui.apply_action(state, "depth:inc")
            lines = tui.render_panes(state, width=80, height=24)
            text = "\n".join(lines)
            assert f"mode:{mode}" in text
            assert f"depth:{depth}" in text
            assert all(len(line) <= 80 for line in lines)


def test_footer_help_covers_all_mode_keys_and_depth():
    for entry in ("m mcp", "b binary", "p project", "g sweep", "v demo", "c cve"):
        assert entry in tui.FOOTER_HELP
    assert "+/- depth" in tui.FOOTER_HELP


def test_capabilities_lines_cover_every_mode():
    text = "\n".join(tui.CAPABILITIES_LINES)
    for mode in ("fixture", "sweep", "mcp", "binary", "project", "demo", "cve"):
        assert f"mode:{mode}" in text


def test_state_metadata_fields_default_empty_and_hold_user_text():
    state = tui.TuiState()
    state.mcp_snippet = "user snippet label"
    state.binary_path = "user picked file"
    assert state.mcp_snippet == "user snippet label"
    assert state.binary_path == "user picked file"
    text = "\n".join(tui.render_panes(state, width=80, height=24))
    assert "user snippet label" not in text
    assert "user picked file" not in text
