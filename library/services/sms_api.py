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

import time
from collections.abc import Mapping
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from library.shared.sms_observability import get_aspect
from library.shared.sms_observability import log as obs_log
from library.shared.sms_observability import record_metric as obs_record_metric
from library.shared.sms_observability import trace as obs_trace
from modules.core.config import ConfigurationError, PurpleBoxConfig, load_config
from modules.workflows.workflow import ScanResult, VerdictReceipt

_API_ASPECT = get_aspect("services.api")


class ApiScanRequest(BaseModel):
    """Programmatic scan request: fixture key + optional pass depth."""

    model_config = ConfigDict(extra="forbid", strict=True)
    target: str = "node_query_sink"
    max_passes: int = 1


class ApiRepoScanRequest(BaseModel):
    """Programmatic repo-intake scan request: HTTPS remote + optional pin.

    ``commit_hash`` None means HEAD: the API pins it via staging
    ``git ls-remote`` before cloning, so the scan still runs on exact bytes.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    repo_url: str = ""
    commit_hash: str | None = None
    contract: str = ""


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

    sweep = max_passes > 1
    # LAW 4: log target key + pass depth only (never snippet bytes/contract).
    obs_log(
        _API_ASPECT,
        "scan_source.start",
        message="scan_source started",
        target=str(target)[:64],
        max_passes=max(1, min(4, int(max_passes))),
        sweep=sweep,
    )
    started = time.monotonic()
    with obs_trace(_API_ASPECT, "scan_source"):
        if sweep:
            result = await execute_sweep_scan(
                target, _emit, config=config, max_passes=max(1, min(4, max_passes))
            )
        else:
            result = await execute_purple_workflow(target, _emit, config=config)
    duration_ms = round((time.monotonic() - started) * 1000, 3)
    obs_log(
        _API_ASPECT,
        "scan_source.verdict",
        message="scan_source verdict",
        target=str(target)[:64],
        status=getattr(result, "status", "unknown"),
        pre_exit_code=getattr(result, "pre_exit_code", None),
        post_exit_code=getattr(result, "post_exit_code", None),
        regression_passed=bool(getattr(result, "regression_passed", False)),
        duration_ms=duration_ms,
    )
    obs_record_metric(_API_ASPECT, "scan_source.duration_ms", duration_ms, unit="ms")
    obs_record_metric(
        _API_ASPECT,
        f"scan_source.status.{getattr(result, 'status', 'unknown')}",
        1,
        unit="count",
    )
    return result


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

    # LAW 4: sizes + format + pass depth only (never blob bytes or contract).
    obs_log(
        _API_ASPECT,
        "scan_binary.start",
        message="scan_binary started",
        binary_format=getattr(spec, "binary_format", "unknown"),
        size_bytes=getattr(spec, "size_bytes", 0),
        max_passes=max(1, min(4, int(max_passes))),
    )
    started = time.monotonic()
    with obs_trace(_API_ASPECT, "scan_binary"):
        result = await execute_binary_sweep(
            spec, _emit, config=config, max_passes=max(1, min(4, max_passes))
        )
    duration_ms = round((time.monotonic() - started) * 1000, 3)
    obs_log(
        _API_ASPECT,
        "scan_binary.verdict",
        message="scan_binary verdict",
        target=getattr(result, "target", ""),
        status=getattr(result, "status", "unknown"),
        passes_completed=len(
            getattr(result, "pass_results", None) or getattr(result, "passes", None) or []
        ),
        duration_ms=duration_ms,
    )
    obs_record_metric(_API_ASPECT, "scan_binary.duration_ms", duration_ms, unit="ms")
    obs_record_metric(
        _API_ASPECT,
        f"scan_binary.status.{getattr(result, 'status', 'unknown')}",
        1,
        unit="count",
    )
    return result


def query_vault_stats(vault_dir: str | None = None) -> dict[str, Any]:
    """Redacted vault telemetry: counts + savings, never payload material."""
    from modules.intel.sms_vault import vault_stats

    return vault_stats(vault_dir)


def verify_receipt(candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate a VerdictReceipt / CycleReceipt digest without Docker.

    Structural-only check: schema conformance + sha256 shape + sane exit
    codes, plus the optional receipt-chain link. It never recomputes the
    digest from patch bytes, so it cannot confirm the patch the receipt
    claims. Returns {"valid": bool, "chain_ok": bool, ...}; never raises
    on malformed input. Docker evidence (not this function) is what earns
    a verdict: a broken chain link sets ``chain_ok`` False but never flips
    ``valid``.

    Chain semantics: the link binds re-attestation equality (a chained
    receipt re-attests the SAME patch, so a live ``prev_receipt_sha`` must
    equal this receipt's ``patch_sha256``). Production receipts are
    currently always-unlinked (genesis): no caller threads prev receipts
    today, so ``chain_ok`` is always False outside tests that hand-build a
    linked receipt.
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
    material, no model text) per LAW 4. Carries server ``ts`` for the
    WebUI v3 ``eventTime()`` ordering.
    """
    import time

    return {
        "team": "telemetry",
        "type": "log",
        "msg": (
            f"Telemetry: Raw {int(raw):,} -> Sent {int(sent):,} tokens "
            f"(Savings {float(savings_pct):.1f}%; novel {int(novel)}, "
            f"known {int(known)})"
        ),
        "ts": time.time(),
    }


