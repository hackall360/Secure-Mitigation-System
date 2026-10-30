# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Fail-first chain-pass prompt tests (LAW 9 RED).

The 4th sweep pass ("chain") does not exist yet: no RED_CHAIN_SYSTEM_PROMPT,
no "chain" dispatch in run_red_team_pass_analysis, no SWEEP_PASSES entry, and
max_passes still clamps to 3. These tests pin the contract before it lands.

LAW 4: contract strings only, no exploit payloads.
"""


def test_chain_prompt_contract_tokens():
    from modules.core.prompts import RED_CHAIN_SYSTEM_PROMPT

    lowered = RED_CHAIN_SYSTEM_PROMPT.lower()
    assert "chain" in lowered
    assert ("multi-step" in lowered) or ("step-a" in lowered)
    assert "do not repeat" in lowered


def test_chain_prompt_demands_four_fields():
    from modules.core.prompts import RED_CHAIN_SYSTEM_PROMPT

    for field in (
        "vulnerability_class",
        "sink_location",
        "analysis_summary",
        "verification_script_python",
    ):
        assert field in RED_CHAIN_SYSTEM_PROMPT, field


def test_chain_pass_dispatches_to_chain_prompt(monkeypatch):
    import asyncio

    from modules.core.agents import MetaMuseClient
    from modules.core.config import PurpleBoxConfig
    from modules.core.prompts import RED_CHAIN_SYSTEM_PROMPT

    async def fake_request(self, model, system, payload, schema, role=""):
        from modules.core.agents import RedTeamFinding

        self.captured_systems.append(system)
        return RedTeamFinding(
            vulnerability_class="test boundary chain",
            sink_location="app.js",
            analysis_summary="Test-only injected agent.",
            verification_script_python="import sys\nsys.exit(0)",
        )

    monkeypatch.setattr(MetaMuseClient, "_request", fake_request)
    muse = MetaMuseClient(PurpleBoxConfig(meta_api_key="test-key"))
    muse.captured_systems = []
    asyncio.new_event_loop().run_until_complete(
        muse.run_red_team_pass_analysis("chain", "app.js", "src", "")
    )
    assert muse.captured_systems == [RED_CHAIN_SYSTEM_PROMPT]


def test_sweep_passes_include_chain():
    from modules.workflows.sweep import SWEEP_PASSES

    assert tuple(SWEEP_PASSES) == ("standard", "deep", "threat_actor", "chain")


def test_sweep_max_passes_accepts_four():
    import asyncio

    from modules.core.agents import BlueTeamPatch, RedTeamFinding
    from modules.core.config import PurpleBoxConfig
    from tests.helpers import FakeFixtureSandbox, silent_emit

    class ChainSweepFakeMuse:
        def __init__(self):
            self.red_calls: list = []
            self.blue_calls = 0

        async def run_red_team_pass_analysis(
            self, pass_id, filename, source, contract=""
        ):
            self.red_calls.append(pass_id)
            return RedTeamFinding(
                vulnerability_class=f"test boundary {pass_id}",
                sink_location=filename,
                analysis_summary="Test-only injected agent.",
                verification_script_python="import sys\nsys.exit(0)",
            )

        async def run_blue_team_sanitizer(
            self, filename, source_code, finding=None, evidence="", contract=""
        ):
            self.blue_calls += 1
            patched = source_code.rstrip("\n") + f"\n// sweep-guard-{self.blue_calls}\n"
            return BlueTeamPatch(
                sanitization_strategy="Validate IDs",
                diff_summary="Add a guard",
                patched_file_content=patched,
            )

        async def aclose(self):
            return None

    from modules.workflows.sweep import execute_sweep_scan

    codes = [0] + [0, 0, 1, 0] * 4
    sandbox = FakeFixtureSandbox(codes)
    muse = ChainSweepFakeMuse()
    result = asyncio.new_event_loop().run_until_complete(
        execute_sweep_scan(
            "node_query_sink",
            silent_emit,
            config=PurpleBoxConfig(meta_api_key="test-key"),
            sandbox_factory=lambda settings: sandbox,
            muse_factory=lambda settings: muse,
            max_passes=4,
        )
    )
    assert [p.pass_id for p in result.pass_results] == [
        "standard",
        "deep",
        "threat_actor",
        "chain",
    ]
