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

    Each Wave 2 producer (agents 1-4) may or may not have landed its fields
    yet; every accessor below degrades to "Not reported" on missing or
    odd-shaped values and never raises. Keys probed (all optional):
    ``verdict_receipt`` (item 1: fixture/pre/post/regression/differential/
    properties/patch_hash dict or object), ``guard_rationales`` (item 2:
    list of {guard, protected_line, reason}), ``mutation_evidence`` (item 4:
    {mutations, failures, verdict} dict or object), and fast-lane topping
    (item 3: ``fast_lane_top`` string, else first ``vulnerabilities`` entry
    with reach_score/reach_evidence). No probe scripts or payloads surface.
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
        return {}

    # Item 1: execution-oracle verdict receipt.
    try:
        receipt = _as_dict(_field("verdict_receipt"))
        if receipt:
            parts = []
            fixture = receipt.get("fixture") or receipt.get("target")
            if fixture:
                parts.append(str(fixture)[:64])
            pre = receipt.get("pre_exit_code")
            post = receipt.get("post_exit_code")
            if pre is not None or post is not None:
                parts.append(f"probe {pre}/{post}")
            for key in ("regression", "differential", "properties"):
                val = receipt.get(key)
                if val:
                    parts.append(f"{key} {val}")
            patch_hash = receipt.get("patch_hash") or receipt.get("patch_sha")
            if patch_hash:
                parts.append(f"hash {str(patch_hash)[:16]}")
            if parts:
                facts["receipt"] = " · ".join(parts)[:200]
    except Exception:
        pass

    # Item 2: sanitization-guard rationale export.
    try:
        rationales = _field("guard_rationales")
        if rationales is None:
            rationales = _field("guard_evidence")
        items = list(rationales) if isinstance(rationales, (list, tuple)) else []
        shown = []
        for item in items[:3]:
            row = _as_dict(item) if not isinstance(item, str) else {}
            if isinstance(item, str):
                shown.append(item[:80])
                continue
            guard = row.get("guard") or row.get("rule") or row.get("check")
            line = row.get("protected_line") or row.get("line") or ""
            if guard:
                shown.append(f"{guard}: {line}"[:80] if line else str(guard)[:80])
        if shown:
            extra = f" +{len(items) - 3} more" if len(items) > 3 else ""
            facts["guard_rationales"] = "; ".join(shown)[:200] + extra
    except Exception:
        pass

    # Item 3: reachable+fixable fast-lane topping.
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
                score = first.get("reach_score")
                fixed = first.get("fixed_versions")
                fixed_str = ""
                if isinstance(fixed, (list, tuple)) and fixed:
                    fixed_str = f" fix {str(fixed[0])[:32]}"
                kev = " KEV" if first.get("kev_listed") else ""
                epss = first.get("epss_percentile")
                epss_str = f" EPSS {float(epss):.2f}" if isinstance(epss, (int, float)) else ""
                facts["fast_lane_top"] = f"{label} reach {score}{fixed_str}{kev}{epss_str}"[:200]
    except Exception:
        pass

    # Item 4: bounded mutation-count probes.
    try:
        mutation = _as_dict(_field("mutation_evidence"))
        if not mutation:
            mutation = _as_dict(_field("mutations"))
        if mutation:
            total = mutation.get("mutations") or mutation.get("count") or mutation.get("total")
            failures = mutation.get("failures") or mutation.get("failed") or 0
            verdict = mutation.get("verdict") or mutation.get("status") or ""
            try:
                facts["mutations"] = f"{int(failures)}/{int(total)} failed"
            except (TypeError, ValueError):
                facts["mutations"] = str(verdict)[:80] or "reported"
            if verdict:
                facts["mutations"] = f"{facts['mutations']} ({verdict})"[:200]
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