def build_ingest_event(*, repo_url: str, sha: str) -> dict[str, str]:
    """HUD websocket event for a validated repo intake (Wave 6 HUD).

    Returns ``{"team": "ingest", "type": "log", "msg": ...}`` for
    ``writeLine``. LAW 4: the URL is redacted to host + short commit sha —
    credentials, userinfo, paths, and query strings never reach the wire,
    so ``msg`` contains no ``@``. Carries server ``ts`` for v3 ordering.
    """
    import time

    try:
        host = urlparse(str(repo_url)).hostname or "unknown-host"
    except (ValueError, AttributeError, TypeError):
        host = "unknown-host"
    short_sha = str(sha or "")[:12]
    return {
        "team": "ingest",
        "type": "log",
        "msg": f"Ingest: {host} {short_sha}",
        "ts": time.time(),
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


def summarize_cycle_evidence(result: dict[str, Any] | Any) -> list[dict[str, Any]]:
    """Per-cycle [{cycle, pre_exit, post_exit, gates, verdict}] (pure, no I/O).

    Missing cycles -> []. Gates that did not run read None (skip): only
    Docker evidence decides verdicts.
    """
    if isinstance(result, Mapping):
        items = result.get("cycle_reports") or result.get("cycles")
    elif result is None:
        items = None
    else:
        items = getattr(result, "cycle_reports", None) or getattr(result, "cycles", None)
    rows: list[dict[str, Any]] = []
    for entry in items if isinstance(items, (list, tuple)) else []:
        node = entry.model_dump() if hasattr(entry, "model_dump") else entry
        if not isinstance(node, Mapping):
            continue
        try:
            receipt = node.get("receipt")
            receipt = receipt.model_dump() if hasattr(receipt, "model_dump") else receipt
            receipt = receipt if isinstance(receipt, Mapping) else {}
            ver = node.get("evidence")
            ver = ver.model_dump() if hasattr(ver, "model_dump") else ver
            patched = ver.get("patched_verification") if isinstance(ver, Mapping) else None
            patched = patched if isinstance(patched, Mapping) else {}
            gates: dict[str, bool | None] = {}
            for name, key in (("mutation", "mutations"), ("property", "properties")):
                n = patched.get(key)
                c = n.get("exit_code") if isinstance(n, Mapping) else getattr(n, "exit_code", None)
                try:
                    gates[name] = None if c is None else int(c) == 0
                except (TypeError, ValueError):
                    gates[name] = False
            if gates["property"] is None:
                p = receipt.get("property_passed")
                gates["property"] = None if p is None else bool(p)
            rep = patched.get("repeat_regression")
            reg = patched.get("regression")
            gates["repeat"] = None
            if rep is not None:
                f = (
                    reg.get("exit_code")
                    if isinstance(reg, Mapping)
                    else getattr(reg, "exit_code", None)
                )
                s = (
                    rep.get("exit_code")
                    if isinstance(rep, Mapping)
                    else getattr(rep, "exit_code", None)
                )
                try:
                    gates["repeat"] = (
                        (int(f) == int(s)) if f is not None and s is not None else False
                    )
                except (TypeError, ValueError):
                    gates["repeat"] = False
            pre = receipt.get("pre_probe_exit", receipt.get("pre_exit_code"))
            post = receipt.get("post_probe_exit", receipt.get("post_exit_code"))
            row = {"cycle": node.get("cycle"), "pre_exit": pre, "post_exit": post}
            row.update(gates=gates, verdict=node.get("status"))
            rows.append(row)
        except Exception:
            continue
    return rows


def summarize_cycle_receipts(report: dict[str, Any] | Any) -> list[dict[str, Any]]:
    """Per-cycle receipts from a report mapping (pure, no I/O)."""
    items = (
        (report.get("cycle_reports") or report.get("cycles"))
        if isinstance(report, Mapping)
        else None
    )
    out: list[dict[str, Any]] = []
    for entry in items if isinstance(items, (list, tuple)) else []:
        node = entry.model_dump() if hasattr(entry, "model_dump") else entry
        if not isinstance(node, Mapping):
            continue
        receipt = node.get("receipt")
        if hasattr(receipt, "model_dump"):
            try:
                receipt = receipt.model_dump()
            except Exception:
                continue
        if isinstance(receipt, Mapping) and receipt:
            out.append(dict(receipt))
    return out


def summarize_intel_provenance(records: Any) -> list[dict[str, Any]]:
    """Summarize which intel grounded a finding: one row per record.

    Pure function (parity W1): accepts ResearchRecord objects or their
    dict dumps, returns [{source, cve_id, summary_snippet, epss, kev}].
    Only allowlisted fields are copied into the output — payload/blob/
    key/secret material on the input (including inside ``extra``) is
    never propagated. Never raises on hostile shapes: non-list input
    yields [], unrecognized items are skipped.
    """
    if not isinstance(records, list):
        return []
    out: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict):
            source = item.get("source", "")
            cve_id = item.get("cve_id", "")
            summary = item.get("summary", "")
            extra = item.get("extra", {})
        elif hasattr(item, "source"):
            source = getattr(item, "source", "")
            cve_id = getattr(item, "cve_id", "")
            summary = getattr(item, "summary", "")
            extra = getattr(item, "extra", {})
        else:
            continue
        if not isinstance(extra, dict):
            extra = {}
        epss = extra.get("epss", "") or extra.get("epss_percentage", "")
        snippet = " ".join(str(summary or "").split())[:160]
        out.append(
            {
                "source": str(source or "")[:32],
                "cve_id": str(cve_id or "")[:32],
                "summary_snippet": snippet,
                "epss": str(epss or "")[:32],
                "kev": bool(extra.get("kev_listed", False)),
            }
        )
    return out


