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
    "research",
    "research_scanners",
    "allow_remote_inference",
    "offline_cve",
    "deep_assessment",
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
    if exit_code is None:
        return "Not reported"
    return f"Exit {exit_code}"


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
    rows = [
        ("Target", facts["target"]),
        ("Status", status_color(facts["status"], use_color)),
        ("Message", facts["message"]),
        ("Baseline", facts["baseline"]),
        ("Pre-probe", facts["pre_probe"]),
        ("Post-probe", facts["post_probe"]),
        ("Regression", facts["regression"]),
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
    lines.append(f"Total tokens: {total}, estimated cost: {total_str}")
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
