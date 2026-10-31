# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""LAW 9 RED: vault novel-vs-historical HUD split per sweep (must FAIL pre-GREEN).

Per W1-telemetry-data: vault counts are global, no per-sweep novel/historical
split exists. These tests assert SweepScanResult exposes it; they fail with
AttributeError until GREEN implements the feature. No feature code here.
"""

from modules.intel.sms_vault import (
    VaultNamespace,
    commit_verified,
    query_vault,
)
from modules.workflows.sweep import SweepScanResult


def test_sweep_result_exposes_novel_and_known_counts():
    """SweepScanResult exposes novel_count + known_count derived from VaultQueryResult.status."""
    result = SweepScanResult(target="node_expr_sink")
    # AttributeError until GREEN adds per-sweep split derived from per-target status.
    assert result.novel_count == 1
    assert result.known_count == 0


def test_novel_plus_known_sums_to_n_targets():
    """novel_count + known_count sums to n_targets scanned."""
    result = SweepScanResult(target="node_expr_sink")
    # AttributeError until GREEN adds the split.
    assert result.novel_count + result.known_count == 1


def test_vault_commit_flips_novel_to_known_and_sweep_reflects(tmp_path):
    """Real VaultStore: commit flips NOVEL_SURFACE to KNOWN_ARCHETYPE; sweep reflects it."""
    source = "eval(user_input)  # fixture sink"
    before = query_vault(source, vault_dir=tmp_path)
    assert before.status == "NOVEL_SURFACE"
    commit_verified(
        namespace=VaultNamespace.RED,
        source=source,
        payload={"kind": "probe", "fixture": "node_expr_sink"},
        vault_dir=tmp_path,
    )
    after = query_vault(source, vault_dir=tmp_path)
    assert after.status == "KNOWN_ARCHETYPE"
    # AttributeError until GREEN wires per-target status into SweepScanResult.
    result = SweepScanResult(target="node_expr_sink")
    assert result.vault_novel_vs_historical == {"novel": 0, "historical": 1}


def test_model_dump_has_hud_novel_vs_historical_keys():
    """HUD-ready novel_vs_historical keys present in model_dump."""
    result = SweepScanResult(target="node_expr_sink")
    # AttributeError until GREEN adds the HUD mapping attribute.
    _ = result.novel_vs_historical
    assert "novel_vs_historical" in result.model_dump()