def list_vault_namespaces(vault_dir: str | None = None) -> list[dict[str, Any]]:
    """Browse vault namespaces: names + record counts, never payloads.

    Parity W1 (LAW 4): returns ``[{"namespace": ..., "record_count": ...}]``
    for namespaces holding at least one record. Namespace names are fixed
    enum values; payloads, keys, and blobs never leave the vault. A missing
    or empty vault dir yields ``[]`` — fail-closed in the browse sense:
    there is simply nothing to list, and no key material is created to
    answer the question.
    """
    from pathlib import Path

    from modules.intel.sms_vault import VaultNamespace, default_vault_dir

    base = Path(vault_dir) if vault_dir is not None else default_vault_dir()
    namespaces: list[dict[str, Any]] = []
    for namespace in VaultNamespace:
        try:
            count = len(list((base / namespace.value).glob("*.vault")))
        except OSError:
            count = 0
        if count:
            namespaces.append({"namespace": namespace.value, "record_count": count})
    # LAW 4: fixed enum names only — never payloads, keys, or blobs.
    obs_log(
        _API_ASPECT,
        "vault.browse.result",
        message="vault browse finished",
        operation="list_namespaces",
        namespaces=[entry["namespace"] for entry in namespaces],
    )
    return namespaces


def replay_vault_record(
    vault_dir: str | None,
    namespace: str,
    record_id: str,
) -> dict[str, Any]:
    """Replay one vault record as a redacted summary (LAW 4).

    Returns ``{"id", "fingerprint_prefix", "status", "created"}``: the
    record id (opaque handle), the first 12 hex chars of its one-way
    fingerprint digest, a fixed status string, and the blob mtime. The
    payload, blob bytes, and key material are never returned or logged.

    Fail closed: unknown namespace, malformed id, missing record, or an
    undecryptable blob raises ``ValueError`` (``VaultError`` already is
    one; ``OSError``/``KeyError`` surface as ``ValueError`` so callers
    handle a single refusal type).
    """
    import re
    from pathlib import Path

    from modules.intel.sms_vault import (
        VaultError,
        VaultNamespace,
        decrypt_blob,
        default_vault_dir,
        load_or_create_key,
    )

    if isinstance(namespace, VaultNamespace):
        parsed = namespace
    else:
        try:
            parsed = VaultNamespace(str(namespace))
        except ValueError as exc:
            raise ValueError(f"Unknown vault namespace: {namespace!r}.") from exc
    record_key = str(record_id)
    if not re.fullmatch(r"[0-9a-f]{32}", record_key):
        raise ValueError("Malformed vault record id; refusing to replay.")
    base = Path(vault_dir) if vault_dir is not None else default_vault_dir()
    blob_path = base / parsed.value / f"{record_key}.vault"
    try:
        raw = blob_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Unknown vault record in namespace {parsed.value!r}.") from exc
    try:
        stored = decrypt_blob(raw, key=load_or_create_key(base))
    except VaultError as exc:
        raise ValueError(f"Vault record failed authentication ({type(exc).__name__}).") from exc
    fingerprint = stored.get("fingerprint", "")
    if not isinstance(fingerprint, str):
        fingerprint = ""
    try:
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(blob_path.stat().st_mtime))
    except OSError:
        created = ""
    summary = {
        "id": record_key,
        "fingerprint_prefix": fingerprint[:12],
        "status": "KNOWN_ARCHETYPE" if fingerprint else "NOVEL_SURFACE",
        "created": created,
    }
    # LAW 4: fixed enum name + status only — never payloads, keys, or blobs.
    obs_log(
        _API_ASPECT,
        "vault.replay.result",
        message="vault replay finished",
        operation="replay",
        namespace=parsed.value,
        status=summary["status"],
    )
    return summary


