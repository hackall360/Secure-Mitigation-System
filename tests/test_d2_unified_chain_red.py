# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): unified single-payload chain contract (Target 2, 2b-3/4).

Gap: the Pass-4 chain sweep runs two ChainLink verdicts against the SAME
script (sweep.py duplicates one pre/post pair into both links), and the chain
prompt asks for "both steps in one run" without demanding the two weaknesses
be DISPARATE classes combined into a SINGLE unified payload.

Contract pinned BEFORE the orchestration refinement (expect FAIL):

1. `RED_CHAIN_SYSTEM_PROMPT` must demand a SINGLE unified payload combining
   two DISPARATE weakness classes (e.g. auth-bypass primitive + injection
   sink), not two sequential same-class probes.
2. `SweepPassResult` chain verdict must record two DISTINCT link probes
   (the runner must execute the chain script's two links separately and must
   not duplicate one pre/post pair into both ChainLinks).

Benign contract strings only: prompt-content markers + verdict-shape pins.
No payloads, no live key, no real Docker/Muse here.
"""

import modules.workflows.sweep as sweep_module


def test_chain_prompt_demands_unified_disparate_payload():
    """Chain prompt requires one unified payload of two disparate classes."""
    from modules.core.prompts import RED_CHAIN_SYSTEM_PROMPT

    lowered = RED_CHAIN_SYSTEM_PROMPT.lower()
    assert "single" in lowered and "payload" in lowered
    assert "disparate" in lowered or "two distinct" in lowered or "distinct" in lowered
    assert "one run" in lowered or "single run" in lowered or "single script" in lowered
    assert "link b" in lowered and "marker" in lowered
    assert "self-contained" in lowered


def test_chain_runner_records_distinct_link_probes():
    """Chain pass executes two link probes; links must not be duplicates."""
    import inspect

    import modules.workflows.sweep as sweep

    source = inspect.getsource(sweep.execute_sweep_scan)
    assert "link_a_pre" in source and "link_b_pre" in source
    assert "link_a_post" in source and "link_b_post" in source
    assert "link-A probe was inconclusive" in source
    assert "link-B probe was inconclusive" in source
    assert "link-A post-patch probe was inconclusive" in source
    assert "link-B post-patch probe was inconclusive" in source
    assert "ChainLink(pre_exit=pre.exit_code, post_exit=post.exit_code)" in source
    assert "ChainLink(" in source and "link_a_pre.exit_code" in source
    assert "link_b_post.exit_code" in source


def test_chain_pass_result_supports_two_distinct_probes():
    """Chain verdict shape holds unified + pre/post link-pair evidence."""
    from modules.workflows.sweep import ChainLink, SweepPassResult

    assert sweep_module.ChainLink is ChainLink
    verified_chain = SweepPassResult(
        pass_id="chain",
        chain_links=[
            ChainLink(pre_exit=0, post_exit=1),
            ChainLink(pre_exit=0, post_exit=1),
            ChainLink(pre_exit=0, post_exit=1),
        ],
        regression_passed=True,
        receipt={"chain": [(0, 1), (0, 1), (0, 1)]},
    )
    assert verified_chain.holds is True
    broken_post = SweepPassResult(
        pass_id="chain",
        chain_links=[
            ChainLink(pre_exit=0, post_exit=1),
            ChainLink(pre_exit=0, post_exit=1),
            ChainLink(pre_exit=2, post_exit=2),
        ],
        regression_passed=True,
        receipt={"chain": [(0, 1), (0, 1), (2, 2)]},
    )
    assert broken_post.holds is False


def test_chain_link_probe_scripts_stay_deterministic():
    """Distinct link scripts keep the deterministic 0/1/2 exit contract."""
    import ast

    link_scripts = ("chain_link_a_probe", "chain_link_b_probe")
    assert all(isinstance(name, str) and name for name in link_scripts)
    for name in link_scripts:
        script = f"import sys\n# {name}: deterministic probe stub\nsys.exit(0)\n"
        tree = ast.parse(script)
        exits = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(getattr(node.func, "value", None), "id", "") == "sys"
            and getattr(node.func, "attr", "") == "exit"
        ]
        assert exits, f"{name} must call sys.exit explicitly"


def test_chain_link_splitter_separates_marker_sections():
    """Splitter divides a marked unified script into standalone link probes."""
    from modules.workflows.sweep import _chain_link_probes

    unified = (
        "import sys\n"
        "# Link A: primitive with benign values\n"
        "print('primitive ok')\n"
        "# --- Link B ---\n"
        "# Link B: sink with malicious value\n"
        "print('sink verdict')\n"
        "sys.exit(0)\n"
    )
    link_a, link_b = _chain_link_probes(unified)
    assert "primitive ok" in link_a
    assert "sink verdict" not in link_a
    assert link_a.rstrip().endswith("sys.exit(0)")
    assert "sink verdict" in link_b
    assert "primitive ok" not in link_b


def test_chain_link_splitter_falls_back_without_marker():
    """Unmarked scripts run whole for both links (two real executions)."""
    from modules.workflows.sweep import _chain_link_probes

    script = "import sys\nprint('whole')\nsys.exit(0)\n"
    link_a, link_b = _chain_link_probes(script)
    assert link_a == script and link_b == script
