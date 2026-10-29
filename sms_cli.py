# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Non-interactive CLI presentation: ANSI colors, stderr spinner, fact/usage tables.

Leaf module: stdlib only. LAW 4: tables carry facts and exit codes only;
probe scripts, payloads, and keys never reach this layer (inputs are
already-redacted workflow result objects).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 fallback; project runs 3.12+.
    tomllib = None  # type: ignore[assignment]

CONFIG_KEY = "sms"

# Exec-audience mirror of main.CAPABILITIES_EPILOG (import-safe: same lines,
# no new flags). Used by sms help text and tui help overlay.
CAPABILITIES_TEXT = (
    "Same-day value (Wave 2/5/8, all in the default scan, no extra flags):\n"
    "  receipts: receipt.json proves what the sandbox actually ran (probe exits + patch hash).\n"
    "  rationale: guard rationales show why each patch guard fired, in plain words.\n"
    "  topping: fast-lane topping lists the most reachable + fixable CVE first (--fast-lane).\n"
    "  mutations: mutation probes confirm the fix still holds under small input changes.\n"
    "  freshness: freshness stamps show the intel was fetched live today, not cached.\n"
    "  templates: template-shaped patches stay inside the small-edit guard budget.\n"
    "  stale token: KEV/EPSS signals older than 1 day render as stale:<date> so old intel never outranks fresh.\n"
    "  repeat-stability: repeat-stability re-runs the check so a flaky pass cannot verify."
)


def capabilities_text() -> str:
    """One-line-per-capability exec summary of Wave 2/5/8 same-day value."""
    return CAPABILITIES_TEXT


# Flag > config > env precedence merges only these CLI-owned keys.
CONFIG_KEYS = (
    "profile",
    "scan_profile",
    "cycles",
    "red_agents",
    "blue_agents",
    "context_budget",
    "intel_theme",
    "intel_offline",
    "build_brief",
    "vulns",
    "demo_size",
    "flaw_count",
    "demo_seed",
    "research",
    "research_scanners",
    "allow_remote_inference",
    "offline_cve",
    "deep_assessment",
    "fast_lane",
    "output_dir",
    "port",
    "format",
)

ENV_FALLBACKS = {
    "research": "PURPLEBOX_RESEARCH",
    "research_scanners": "PURPLEBOX_RESEARCH_SCANNERS",
    "intel_offline": "PURPLEBOX_INTEL_OFFLINE",
}

_ALLOWED_FORMATS = ("table", "json")


class LoadError(ValueError):
    """A config file is unreadable, malformed, or carries unknown keys."""


def _coerce_value(key: str, value: object) -> object:
    if key in (
        "research",
        "intel_offline",
        "allow_remote_inference",
        "deep_assessment",
        "offline_cve",
        "fast_lane",
    ):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("1", "true", "yes", "on"):
                return True
            if lowered in ("0", "false", "no", "off"):
                return False
        raise LoadError(f"Config key {key!r} must be a boolean.")
    if key in ("cycles", "red_agents", "blue_agents", "context_budget", "port"):
        if isinstance(value, bool) or not isinstance(value, int):
            raise LoadError(f"Config key {key!r} must be an integer.")
        return value
    if key in ("flaw_count", "demo_seed"):
        # None (absent) or plain ints only; never raise on garbage from the
        # file — fall back to None and let the CLI/WS clamps bound the rest.
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value
    if not isinstance(value, str):
        raise LoadError(f"Config key {key!r} must be a string.")
    return value