def docker_health(config: PurpleBoxConfig | None = None, *, client: Any = None) -> dict[str, Any]:
    """Library parity for CLI ``--docker-status`` (W2 ops visibility).

    Same shape as the ``docker_report`` in ``main._health_report``:
    ``{"state", "missing_images", "leftover_containers"}``. Delegates to
    ``modules.core.docker_manager.docker_status``, which never raises: a
    daemon-unreachable client reads ``state: unavailable`` (fail closed).
    ``client`` is an injected docker client (tests); ``None`` uses the
    real daemon.
    """
    from modules.core.docker_manager import docker_status

    if config is None:
        try:
            config = load_config()
        except ConfigurationError:
            # Read-only helper: still answer, fail closed, flag the cause.
            return {
                "state": "unavailable",
                "missing_images": [],
                "leftover_containers": 0,
                "configuration_error": True,
            }
    return docker_status(config, client=client)


def cleanup_preview(config: PurpleBoxConfig | None = None, *, client: Any = None) -> dict[str, Any]:
    """Dry-run for CLI ``--cleanup``: LIST what would be removed, remove nothing.

    Mirrors the label scoping of ``remove_stale_resources`` (session
    containers, session networks, clone-cache snapshot images) but never
    calls ``remove`` on anything. Fail-closed per scope: a dead daemon
    mid-list yields empty lists instead of raising.
    """
    if config is None:
        try:
            config = load_config()
        except ConfigurationError:
            return {"containers": [], "networks": [], "images": [], "configuration_error": True}
    settings = config
    if client is None:
        try:
            import docker as _docker

            client = _docker.from_env(timeout=60)
        except Exception:
            return {"containers": [], "networks": [], "images": []}
    label = {"label": "purplebox.session"}
    try:
        containers = client.containers.list(all=True, filters=label)
    except Exception:
        containers = []
    try:
        networks = client.networks.list(filters=label)
    except Exception:
        networks = []
    try:
        snapshots = client.images.list(name=settings.clone_repo_prefix)
    except Exception:
        snapshots = []
    return {
        "containers": [getattr(c, "name", None) or str(getattr(c, "id", "?")) for c in containers],
        "networks": [getattr(n, "name", None) or str(getattr(n, "id", "?")) for n in networks],
        "images": [str(getattr(i, "id", "?")) for i in snapshots],
    }


