# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first gap tests for pure presentation surfaces (sms_cli/tui/main writers).

SCOPE: pure helpers reachable from main.py/tui.py/sms_cli.py/docker harnesses
only — fact_table/usage_table/status_color/paint/_coerce_argv/emit progress/
report writers. No socket/server tests (out of scope).
"""


def test_status_color_error_is_red_exact():
    from sms_cli import paint, status_color

    assert status_color("error", use_color=True) == "\x1b[31merror\x1b[0m"
    assert status_color("failed", use_color=True) == paint("failed", "red", True)


def test_status_color_unknown_falls_through_to_yellow_exact():
    from sms_cli import status_color

    weird = "weird-status"
    assert status_color(weird, use_color=True) == f"\x1b[33m{weird}\x1b[0m"


def test_probe_label_exit_paths_exact():
    from sms_cli import _probe_label

    assert _probe_label(2) == "Inconclusive (exit 2)"
    assert _probe_label(None) == "Not reported"
    assert _probe_label(9) == "Exit 9"


def test_paint_unknown_color_returns_text_verbatim():
    from sms_cli import paint

    assert paint("x", "nope", use_color=True) == "x"


def test_fact_table_degrades_wave2_boom_to_not_reported():
    from sms_cli import fact_table

    class Boom:
        target = "t"
        status = "verified"
        message = "m"

        @property
        def model_dump(self):
            raise RuntimeError("boom")

    table = fact_table(Boom(), use_color=False)
    assert "Scan facts" in table
    receipt = [line for line in table.splitlines() if "Receipt" in line]
    assert receipt and receipt[0].split("Receipt", 1)[1].strip() == "Not reported"


def test_coerce_argv_tuple_json_and_shlex_exact():
    import tui

    assert tui._coerce_argv(("x", "y"), ["a"]) == ["x", "y"]
    assert tui._coerce_argv('["p", "q"]', ["a"]) == ["p", "q"]
    assert tui._coerce_argv("a b 'c d'", ["z"]) == ["a", "b", "c d"]
    assert tui._coerce_argv([], ["dflt"]) == ["dflt"]


def test_rc_from_outcome_bool_dict_and_object_exact():
    from types import SimpleNamespace

    import tui

    assert tui._rc_from_outcome(True) == 0
    assert tui._rc_from_outcome(False) == 1
    assert tui._rc_from_outcome({"status": "ok"}) == 0
    assert tui._rc_from_outcome({"status": "error"}) == 1
    assert tui._rc_from_outcome(SimpleNamespace(status="failed")) == 1
    assert tui._rc_from_outcome(SimpleNamespace(success=True)) == 0


def test_prompt_line_eof_blank_and_keyboard_fall_back_to_default():
    import tui

    def _boom(prompt, exc):
        def _raise(prompt):
            raise exc()

        return _raise

    assert tui.prompt_line("p", "dflt", input_func=_boom("p", EOFError)) == "dflt"
    assert tui.prompt_line("p", "dflt", input_func=_boom("p", KeyboardInterrupt)) == "dflt"
    assert tui.prompt_line("p", "dflt", input_func=lambda p: "   ") == "dflt"
    assert tui.prompt_line("p", "dflt", input_func=lambda p: None) == "dflt"
    assert tui.prompt_line("p", "dflt", input_func=lambda p: "  hi  ") == "hi"


def test_redact_event_text_masks_secret_path_and_script_markers():
    import tui

    assert tui.redact_event_text("red", "my api_key is abc") == "[redacted: credentials hidden]"
    assert tui.redact_event_text("sys", "wrote /etc/shadow file ok") == "sys: wrote <path> file ok"
    assert tui.redact_event_text("red", "traceback boom here") == "red: <probe> boom here"


def test_queue_emit_redacts_credentials_into_queue():
    import asyncio
    import queue as queue_mod

    import tui

    async def _run():
        events = queue_mod.Queue()
        emit = tui.queue_emit(events)
        await emit("red", "leaked secret token abc")
        return events.get()

    assert asyncio.run(_run()) == ("red", "[redacted: credentials hidden]")


def test_describe_result_exact_one_liner_with_receipt_token():
    from types import SimpleNamespace

    import tui

    result = SimpleNamespace(
        target="t",
        status="verified",
        message="m",
        receipt={
            "fixture": "fx",
            "pre_exit_code": 0,
            "post_exit_code": 1,
            "patch_sha256": "ab" * 32,
        },
        model_dump=lambda: {"target": "t"},
    )
    assert tui.describe_result(result) == (
        "t -> verified: m [receipt fx \u00b7 probe 0/1 \u00b7 sha abababababab \u00b7 chain broken]"
    )


def test_write_run_report_fresh_dir_and_0600_files_with_receipt(tmp_path):
    import json
    import stat

    import main

    report = {
        "receipt": {
            "fixture": "fx",
            "pre_exit_code": 0,
            "post_exit_code": 1,
            "patch_sha256": "ab" * 32,
        }
    }
    run_dir = main.write_run_report(tmp_path, report, "# summary", diff="--- patch")
    assert run_dir.is_dir()
    assert (stat.S_IMODE(run_dir.stat().st_mode)) == 0o700
    for name in ("report.json", "receipt.json", "SUMMARY.md", "candidate.patch"):
        assert (stat.S_IMODE((run_dir / name).stat().st_mode)) == 0o600
    assert "fx" in (run_dir / "receipt.json").read_text(encoding="utf-8")
    assert json.loads((run_dir / "report.json").read_text(encoding="utf-8")) == report


def test_extract_cycle_receipts_preserves_first_cycle_order():
    import main

    report = {"cycle_reports": [{"receipt": {"a": 1}}, {"receipt": {"b": 2}}]}
    assert main.extract_cycle_receipts(report) == [{"a": 1}, {"b": 2}]
    assert main.extract_cycle_receipts("nope") == []


def test_redact_event_text_truncates_long_plain_text_with_ellipsis():
    import tui

    out = tui.redact_event_text("k", "x" * 250)
    assert out.startswith("k: ")
    assert out.endswith("...")
    assert len(out) == 3 + 157 + 3  # "k: " + text[:157] + "..."


def test_state_mode_blank_falls_back_to_fixture():
    from types import SimpleNamespace

    import tui

    assert tui._state_mode(SimpleNamespace(mode="sweep")) == "sweep"
    assert tui._state_mode(SimpleNamespace(mode="")) == "fixture"


def test_coerce_argv_none_empty_and_malformed_json_exact():
    import tui

    assert tui._coerce_argv(None, ["dflt"]) == ["dflt"]
    assert tui._coerce_argv((), ["dflt"]) == ["dflt"]
    assert tui._coerce_argv("[not json", ["dflt"]) == ["[not", "json"]


def test_state_int_missing_and_garbage_return_default_clamped_exact():
    from types import SimpleNamespace

    import tui

    assert tui._state_int(SimpleNamespace(), "missing", 7, 1, 9) == 7
    assert tui._state_int(SimpleNamespace(d="bad"), "d", 7, 1, 9) == 7
    assert tui._state_int(SimpleNamespace(depth=5), "depth", 1, 1, 4) == 4


def test_result_field_dict_and_object_defaults_exact():
    from types import SimpleNamespace

    import tui

    assert tui._result_field({"k": 1}, "missing") == "?"
    assert tui._result_field({"k": None}, "k", "D") == "D"
    assert tui._result_field(SimpleNamespace(), "missing", "D") == "D"
    assert tui._state_field(SimpleNamespace(), "nope", default="Dflt") == "Dflt"


def test_rc_from_outcome_int_passthrough_and_unknown_object_zero():
    from types import SimpleNamespace

    import tui

    assert tui._rc_from_outcome(7) == 7
    assert tui._rc_from_outcome(SimpleNamespace(status="weird")) == 0
