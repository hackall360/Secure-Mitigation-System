# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Slice F recon pins: doc claims about the Meta Model API surface, prompts, pricing.

READ-ONLY pins: assert on shipped code + doc files only. No behavior changed.
Grounding: live docs read 2026-11-04 (see docs/plans/SLICE_F_RECON.md).
"""

from modules.core import agents as agents_mod
from modules.core import prompts as prompts_mod
from modules.core.pricing import PRICES_PER_MILLION


def test_request_body_has_no_stream_flag_and_uses_deprecated_max_tokens_alias():
    import inspect

    src = inspect.getsource(agents_mod.MetaMuseClient._body)
    assert '"stream"' not in src  # non-streaming transport; SSE is endpoint-supported but unused
    assert '"max_tokens"' in src  # deprecated alias for max_completion_tokens; still accepted


def test_request_targets_chat_completions_with_json_schema_response_format():
    import inspect

    src = inspect.getsource(agents_mod.MetaMuseClient._request)
    assert '"chat/completions"' in src
    assert '"response_format"' in src and '"json_schema"' in src
    assert "transient" in src.lower() or "TRANSIENT_STATUS_CODES" in src


def test_transport_issues_sequential_calls_only():
    import inspect

    src = inspect.getsource(agents_mod.MetaMuseClient._request)
    # No server-side parallel sampling (n>1 is HTTP 400 per live docs) and no
    # concurrent fan-out inside one _request call.
    assert '"n"' not in src and "asyncio.gather" not in src and "Semaphore" not in src


def test_pricing_table_matches_live_docs_exactly():
    # Live pricing-rate-limits page 2026-11-04 (standard + contributor rows).
    assert PRICES_PER_MILLION["muse-wonder-1.0"] == (0.20, 4.00, 20.00)
    for m in ("muse-spark-1.3", "muse-spark-1.2", "muse-spark-1.1"):
        assert PRICES_PER_MILLION[m] == (0.15, 1.25, 4.25)
    for m in ("muse-spark-1.3-contributor", "muse-spark-1.2-contributor"):
        assert PRICES_PER_MILLION[m] == (0.002, 0.10, 0.20)


def test_open_weight_rows_stay_provisional():
    # No partner rate card exists (open-weight, not served by api.meta.ai).
    assert PRICES_PER_MILLION["meta-models/muse-spark-open"] == (0.006, 0.30, 0.60)
    assert PRICES_PER_MILLION["meta-models/muse-spark-open-1026"] == (0.006, 0.30, 0.60)


def test_rate_limit_constants_documented_in_recon_doc():
    from pathlib import Path

    text = Path("docs/plans/SLICE_F_RECON.md").read_text()
    for token in ("3000", "4,000,000", "150", "3,000,000", "x-ratelimit-remaining-tokens"):
        assert token in text


def test_max_effort_contributor_trap_documented():
    from pathlib import Path

    text = Path("docs/plans/SLICE_F_RECON.md").read_text()
    assert "muse-spark-1.3-contributor" in text and "max" in text


def test_system_role_compat_and_developer_note_documented():
    from pathlib import Path

    text = Path("docs/plans/SLICE_F_RECON.md").read_text()
    assert "Prefer" in text and "developer" in text and "max_tokens" in text


def test_prompt_noun_inventory_present():
    from pathlib import Path

    text = Path("docs/plans/SLICE_F_RECON.md").read_text()
    assert "input-boundary auditor" in text and "input sanitizer" in text
    assert "RED_COVERAGE_SWEEP_SYSTEM_PROMPT" in text
    # Prompts themselves unchanged by this slice: coverage sweep keeps its 5 classes.
    assert (
        "SECRETS" in prompts_mod.RED_COVERAGE_SWEEP_SYSTEM_PROMPT
        or "Secrets" in prompts_mod.RED_COVERAGE_SWEEP_SYSTEM_PROMPT
        or "secrets" in prompts_mod.RED_COVERAGE_SWEEP_SYSTEM_PROMPT.lower()
    )