def effective_knobs(config: PurpleBoxConfig | None = None) -> dict[str, Any]:
    """Effective inference/verifier knob values (parity wave W2).

    These knobs live in env only (``META_MUSE_TIMEOUT_SECONDS``,
    ``META_MUSE_MAX_TOKENS``, ``META_MUSE_REASONING_EFFORT``,
    ``PURPLEBOX_VERIFIER_TIMEOUT_SECONDS``, ``PURPLEBOX_RESEARCH_SCANNERS``)
    and change scan behaviour while appearing in no ``--help`` and no API.
    This function surfaces the resolved values: it reads a passed config
    (default: the live :func:`load_config`) and returns plain values.
    Pure read: the config object is never mutated.
    """
    if config is None:
        from library.core.config import load_config

        config = load_config()
    return {
        "timeout_seconds": config.api_timeout_seconds,
        "max_tokens": config.max_output_tokens,
        "reasoning_effort": config.reasoning_effort,
        "verifier_timeout": config.verifier_timeout_seconds,
        "research_scanners": list(config.research_scanners),
    }


def showcase_status(root: Any = None) -> dict[str, Any]:
    """Static presence report for the standalone showcase rig (parity W2).

    The showcase rig (TTS booth, desktop capture, music DSP,
    ``video-demo/render_demo.sh``) is deliberately standalone with zero
    product wiring; this function only acknowledges it exists. Static
    presence checks via file existence plus ``bash -n`` on
    ``render_demo.sh``: fast, no execution, no servers started. Fail
    closed: a missing ``root`` override reports absent everywhere and
    never raises.
    """
    import subprocess
    from pathlib import Path

    try:
        base = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    except Exception:  # noqa: BLE001 - fail closed, never raise
        base = Path(__file__).resolve().parents[2]
    demo = base / "video-demo"

    tts_port = 8002  # video-demo/TTSServer/server.py DEFAULT_PORT (static; not imported)
    tts_present = (demo / "TTSServer" / "server.py").is_file()

    _capture_rels = (
        "video-demo/desktop-capture/gamescope/launch_sandbox.sh",
        "video-demo/desktop-capture/pipewire/setup_audio_sink.sh",
        "video-demo/desktop-capture/pipewire/teardown_audio_sink.sh",
        "video-demo/desktop-capture/deskcap/Makefile",
        "video-demo/desktop-capture/deskcap/pwcam_desktop.c",
    )
    scripts = [rel for rel in _capture_rels if (base / rel).is_file()]

    _final_bed_rel = "video-demo/music-generation/cinematic_cybersec_epic_FINAL.py"
    _final_bed = base / _final_bed_rel
    music_present = _final_bed.is_file()

    _render_rel = "video-demo/render_demo.sh"
    _render_path = base / _render_rel
    script_present = _render_path.is_file()
    bash_syntax_ok = False
    if script_present:
        try:
            proc = subprocess.run(
                ["bash", "-n", str(_render_path)],
                capture_output=True,
                timeout=15,
            )
            bash_syntax_ok = proc.returncode == 0
        except Exception:  # noqa: BLE001 - fail closed (no bash? syntax unknown)
            bash_syntax_ok = False

    return {
        "tts": {
            "present": bool(tts_present),
            "port": tts_port,
            "health_url": f"http://127.0.0.1:{tts_port}/healthz",
        },
        "capture": {"present": bool(scripts), "scripts": scripts},
        "music": {
            "present": bool(music_present),
            "final_bed": _final_bed_rel if music_present else None,
        },
        "render": {
            "script_present": bool(script_present),
            "bash_syntax_ok": bool(bash_syntax_ok),
        },
    }


_LS_REMOTE_SCRIPT = (
    "git -c protocol.allow=never -c protocol.https.allow=always "
    '-c submodule.recurse=false ls-remote -- "$1" HEAD'
)
_HEAD_HEX = frozenset("0123456789abcdefABCDEF")


def _repo_host_prefix(repo_url: object, commit_hash: object | None = None) -> str:
    """LAW 4 redaction: host + short commit only, never the URL."""
    try:
        host = urlparse(str(repo_url)).hostname or str(repo_url)
    except Exception:
        host = str(repo_url)
    prefix = str(commit_hash or "")[:12] if commit_hash else "(HEAD)"
    return f"repo host {host!r} at commit {prefix}"


