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
from urllib.parse import urlparse

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
    codes, plus the optional receipt-chain link. Returns
    {"valid": bool, "chain_ok": bool, ...}; never raises on malformed input.
    Docker evidence (not this function) is what earns a receipt: a broken
    chain link sets ``chain_ok`` False but never flips ``valid``.
    """
    try:
        receipt = VerdictReceipt.model_validate(candidate)
    except Exception as exc:
        return {
            "valid": False,
            "chain_ok": False,
            "reason": f"schema mismatch ({type(exc).__name__})",
        }
    digest = receipt.patch_sha256 or ""
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        return {"valid": False, "chain_ok": False, "reason": "patch_sha256 is not a 64-hex digest"}
    if receipt.pre_exit_code not in (0, 1, 2) or receipt.post_exit_code not in (0, 1, 2):
        return {"valid": False, "chain_ok": False, "reason": "exit codes must be 0, 1, or 2"}
    expected: dict[str, Any] = {
        "fixture": receipt.fixture,
        "pre_exit_code": receipt.pre_exit_code,
        "post_exit_code": receipt.post_exit_code,
        "regression_passed": receipt.regression_passed,
    }
    # Chain link is structural only, but it binds the digest: a chained
    # receipt re-attests the SAME patch, so a live prev_receipt_sha must
    # equal this receipt's patch_sha256. The all-zero digest is the genesis
    # sentinel ("no previous receipt"): it carries no chain claim, so the
    # verdict falls back to shape alone (valid) while the chain reads
    # broken (chain_ok False). A live link that does not match the digest
    # means the receipt is not what its chain claims -> valid False. An
    # absent or sentinel link never earns or overturns a verdict on its
    # own: Docker evidence alone decides ``valid`` for unlinked receipts.
    # chain_ok asserts positive membership in an intact chain, so genesis
    # (unlinked) receipts report chain_ok False alongside a valid verdict.
    _NULL_LINK = "0" * 64
    prev = receipt.prev_receipt_sha
    linked = prev is not None and prev != _NULL_LINK
    if linked and prev != receipt.patch_sha256:
        return {
            "valid": False,
            "chain_ok": False,
            "reason": "patch_sha256 does not match prev_receipt_sha",
        }
    chain_ok = linked and prev == receipt.patch_sha256
    return {"valid": True, "chain_ok": chain_ok, "fixture": receipt.fixture, "expected": expected}


def build_telemetry_event(
    *,
    raw: int | float,
    sent: int | float,
    savings_pct: float,
    novel: int,
    known: int,
) -> dict[str, str]:
    """HUD websocket event for context-compression telemetry (Wave 6 HUD).

    Returns ``{"team": "telemetry", "type": "log", "msg": ...}`` so the
    dashboard ``writeLine`` path renders it on the activity timeline like
    any other team event. ``msg`` carries redacted counts only (no payload
    material, no model text) per LAW 4.
    """
    return {
        "team": "telemetry",
        "type": "log",
        "msg": (
            f"Telemetry: Raw {int(raw):,} -> Sent {int(sent):,} tokens "
            f"(Savings {float(savings_pct):.1f}%; novel {int(novel)}, "
            f"known {int(known)})"
        ),
    }


def build_ingest_event(*, repo_url: str, sha: str) -> dict[str, str]:
    """HUD websocket event for a validated repo intake (Wave 6 HUD).

    Returns ``{"team": "ingest", "type": "log", "msg": ...}`` for
    ``writeLine``. LAW 4: the URL is redacted to host + short commit sha —
    credentials, userinfo, paths, and query strings never reach the wire,
    so ``msg`` contains no ``@``.
    """
    try:
        host = urlparse(str(repo_url)).hostname or "unknown-host"
    except (ValueError, AttributeError, TypeError):
        host = "unknown-host"
    short_sha = str(sha or "")[:12]
    return {
        "team": "ingest",
        "type": "log",
        "msg": f"Ingest: {host} {short_sha}",
    }


def build_result_hud(result: dict[str, Any] | Any) -> dict[str, Any]:
    """HUD render subset of a scan result for the dashboard result card.

    Picks the token/vault facts ``renderUsage`` needs — ``hud_tokens``
    (raw/sent/saved/ratio), ``hud_vault`` (recall/namespaces),
    ``savings_pct``, and ``novel_vs_historical`` — from either a result
    mapping or a ``ScanResult``-shaped object. Never raises; missing fields
    surface as ``"Not reported"`` so the card renders instead of failing.
    """
    if isinstance(result, dict):
        get = result.get
        raw_tokens = get("hud_tokens")
        raw_vault = get("hud_vault")
    else:
        raw_tokens = getattr(result, "hud_tokens", None)
        raw_vault = getattr(result, "hud_vault", None)

    def _num(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    tokens = raw_tokens if isinstance(raw_tokens, dict) else {}
    vault = raw_vault if isinstance(raw_vault, dict) else {}
    raw = _num(tokens.get("raw", tokens.get("raw_tokens_estimated", 0.0)))
    sent = _num(tokens.get("sent", tokens.get("compressed_tokens_sent", 0.0)))
    saved = _num(tokens.get("saved", tokens.get("tokens_saved", max(0.0, raw - sent))))
    ratio = _num(tokens.get("ratio", tokens.get("compression_ratio", 0.0)))
    savings_pct = round((saved / raw * 100.0) if raw > 0 else 0.0, 1)
    novel = int(_num(vault.get("novel", 0.0)))
    known = int(_num(vault.get("known", 0.0)))
    recall = vault.get("recall", vault.get("vault_recall", ""))
    namespaces = vault.get("namespaces", vault.get("vault_namespaces", []))
    if not isinstance(namespaces, list):
        namespaces = [namespaces] if namespaces else []
    return {
        "hud_tokens": {
            "raw": int(raw),
            "sent": int(sent),
            "saved": int(saved),
            "ratio": ratio,
        },
        "hud_vault": {
            "novel": novel,
            "known": known,
            "recall": str(recall) if recall else "Not reported",
            "namespaces": [str(n) for n in namespaces],
        },
        "savings_pct": savings_pct,
        "novel_vs_historical": f"{novel} novel vs {known} historical",
    }
