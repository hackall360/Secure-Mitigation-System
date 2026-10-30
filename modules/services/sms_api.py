# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""First-class Python library API (Subsystem E, V1 Y5).

External applications import this module and call the engine directly::

    from modules.services.sms_api import scan_source, verify_receipt

    receipt = await scan_source("node_query_sink", emit=print)
    verdict = verify_receipt(receipt.model_dump())

No CLI parsing, no stdout scraping: structured Pydantic receipts in,
structured dicts out. Docker evidence still decides every verdict; these
wrappers never invent one.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ConfigDict

from modules.core.config import PurpleBoxConfig
from modules.workflows.workflow import ScanResult, VerdictReceipt


class ApiScanRequest(BaseModel):
    """Programmatic scan request: fixture key + optional pass depth."""

    model_config = ConfigDict(extra="forbid", strict=True)
    target: str = "node_query_sink"
    max_passes: int = 1


async def scan_source(
    target: str,
    emit: Callable[[str, str], Awaitable[None] | None] | None = None,
    *,
    config: PurpleBoxConfig | None = None,
    max_passes: int = 1,
) -> ScanResult:
    """Run the evidence-gated red/blue loop over a fixture or snippet target."""
    from modules.workflows.sweep import execute_sweep_scan
    from modules.workflows.workflow import execute_purple_workflow

    async def _emit(team: str, message: str) -> None:
        if emit is None:
            return
        outcome = emit(team, message)
        if isinstance(outcome, Awaitable):
            await outcome

    if max_passes > 1:
        return await execute_sweep_scan(
            target, _emit, config=config, max_passes=max(1, min(3, max_passes))
        )
    return await execute_purple_workflow(target, _emit, config=config)


async def scan_binary(
    binary_path: str,
    emit: Callable[[str, str], Awaitable[None] | None] | None = None,
    *,
    config: PurpleBoxConfig | None = None,
    contract: str = "",
    max_passes: int = 3,
):
    """Run the 3-pass binary sweep over a compiled binary file on disk."""
    from modules.services.binary_intake import validate_binary_file
    from modules.workflows.binary_sweep import execute_binary_sweep

    spec = validate_binary_file(
        binary_path,
        contract=contract or "Preserve normal behavior. Only harden untrusted inputs.",
    )

    async def _emit(team: str, message: str) -> None:
        if emit is None:
            return
        outcome = emit(team, message)
        if isinstance(outcome, Awaitable):
            await outcome

    return await execute_binary_sweep(
        spec, _emit, config=config, max_passes=max(1, min(3, max_passes))
    )


def query_vault_stats(vault_dir: str | None = None) -> dict[str, Any]:
    """Redacted vault telemetry: counts + savings, never payload material."""
    from modules.intel.sms_vault import vault_stats

    return vault_stats(vault_dir)


def verify_receipt(candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate a VerdictReceipt / CycleReceipt digest without Docker.

    Structural check only: schema conformance + sha256 shape + sane exit
    codes. Returns {"valid": bool, ...}; never raises on malformed input.
    Docker evidence (not this function) is what earns a receipt.
    """
    try:
        receipt = VerdictReceipt.model_validate(candidate)
    except Exception as exc:
        return {"valid": False, "reason": f"schema mismatch ({type(exc).__name__})"}
    digest = receipt.patch_sha256 or ""
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        return {"valid": False, "reason": "patch_sha256 is not a 64-hex digest"}
    if receipt.pre_exit_code not in (0, 1, 2) or receipt.post_exit_code not in (0, 1, 2):
        return {"valid": False, "reason": "exit codes must be 0, 1, or 2"}
    expected: dict[str, Any] = {
        "fixture": receipt.fixture,
        "pre_exit_code": receipt.pre_exit_code,
        "post_exit_code": receipt.post_exit_code,
        "regression_passed": receipt.regression_passed,
    }
    return {"valid": True, "fixture": receipt.fixture, "expected": expected}