def _resolve_head_commit(repo_url: str, sandbox, *, timeout_seconds: int = 60) -> str:
    """Pin HEAD via a staging ``git ls-remote`` container (clone=True needs a pin).

    Same LAW 4 isolation shape as the intake clone: the URL rides as a
    positional ``sh -c`` argument (``$1``, never interpolated), bridge
    network for the fetch only, no host mounts, bounded pids/mem/cpu,
    read-only with all capabilities dropped and ``no-new-privileges``.
    Fail closed: non-zero exit, unreadable output, or no 40-hex HEAD line
    raises ``ValueError`` naming the host only.
    """
    client = getattr(sandbox, "client", None)
    if client is None:
        raise ValueError("HEAD resolution requires a sandbox with a Docker client")
    configured = getattr(getattr(sandbox, "config", None), "target_base_image", None)
    image = configured if isinstance(configured, str) and configured else "sms-target"
    where = _repo_host_prefix(repo_url)
    container = client.containers.run(
        image,
        command=["sh", "-c", _LS_REMOTE_SCRIPT, "sh", repo_url],
        detach=True,
        network_mode="bridge",
        user="10001",
        working_dir="/work",
        tmpfs={"/work": "rw,nosuid,nodev,size=64m,uid=10001,gid=10001,mode=0700"},
        environment={
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": "/work",
        },
        pids_limit=128,
        mem_limit="512m",
        nano_cpus=1_000_000_000,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        read_only=True,
        entrypoint=[],
    )
    try:
        try:
            status = container.wait(timeout=timeout_seconds)
        except Exception:
            raise ValueError(
                f"staging ls-remote failed (timeout or wait error) for {where}"
            ) from None
        code = status.get("StatusCode", 1) if isinstance(status, dict) else 1
        if code != 0:
            raise ValueError(f"staging ls-remote failed for {where} (exit {code})")
        try:
            raw = container.logs()
        except Exception as exc:
            raise ValueError(f"staging ls-remote unreadable for {where}") from exc
        text = (
            bytes(raw).decode("ascii", errors="strict")
            if isinstance(raw, (bytes, bytearray))
            else str(raw)
        )
        sha = ""
        for line in text.splitlines():
            parts = line.split()
            if (
                len(parts) >= 2
                and parts[1] == "HEAD"
                and len(parts[0]) == 40
                and all(char in _HEAD_HEX for char in parts[0])
            ):
                sha = parts[0].lower()
                break
        if not sha:
            raise ValueError(f"staging ls-remote returned no HEAD pin for {where}")
        return sha
    finally:
        try:
            container.remove(force=True)
        except Exception:
            pass


