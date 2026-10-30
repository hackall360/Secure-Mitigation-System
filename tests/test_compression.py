# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first compression tests (Subsystem A, V1 guidance matrix Y1).

RED per LAW 9: written BEFORE modules/shared/sms_compress.py exists.
Run and verify they FAIL for the expected functional reason (ModuleNotFoundError),
then implement the module to turn them green. Never weaken these assertions.
"""


def test_compress_module_importable():
    import modules.shared.sms_compress as compress

    assert callable(compress.compress_context)
    assert callable(compress.estimate_tokens)


def test_estimate_tokens_scales_with_text():
    from modules.shared.sms_compress import estimate_tokens

    short = estimate_tokens("hi")
    long = estimate_tokens("hi" * 1000)
    assert long > short > 0


def test_compress_dedups_repeated_lines():
    from modules.shared.sms_compress import compress_context

    source = "const a = 1;\n" * 20 + "const queryExpression = eval(rawUserId);\n"
    report = compress_context(source, filename="app.js")
    assert report.compressed_tokens < report.raw_tokens
    assert report.tokens_saved > 0
    assert 0.0 < report.compression_ratio < 1.0
    # Security-critical sink line is preserved verbatim.
    assert "const queryExpression = eval(rawUserId);" in report.compressed_text


def test_compress_preserves_sink_and_flow_sentences():
    from modules.shared.sms_compress import compress_context

    source = (
        "// boilerplate comment line\n" * 10
        + "const rawUserId = req.query.id;\n"
        + "// another filler\n" * 10
        + "child_process.exec('diag ' + host);\n"
    )
    report = compress_context(source, filename="index.php")
    assert "rawUserId" in report.compressed_text
    assert "child_process.exec" in report.compressed_text
    assert report.compressed_tokens < report.raw_tokens


def test_compress_empty_and_small_inputs_never_raise():
    from modules.shared.sms_compress import compress_context

    empty = compress_context("", filename="app.js")
    assert empty.raw_tokens == 0
    assert empty.compressed_tokens == 0
    assert empty.tokens_saved == 0
    tiny = compress_context("x", filename="app.js")
    assert tiny.compressed_text == "x"


def test_compress_respects_token_budget():
    from modules.shared.sms_compress import compress_context

    big = "".join(f"// filler line {i:04d} abcdefgh\n" for i in range(2000))
    big += "const queryExpression = eval(rawUserId);\n"
    report = compress_context(big, filename="app.js", max_tokens=200)
    assert report.compressed_tokens <= 200
    assert "const queryExpression = eval(rawUserId);" in report.compressed_text


def test_compression_report_serializes_for_scan_result():
    from modules.shared.sms_compress import compress_context

    report = compress_context("const a = 1;\nconst b = 2;\n", filename="app.js")
    dumped = report.model_dump()
    assert dumped["raw_tokens_estimated"] >= 0
    assert dumped["compressed_tokens_sent"] >= 0
    assert dumped["tokens_saved"] >= 0
    assert 0.0 <= dumped["compression_ratio"] <= 1.0


def test_compression_stats_accumulate_across_cycles():
    from modules.shared.sms_compress import CompressionStats, compress_context

    stats = CompressionStats()
    for chunk in ("const a = 1;\n" * 5, "const b = eval(x);\n" * 5):
        stats.add(compress_context(chunk, filename="app.js"))
    assert stats.cycles == 2
    assert stats.total_raw > 0
    assert stats.total_saved >= 0
    summary = stats.summary()
    assert summary["cycles"] == 2
    assert "total_tokens_saved" in summary
    assert "mean_compression_ratio" in summary


def test_persisted_dictionary_survives_reload(tmp_path):
    from modules.shared.sms_compress import DictionaryStore

    store = DictionaryStore(path=tmp_path / "dict.json")
    store.record(filename="app.js", seen_lines=("const a = 1;", "const b = 2;"))
    store.save()
    reloaded = DictionaryStore(path=tmp_path / "dict.json")
    assert reloaded.known("const a = 1;")
    assert not reloaded.known("const never_seen = 0;")


def test_scan_result_carries_compression_fields():
    from modules.workflows.workflow import ScanResult

    result = ScanResult(target="node_query_sink")
    assert hasattr(result, "compression")
    dumped = result.model_dump()
    assert "compression" in dumped


def test_compress_budget_preserves_order_under_value_equality():
    """Budget pass must not rely on object identity (id())."""
    from modules.shared.sms_compress import compress_context

    # Many filler lines + critical sinks at known positions; force budget
    # trimming so head/tail selection must restore original order.
    filler = "".join(f"x filler unique {i:04d}\n" for i in range(300))
    src = filler + "const queryExpression = eval(rawUserId);\n" + filler
    report = compress_context(src, filename="app.js", max_tokens=80)
    assert report.compressed_tokens <= 80
    assert "const queryExpression = eval(rawUserId);" in report.compressed_text
    # Within budget, non-critical lines that survive should keep original order.
    text = report.compressed_text
    # The surviving filler indices should be monotonically increasing if we map
    # back to the original filler numbering.
    import re

    nums = [int(m.group(1)) for m in re.finditer(r"unique (\d+)", text)]
    assert nums == sorted(nums), nums[:20]
