#!/usr/bin/env python3
# Run the production scan workflow through real Docker for every fixture, replacing only Muse with known outputs.
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""No API key or inference. Requires built base images. Exit 0 only if every fixture verifies.

This exercises workflow.execute_purple_workflow, DockerSandboxManager, patch validation,
regression checks and cleanup exactly as a real scan does. It proves the sandbox path,
not model quality: the red/blue outputs are the harness's known fixture probe and patch.
"""

import asyncio
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module(name)


class KnownMuse:
    """Stands in for MetaMuseClient. Same async interface, deterministic outputs."""

    def __init__(self, key: str):
        self.key = key
        self.harness = load("test_harness")
        self.agents = load("agents")

    async def run_red_team_analysis(self, filename, source, contract):
        return self.agents.RedTeamFinding(
            vulnerability_class="fixture boundary",
            sink_location=filename,
            analysis_summary="Known fixture boundary (offline check, no model call)",
            verification_script_python=self.harness.diagnostic_script(self.key),
        )

    async def run_blue_team_sanitizer(self, filename, source, finding, evidence, contract):
        return self.agents.BlueTeamPatch(
            sanitization_strategy="Known minimal sanitization (offline check)",
            diff_summary="Known fixture patch",
            patched_file_content=self.harness.known_patch(self.key, source),
        )

    async def aclose(self):
        return None


async def scan(key: str) -> bool:
    config = load("config")
    workflow = load("workflow")
    events: list[str] = []

    async def emit(team: str, message: str) -> None:
        events.append(team)

    result = await workflow.execute_purple_workflow(
        key,
        emit,
        config=config.PurpleBoxConfig(meta_api_key="offline-check-not-a-key"),
        muse_factory=lambda settings: KnownMuse(key),
    )
    print(
        f"{key}: status={result.status} pre={result.pre_exit_code} post={result.post_exit_code} "
        f"baseline={result.baseline_passed} regression={result.regression_passed} "
        f"cleanup={result.cleanup_ok} events={len(events)}",
        flush=True,
    )
    if not result.success:
        print(f"  message: {result.message}", flush=True)
    return result.success


async def main() -> int:
    registry = load("registry")
    results = [await scan(key) for key in registry.TARGETS_REGISTRY]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