async def scan_repo(
    repo_url: str,
    emit: Callable[[str, str], Awaitable[None] | None] | None = None,
    *,
    commit_hash: str | None = None,
    contract: str = "",
    config: PurpleBoxConfig | None = None,
    timeout_s: float | None = None,
):
    """Run the evidence-gated project loop over a remote repo (D7 surface).

    Separate-project surface: validates via ``RepoIntakeSpec`` (``commit_hash``
    None means HEAD, pinned first through a staging ``git ls-remote`` so the
    scan still runs on exact bytes), clones inside Docker staging via
    ``intake_repo_to_snapshot(..., clone=True)``, materializes the staged
    tree into an owner-only temp dir, detects the runtime, and delegates to
    ``execute_project_workflow`` with a caller-contract ``ProjectSpec``.
    Returns the raw project result, same as the project scan path.

    No ``main`` import by design (main imports this module: importing it
    back would be a cycle): the snapshot-to-ProjectSpec mapping is inline
    here, following the shape of ``main._ingest_repo_to_project``.

    D3: ``allow_remote_inference=True`` is set on the built spec because
    this explicit call IS the consent grant. LAW 4: the URL is redacted to
    host + short commit in every message, log, and error — never the URL.
    """
    # Lazy imports: this module is imported by main at top level, so the
    # heavier workflow/sandbox pieces stay function-local (same convention
    # as scan_source/scan_binary).
    from modules.core.config import require_api_key
    from modules.core.docker_manager import DockerSandboxManager
    from modules.services.repo_intake import (
        RepoIntakeSpec,
        detect_runtime,
        intake_repo_to_snapshot,
    )
    from modules.workflows.project_workflow import (
        execute_project_workflow,
        validate_safe_path,
    )

    request = ApiRepoScanRequest.model_validate(
        {"repo_url": repo_url, "commit_hash": commit_hash, "contract": contract or ""}
    )
    settings = config or load_config()
    if timeout_s is not None:
        if not 0 <= timeout_s <= 3600:
            raise ValueError("timeout_s must be 0 (no timeout) or 1-3600.")
        settings = settings.__class__(**{**settings.__dict__, "api_timeout_seconds": timeout_s})
    require_api_key(settings)

    async def _emit(team: str, message: str) -> None:
        if emit is None:
            return
        outcome = emit(team, message)
        if isinstance(outcome, Awaitable):
            await outcome

    try:
        host = urlparse(str(request.repo_url)).hostname or "unknown-host"
    except (ValueError, AttributeError, TypeError):
        host = "unknown-host"
    # LAW 4: host + commit prefix only (never the URL or the contract).
    obs_log(
        _API_ASPECT,
        "scan_repo.start",
        message="scan_repo started",
        host=str(host)[:64],
        commit_prefix=str(request.commit_hash or "")[:12] or "HEAD",
    )
    started = time.monotonic()
    with obs_trace(_API_ASPECT, "scan_repo"):
        manager = DockerSandboxManager(settings)
        pin = request.commit_hash
        if pin is None:
            pin = _resolve_head_commit(request.repo_url, manager)
        try:
            spec = RepoIntakeSpec(url=request.repo_url, commit_hash=pin)
        except ValueError as exc:
            raise ValueError(
                f"invalid repo intake ({exc}); {_repo_host_prefix(request.repo_url, pin)}"
            ) from exc
        try:
            snapshot = intake_repo_to_snapshot(
                spec,
                ["true"],
                file_list=None,
                clone=True,
                sandbox=manager,
            )
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(
                "repo-intake scan refused: staging clone failed for "
                f"{_repo_host_prefix(spec.url, spec.commit_hash)}"
            ) from exc
        tree = {
            key[5:]: value
            for key, value in dict(snapshot.files or {}).items()
            if key.startswith("tree/")
        }
        if not tree:
            raise ValueError(
                "repo-intake scan refused: empty staged tree for "
                f"{_repo_host_prefix(spec.url, spec.commit_hash)}"
            )
        import tempfile
        from pathlib import Path

        staged = Path(tempfile.mkdtemp(prefix="sms-scan-repo-")).resolve()
        staged.chmod(0o700)
        for rel, content in tree.items():
            # Untrusted remote bytes: never let absolute paths or ".."
            # escape the staged dir (defense in depth over the intake strip).
            clean = rel.lstrip("/").replace("\\", "/")
            parts = [part for part in clean.split("/") if part not in ("", ".", "..")]
            if not parts:
                continue
            safe_rel = "/".join(parts)
            try:
                validate_safe_path(safe_rel)
            except ValueError as exc:
                raise ValueError(
                    "repo-intake scan refused: unsafe staged path for "
                    f"{_repo_host_prefix(spec.url, spec.commit_hash)}"
                ) from exc
            dest = staged.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(
                content if isinstance(content, bytes) else str(content).encode("utf-8")
            )
        runtime = detect_runtime(
            sorted(tree),
            str(spec.url).rstrip("/").rsplit("/", 1)[-1].removesuffix(".git"),
        )
        contract_text = (request.contract or "").strip() or (
            f"Ingest scan of {spec.url} at commit {spec.commit_hash[:12]}. "
            "Preserve the public API. Only sanitize untrusted input."
        )
        from modules.services.projects import ProjectSpec

        project = ProjectSpec.model_validate(
            {
                "path": str(staged),
                "command": runtime,
                "test_command": list(runtime),
                "contract": contract_text[:32_768],
                "scan_profile": "custom",
                "cycles": 1,
                # D3: this explicit scan_repo call IS the remote-inference grant.
                "allow_remote_inference": True,
            }
        )
        result = await execute_project_workflow(project, _emit, config=settings)
    duration_ms = round((time.monotonic() - started) * 1000, 3)
    obs_log(
        _API_ASPECT,
        "scan_repo.verdict",
        message="scan_repo verdict",
        host=str(host)[:64],
        status=getattr(result, "status", "unknown"),
        duration_ms=duration_ms,
    )
    obs_record_metric(_API_ASPECT, "scan_repo.duration_ms", duration_ms, unit="ms")
    obs_record_metric(
        _API_ASPECT,
        f"scan_repo.status.{getattr(result, 'status', 'unknown')}",
        1,
        unit="count",
    )
    return result
