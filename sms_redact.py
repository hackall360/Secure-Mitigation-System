# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Shared redaction for user-facing reports: dict-level, no model imports.

LAW 4: probe scripts, raw probe output, and exploit payloads never reach the
user. Both the fixture workflow and the project workflow redact through
these helpers; tests import EXPLOIT_REDACTED from here (re-exported by the
workflows for backward compatibility). Leaf module: only stdlib + typing.
"""

from __future__ import annotations

from typing import Any

EXPLOIT_REDACTED = "[exploit details withheld: available only inside the isolated verification sandbox]"

PROBE_OUTPUT_WITHHELD = (
    "[probe output withheld: available only inside the isolated verification sandbox]"
)

PROBE_TRUNCATED_SUFFIX = "\n[probe output truncated; full exploit output withheld]"

NORMAL_OUTPUT_SUFFIX = "\n[normal-input output truncated]"


def redact_probe_output(output: Any, limit: int = 500) -> Any:
    """Redact one probe output: keep exit codes upstream, drop payload text."""
    if not isinstance(output, str) or not output:
        return output
    if len(output) > limit:
        return output[:limit] + PROBE_TRUNCATED_SUFFIX
    return EXPLOIT_REDACTED


def redact_fixture_result(result: Any) -> dict:
    """User-safe fixture report: patch + exit codes only, no probe source or payloads."""
    data = result.model_dump()
    finding = data.get("finding")
    if isinstance(finding, dict):
        finding["verification_script_python"] = EXPLOIT_REDACTED
    for key in ("before", "after"):
        if isinstance(data.get("traces", {}).get(key), str):
            data["traces"][key] = PROBE_OUTPUT_WITHHELD
    for key in ("baseline", "regression", "after_probe_regression"):
        if isinstance(data.get("traces", {}).get(key), str):
            out = data["traces"][key]
            if len(out) > 2000:
                data["traces"][key] = out[:2000] + NORMAL_OUTPUT_SUFFIX
    return data


def _redact_candidate_list(items: Any) -> None:
    for item in items or []:
        for cand in item.get("candidates") or []:
            cand["verification_script_python"] = EXPLOIT_REDACTED
            cand["evidence"] = EXPLOIT_REDACTED


def redact_cycle_evidence(evidence: Any) -> dict:
    """Redact one cycle evidence dict: candidate scripts + probe outputs."""
    data = evidence.model_dump() if hasattr(evidence, "model_dump") else dict(evidence)
    red = data.get("red") or {}
    for key in ("batch_evidence", "evidence_digests"):
        _redact_candidate_list(red.get(key))
    report = red.get("report") or {}
    report["verification_script_python"] = EXPLOIT_REDACTED
    ired = data.get("independent_red") or {}
    for key in ("batch_evidence", "evidence_digests"):
        _redact_candidate_list(ired.get(key))
    ireport = ired.get("report") or {}
    if ireport:
        ireport["verification_script_python"] = EXPLOIT_REDACTED
    for section in ("pre_verification", "patched_verification", "independent_verification"):
        ver = data.get(section)
        if isinstance(ver, dict):
            probe = ver.get("probe") or {}
            # Keep exit codes and short status, drop raw probe output that may contain payloads.
            probe["output"] = redact_probe_output(probe.get("output", ""))
    return data


def redact_project_result(result: Any) -> dict:
    """User-safe project report: patched code only, no exploit scripts or payloads."""
    data = result.model_dump()
    data["cycle_reports"] = [
        {**cycle, "evidence": redact_cycle_evidence(cycle["evidence"])}
        if isinstance(cycle.get("evidence"), dict)
        else cycle
        for cycle in data.get("cycle_reports", [])
    ]
    # model_dump already expanded cycles alias; keep both consistent.
    data["cycles"] = data["cycle_reports"]
    history = []
    for item in data.get("verified_history", []):
        history.append({k: v for k, v in item.items()})
    data["verified_history"] = history
    return data
