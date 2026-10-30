# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED sweep-level compression HUD aggregator tests (LAW 9).

Written BEFORE the sweep-level token aggregator exists. Per W1-telemetry-data,
per-target CompressionReports exist (SweepScanResult.compression) but NO
sweep-level aggregator exists. These tests MUST FAIL with AttributeError
(missing aggregator) until the feature is implemented. Never weaken them.
"""

import math

from modules.shared.sms_compress import CompressionReport
from modules.workflows.sweep import SweepScanResult


def _sweep_compression_of(result: SweepScanResult):
    """Resolve the sweep-level aggregator (or equivalent) or raise AttributeError."""
    for name in ("sweep_compression", "sweep_compression_summary", "compression_summary"):
        if hasattr(result, name):
            return getattr(result, name)
    raise AttributeError(
        "missing sweep-level token aggregator: SweepScanResult has no "
        "'sweep_compression' (or equivalent) aggregating per-pass/per-target reports"
    )


def _module_aggregator():
    """Resolve a module-level sweep aggregator helper or raise AttributeError."""
    import modules.workflows.sweep as sweep_mod

    for name in (
        "aggregate_sweep_compression",
        "summarize_sweep_compression",
        "sweep_compression_summary",
    ):
        if hasattr(sweep_mod, name):
            return getattr(sweep_mod, name)
    raise AttributeError("missing sweep-level token aggregator helper in modules.workflows.sweep")


def test_sweep_result_exposes_sweep_compression_totals():
    r1 = CompressionReport(
        raw_tokens_estimated=1000,
        compressed_tokens_sent=700,
        tokens_saved=300,
        compression_ratio=0.3,
    )
    result = SweepScanResult(target="node_query_sink", compression=r1)
    agg = _sweep_compression_of(result)
    assert agg.total_raw == 1000
    assert agg.total_sent == 700
    assert agg.total_saved == 300
    assert agg.savings_pct == 30.0


def test_sweep_compression_aggregates_across_reports():
    r1 = CompressionReport(
        raw_tokens_estimated=1000,
        compressed_tokens_sent=700,
        tokens_saved=300,
        compression_ratio=0.3,
    )
    r2 = CompressionReport(
        raw_tokens_estimated=500,
        compressed_tokens_sent=400,
        tokens_saved=100,
        compression_ratio=0.2,
    )
    aggregate = _module_aggregator()
    totals = aggregate([r1, r2])
    raw = totals.total_raw if hasattr(totals, "total_raw") else totals["total_raw"]
    sent = totals.total_sent if hasattr(totals, "total_sent") else totals["total_sent"]
    saved = totals.total_saved if hasattr(totals, "total_saved") else totals["total_saved"]
    pct = totals.savings_pct if hasattr(totals, "savings_pct") else totals["savings_pct"]
    assert raw == 1500
    assert sent == 1100
    assert saved == 400
    assert pct == 400 / 1500 * 100


def test_sweep_compression_empty_sweep_zero_division_safe():
    result = SweepScanResult(target="node_query_sink")
    agg = _sweep_compression_of(result)
    pct = agg.savings_pct if hasattr(agg, "savings_pct") else agg["savings_pct"]
    assert pct == 0.0
    assert not math.isnan(pct)


def test_sweep_compression_dict_includes_savings_pct_for_hud():
    r1 = CompressionReport(
        raw_tokens_estimated=1000,
        compressed_tokens_sent=700,
        tokens_saved=300,
        compression_ratio=0.3,
    )
    result = SweepScanResult(target="node_query_sink", compression=r1)
    agg = _sweep_compression_of(result)
    dumped = agg.model_dump() if hasattr(agg, "model_dump") else dict(agg)
    assert "savings_pct" in dumped