def load_config_file(path: str | Path) -> dict:
    """Load [sms] table (TOML) or {"sms": {...}} (JSON). Unknown keys error."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LoadError(f"Cannot read config file {path}: {exc}") from exc
    data: object = None
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LoadError(f"Config file {path} is not valid JSON: {exc}") from exc
    else:
        if tomllib is None:
            raise LoadError("TOML config requires Python 3.11+ (tomllib).")
        try:
            data = tomllib.loads(text)
        except (tomllib.TOMLDecodeError, ValueError) as exc:
            # A JSON file with a .toml suffix decodes as neither; offer the JSON path.
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                raise LoadError(f"Config file {path} is not valid TOML: {exc}") from exc
    if not isinstance(data, dict):
        raise LoadError(f"Config file {path} must hold a top-level table/object.")
    section = data.get(CONFIG_KEY, data) if isinstance(data, dict) else {}
    if not isinstance(section, dict):
        raise LoadError(f"Config file {path} [{CONFIG_KEY}] must be a table/object.")
    cleaned: dict = {}
    for key, value in section.items():
        if key not in CONFIG_KEYS:
            raise LoadError(f"Unknown config key {key!r} in {path}.")
        cleaned[key] = _coerce_value(key, value)
    if "format" in cleaned and cleaned["format"] not in _ALLOWED_FORMATS:
        raise LoadError("--format must be 'table' or 'json'.")
    return cleaned


def merge_config(env: dict | None, file_values: dict, flags: dict) -> dict:
    """Precedence: explicit CLI flags > config file > environment > default.

    `env` maps sms key -> value (defaults to process env lookups); `flags`
    carries only explicitly-passed CLI values; unset keys stay absent.
    """
    merged: dict = {}
    source = dict(env) if env is not None else _env_values()
    for key in CONFIG_KEYS:
        if key in flags and flags[key] not in (None, "", False):
            merged[key] = flags[key]
        elif key in file_values:
            merged[key] = file_values[key]
        elif key in source:
            merged[key] = source[key]
    if "format" in merged and merged["format"] not in _ALLOWED_FORMATS:
        raise LoadError("--format must be 'table' or 'json'.")
    return merged


def _env_values() -> dict:
    out: dict = {}
    if os.getenv("PURPLEBOX_RESEARCH", "off").strip().lower() == "on":
        out["research"] = True
    scanners = os.getenv("PURPLEBOX_RESEARCH_SCANNERS", "").strip()
    if scanners:
        out["research_scanners"] = scanners
    offline = os.getenv("PURPLEBOX_INTEL_OFFLINE", "").strip().lower()
    if offline in ("1", "true", "yes", "on"):
        out["intel_offline"] = True
    return out


# ---------- ANSI (NO_COLOR aware) ----------


def _color_enabled(use_color: bool | None = None) -> bool:
    if use_color is not None:
        return bool(use_color)
    if os.getenv("NO_COLOR") is not None:
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


_COLORS = {
    "reset": "\x1b[0m",
    "bold": "\x1b[1m",
    "green": "\x1b[32m",
    "red": "\x1b[31m",
    "yellow": "\x1b[33m",
    "cyan": "\x1b[36m",
    "dim": "\x1b[2m",
}


def paint(text: str, color: str, use_color: bool | None = None) -> str:
    """Wrap text in ANSI color unless NO_COLOR is set or color is disabled."""
    if not _color_enabled(use_color) or color not in _COLORS:
        return text
    return f"{_COLORS[color]}{text}{_COLORS['reset']}"


def status_color(status: str, use_color: bool | None = None) -> str:
    """Green for verified/no_findings/completed/ok, red for error, else yellow."""
    lowered = str(status or "").lower()
    if lowered in ("verified", "no_findings", "completed", "ok", "ready", "passed"):
        return paint(str(status), "green", use_color)
    if lowered in ("error", "failed"):
        return paint(str(status), "red", use_color)
    return paint(str(status), "yellow", use_color)


# ---------- stderr spinner/progress ----------


class Spinner:
    """Non-blocking stderr progress indicator; silent unless a TTY (or forced)."""

    FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self, message: str = "Scanning", enabled: bool | None = None, stream=None) -> None:
        self.message = message
        self.stream = stream or sys.stderr
        if enabled is None:
            try:
                enabled = bool(self.stream.isatty())
            except Exception:
                enabled = False
        self.enabled = bool(enabled)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "Spinner":
        if not self.enabled:
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def _spin(self) -> None:
        index = 0
        while not self._stop.is_set():
            frame = self.FRAMES[index % len(self.FRAMES)]
            try:
                self.stream.write(f"\r{frame} {self.message}…")
                self.stream.flush()
            except Exception:
                return
            index += 1
            time.sleep(0.08)
        try:
            self.stream.write("\r" + " " * (len(self.message) + 4) + "\r")
            self.stream.flush()
        except Exception:
            pass

    def update(self, message: str) -> None:
        """Swap the progress label mid-run (stderr only, never stdout)."""
        self.message = message

    def stop(self) -> None:
        """Halt the spinner and clear its line."""
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None


# ---------- fact + usage tables ----------


def _probe_label(exit_code: object) -> str:
    if exit_code == 0:
        return "Reached (exit 0)"
    if exit_code == 1:
        return "Blocked (exit 1)"
    if exit_code == 2:
        return "Inconclusive (exit 2)"
    if exit_code is None:
        return "Not reported"
    return f"Exit {exit_code}"


def format_wave2_facts(result: object, use_color: bool | None = None) -> dict:
    """Wave 2 items 1-4 fact rows (SPEC 14.8). Read-only defensive probes.

    REAL fields first (merged reality e76b019), guessed names fallback only:
    1. ``result.receipt``: VerdictReceipt (fixture/pre_exit_code/
       post_exit_code/regression_passed/differential_passed/patch_sha256),
       or ``cycle.receipt``: CycleReceipt (fixture/pre_probe_exit/
       post_probe_exit/baseline_regression_exit/patched_regression_exit/
       patch_sha256) on any entry of ``cycle_reports``/``cycles``.
       Legacy fallback: ``verdict_receipt`` dict.
    2. ``evidence.replacement_validation.guard_rationale``: GuardRationale
       (guard_id/reason/trigger) on any cycle evidence; also a top-level
       ``guard_rationale``. Legacy fallback: ``guard_rationales`` list.
    3. ``vulnerabilities[].queue_evidence`` auditable string
       (``reach:N fix:X kev:listed/absent epss:N.NN``); else first
       vulnerabilities entry reach/KEV/EPSS components. Legacy: fast_lane_top.
    4. ``patched_verification.mutations``/``pre_verification.mutations``:
       ExecutionEvidence (exit_code/output) on any cycle evidence; also
       top-level ``mutations`` ExecutionEvidence. Display parses ``N/M`` or
       exit verdict via mutation_gate_passed semantics (exit 0 held).
       Legacy fallback: ``mutation_evidence`` dict.
    Absent/odd-shaped values degrade to "Not reported"; never raises; no
    probe scripts or payloads surface.
    """
    _ = use_color  # rows are plain facts; color applied by fact_table caller
    facts = {
        "receipt": "Not reported",
        "guard_rationales": "Not reported",
        "fast_lane_top": "Not reported",
        "mutations": "Not reported",
    }
    get = lambda name, default=None: getattr(result, name, default)  # noqa: E731
    model_dump = getattr(result, "model_dump", None)
    dumped: dict = {}
    try:
        if callable(model_dump):
            maybe = model_dump()
            if isinstance(maybe, dict):
                dumped = maybe
    except Exception:
        dumped = {}

    def _field(name: str):
        value = get(name, None)
        if value is None and isinstance(dumped, dict):
            value = dumped.get(name)
        return value

    def _as_dict(value: object) -> dict:
        if isinstance(value, dict):
            return value
        to_dict = getattr(value, "model_dump", None)
        if callable(to_dict):
            try:
                maybe = to_dict()
                if isinstance(maybe, dict):
                    return maybe
            except Exception:
                pass
        try:
            namespace = vars(value)
            if isinstance(namespace, dict):
                return dict(namespace)
        except TypeError:
            pass
        return {}

    def _cycles() -> list:
        for name in ("cycle_reports", "cycles"):
            try:
                items = _field(name)
            except Exception:
                continue
            if isinstance(items, (list, tuple)) and items:
                return list(items)
        return []

    # Item 1: execution-oracle verdict receipt — REAL fields first.
    try:
        receipt = _as_dict(_field("receipt"))
        if not receipt:
            for cycle in _cycles():
                receipt = _as_dict(getattr(cycle, "receipt", None))
                if not receipt and isinstance(cycle, dict):
                    receipt = _as_dict(cycle.get("receipt"))
                if receipt:
                    break
        if not receipt:
            receipt = _as_dict(_field("verdict_receipt"))  # legacy fallback
        if receipt:
            parts = []
            fixture = receipt.get("fixture") or receipt.get("target")
            if fixture:
                parts.append(str(fixture)[:64])
            pre = receipt.get("pre_exit_code", receipt.get("pre_probe_exit"))
            post = receipt.get("post_exit_code", receipt.get("post_probe_exit"))
            if pre is not None or post is not None:
                parts.append(f"probe {pre}/{post}")
            reg = receipt.get("regression_passed")
            if reg is None:
                base = receipt.get("baseline_regression_exit")
                patched = receipt.get("patched_regression_exit")
                if base is not None or patched is not None:
                    parts.append(f"regression {base}/{patched}")
            elif reg:
                parts.append("regression passed")
            diff = receipt.get("differential_passed")
            if diff is True:
                parts.append("differential passed")
            prop = receipt.get("property_passed")
            if prop is True:
                parts.append("properties passed")
            elif receipt.get("property_exit_code") is not None:
                parts.append(f"properties exit {receipt.get('property_exit_code')}")
            patch_hash = (
                receipt.get("patch_sha256") or receipt.get("patch_hash") or receipt.get("patch_sha")
            )
            if patch_hash:
                parts.append(f"sha {str(patch_hash)[:16]}")
            for key in ("regression", "differential", "properties"):
                val = receipt.get(key)
                if val and f"{key} " not in " ".join(parts):
                    parts.append(f"{key} {val}")
            if parts:
                facts["receipt"] = " · ".join(parts)[:200]
    except Exception:
        pass

    # Item 2: sanitization-guard rationale export — REAL GuardRationale first.
    try:
        shown: list[str] = []

        def _guard_text(item: object) -> str | None:
            if isinstance(item, str):
                return item[:80] if item.strip() else None
            row = _as_dict(item)
            if not row:
                return None
            guard = row.get("guard_id") or row.get("guard") or row.get("rule") or row.get("check")
            line = row.get("trigger") or row.get("protected_line") or row.get("line") or ""
            reason = row.get("reason") or ""
            if not guard and not reason:
                return None
            head = f"{guard}: {line}"[:80] if line else str(guard or reason)[:80]
            if reason and guard and str(reason)[:40] not in head:
                head = f"{head} ({str(reason)[:40]})"[:80]
            return head

        top_guard = _field("guard_rationale")
        if top_guard is not None:
            text = _guard_text(top_guard)
            if text:
                shown.append(text)
        for cycle in _cycles():
            try:
                ev = getattr(cycle, "evidence", None)
                if ev is None and isinstance(cycle, dict):
                    ev = cycle.get("evidence")
                evd = _as_dict(ev)
                rv = _as_dict(evd.get("replacement_validation"))
                cand = rv.get("guard_rationale")
                if cand is None:
                    cand = evd.get("guard_rationale")
                text = _guard_text(cand) if cand is not None else None
                if text and text not in shown:
                    shown.append(text)
            except Exception:
                continue
            if len(shown) >= 3:
                break
        if not shown:
            rationales = _field("guard_rationales")
            if rationales is None:
                rationales = _field("guard_evidence")
            items = list(rationales) if isinstance(rationales, (list, tuple)) else []
            for item in items[:3]:
                text = _guard_text(item)
                if text:
                    shown.append(text)
            if len(items) > 3 and shown:
                shown[-1] = (shown[-1] + f" +{len(items) - 3} more")[:80]
        if shown:
            facts["guard_rationales"] = "; ".join(shown)[:200]
    except Exception:
        pass

    # Item 3: reachable+fixable fast-lane topping — REAL queue_evidence first.
    try:
        top = _field("fast_lane_top")
        if isinstance(top, str) and top.strip():
            facts["fast_lane_top"] = top.strip()[:200]
        else:
            vulns = _field("vulnerabilities")
            first = None
            if isinstance(vulns, (list, tuple)) and vulns:
                first = _as_dict(vulns[0]) if not isinstance(vulns[0], str) else {}
            if first:
                label = (
                    first.get("id") or (first.get("cves") or [None])[0]
                    if isinstance(first.get("cves"), list)
                    else first.get("id")
                )
                label = label or first.get("id") or "top vuln"
                queue_ev = first.get("queue_evidence")
                if isinstance(queue_ev, str) and queue_ev.strip():
                    facts["fast_lane_top"] = f"{label} {queue_ev.strip()}"[:200]
                else:
                    score = first.get("reach_score")
                    fixed = first.get("fixed_versions")
                    fixed_str = ""
                    if isinstance(fixed, (list, tuple)) and fixed:
                        fixed_str = f" fix {str(fixed[0])[:32]}"
                    kev = " KEV" if first.get("kev_listed") else ""
                    epss = first.get("epss_percentile")
                    epss_s = f" EPSS {float(epss):.2f}" if isinstance(epss, (int, float)) else ""
                    facts["fast_lane_top"] = f"{label} reach {score}{fixed_str}{kev}{epss_s}"[:200]
    except Exception:
        pass

    # Item 4: bounded mutation-count probes — REAL ExecutionEvidence first.
    try:
        mutation_text: str | None = None

        def _ev_text(ev: object) -> str | None:
            row = _as_dict(ev)
            if not row:
                return None
            exit_code = row.get("exit_code")
            output = str(row.get("output") or "")
            import re as _re

            match = _re.search(r"(\d+)\s*/\s*(\d+)", output)
            if match:
                verb = "held" if exit_code == 0 else "failed"
                return f"{match.group(0)} mutations {verb} (exit {exit_code})"[:200]
            if exit_code is not None:
                verb = "held" if exit_code == 0 else "failed"
                return f"mutations {verb} (exit {exit_code})"[:200]
            return None

        for cycle in _cycles():
            try:
                ev = getattr(cycle, "evidence", None)
                if ev is None and isinstance(cycle, dict):
                    ev = cycle.get("evidence")
                evd = _as_dict(ev)
                for section in ("patched_verification", "pre_verification"):
                    text = _ev_text(
                        evd.get(section, {}).get("mutations")
                        if isinstance(evd.get(section), dict)
                        else _as_dict(evd.get(section)).get("mutations")
                    )
                    if text:
                        mutation_text = text
                        break
                if mutation_text:
                    break
                direct = evd.get("mutations")
                if direct is not None:
                    text = _ev_text(direct)
                    if text:
                        mutation_text = text
                        break
            except Exception:
                continue
        if mutation_text is None:
            top_mut = _field("mutations")
            if top_mut is not None and not isinstance(top_mut, dict):
                mutation_text = _ev_text(top_mut)
            else:
                mutation = _as_dict(top_mut) if top_mut is not None else {}
                if not mutation:
                    mutation = _as_dict(_field("mutation_evidence"))  # legacy
                if mutation and "exit_code" in mutation:
                    mutation_text = _ev_text(mutation)
                elif mutation:
                    total = (
                        mutation.get("mutations") or mutation.get("count") or mutation.get("total")
                    )
                    failures = mutation.get("failures") or mutation.get("failed") or 0
                    verdict = mutation.get("verdict") or mutation.get("status") or ""
                    try:
                        mutation_text = f"{int(failures)}/{int(total)} failed"
                    except (TypeError, ValueError):
                        mutation_text = str(verdict)[:80] or "reported"
                    if verdict:
                        mutation_text = f"{mutation_text} ({verdict})"[:200]
        if mutation_text:
            facts["mutations"] = mutation_text[:200]
    except Exception:
        pass
    return facts


def format_facts(result: object, use_color: bool | None = None) -> dict:
    """Fact rows for a fixture or project result (already-redacted inputs only)."""
    get = lambda name, default=None: getattr(result, name, default)  # noqa: E731
    target = get("target", None) or get("project", "scan")
    facts = {
        "target": str(target),
        "status": str(get("status", "unknown")),
        "baseline": "Passed" if get("baseline_passed") else "Not passed",
        "pre_probe": _probe_label(get("pre_exit_code")),
        "post_probe": _probe_label(get("post_exit_code")),
        "regression": "Passed" if get("regression_passed") else "Not passed",
        "cleanup": "Resources removed" if get("cleanup_ok", get("cleanup")) else "Inspect Docker",
        "message": str(get("message", "")),
    }
    cycles = get("cycle_reports", None) or get("cycles", None) or []
    try:
        facts["cycles"] = str(len(list(cycles)))
    except TypeError:
        facts["cycles"] = "0"
    research = get("research_records", None) or []
    try:
        facts["research_records"] = str(len(list(research)))
    except TypeError:
        facts["research_records"] = "0"
    return facts


def fact_table(result: object, use_color: bool | None = None) -> str:
    """Aligned two-column fact table for terminal output."""
    facts = format_facts(result, use_color=use_color)
    try:
        wave2 = format_wave2_facts(result, use_color=use_color)
    except Exception:
        wave2 = {}
    rows = [
        ("Target", facts["target"]),
        ("Status", status_color(facts["status"], use_color)),
        ("Message", facts["message"]),
        ("Baseline", facts["baseline"]),
        ("Pre-probe", facts["pre_probe"]),
        ("Post-probe", facts["post_probe"]),
        ("Regression", facts["regression"]),
        ("Receipt", wave2.get("receipt", "Not reported")),
        ("Guard rationales", wave2.get("guard_rationales", "Not reported")),
        ("Fast-lane top", wave2.get("fast_lane_top", "Not reported")),
        ("Mutations", wave2.get("mutations", "Not reported")),
        ("Cycles", facts["cycles"]),
        ("Research records", facts["research_records"]),
        ("Cleanup", facts["cleanup"]),
        ("Capabilities", "run main.py --help for Wave 2/5/8 same-day value"),
    ]
    width = max(len(label) for label, _ in rows)
    lines = [paint("Scan facts", "bold", use_color)]
    for label, value in rows:
        lines.append(f"  {label.ljust(width)}  {value}")
    return "\n".join(lines)


def usage_table(result: object, use_color: bool | None = None) -> str:
    """Aligned per-call token/cost table (mirrors SUMMARY.md columns)."""
    usage = getattr(result, "usage", None)
    calls = list(getattr(usage, "calls", []) or [])
    header = f"{'Role':<8} {'Model':<22} {'In':>8} {'Out':>8} {'Seconds':>8} {'Cost USD':>10}"
    lines = [paint("Token and cost breakdown", "bold", use_color), header]
    for call in calls:
        cost = getattr(call, "cost_usd", None)
        cost_str = "unknown" if cost is None else f"{cost:.4f}"
        lines.append(
            f"{str(getattr(call, 'role', '?')):<8} "
            f"{str(getattr(call, 'model', '')):<22} "
            f"{int(getattr(call, 'prompt_tokens', 0)):>8} "
            f"{int(getattr(call, 'completion_tokens', 0)):>8} "
            f"{float(getattr(call, 'seconds', 0.0)):>8.1f} "
            f"{cost_str:>10}"
        )
    total = getattr(result, "total_tokens", 0)
    total_cost = getattr(result, "cost_usd", getattr(result, "total_cost_usd", None))
    total_str = "unknown" if total_cost is None else f"${total_cost:.4f}"
    try:
        total_fmt = f"{int(total):,}"
    except (TypeError, ValueError):
        total_fmt = str(total)
    lines.append(f"Total tokens: {total_fmt}, estimated cost: {total_str}")
    return "\n".join(lines)


def health_table(report: dict, use_color: bool | None = None) -> str:
    """Aligned readiness table for --health (no secrets; booleans only)."""
    rows = [
        ("Status", status_color(str(report.get("status", "unknown")), use_color)),
        ("Inference mode", str(report.get("inference_mode", "?"))),
        ("Inference ready", str(bool(report.get("inference_ready")))),
        ("API key configured", str(bool(report.get("api_key_configured")))),
        ("Red model", str(report.get("red_model", "?"))),
        ("Blue model", str(report.get("blue_model", "?"))),
        ("Docker", str((report.get("docker") or {}).get("state", "?"))),
        ("Busy", str(bool(report.get("busy")))),
    ]
    width = max(len(label) for label, _ in rows)
    lines = [paint("Secure Mitigation System health", "bold", use_color)]
    for label, value in rows:
        lines.append(f"  {label.ljust(width)}  {value}")
    return "\n".join(lines)
