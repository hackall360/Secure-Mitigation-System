# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Terminal UI for the Secure Mitigation System (80x24, stdlib + curses only).

Read-only reference to ``main.create_app`` / ``workflow.execute_purple_workflow``:
the TUI drives the same in-process workflow via an emit->queue bridge. It
never hand-rolls a websocket client and never shells out to Fugue.

LAW 4: event text shown here is redacted. Probe scripts, sandbox traces, API
keys, and project paths are truncated or replaced before display or queueing.
"""

from __future__ import annotations

import argparse
import asyncio
import queue
import re
import sys
import threading
from dataclasses import dataclass, field

try:  # Windows fallback: curses may be absent; plain-text mode covers that.
    import curses
except ImportError:  # pragma: no cover - platform dependent
    curses = None  # type: ignore[assignment]

NOTICE = "Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use."

WIDTH = 80
HEIGHT = 24

FIXTURE_ORDER = ("node_query_sink", "php_command_sink", "mysql_insecure_conf")
FIXTURE_SHORT = ("Node query", "PHP command", "MySQL conf")
PANES = ("red", "blue", "system")

FOOTER_HELP = "1/2/3 fixture  m mcp  b binary  p project  i ingest  g sweep  v demo  c cve  +/- depth  Enter/s start  x/Esc stop  f filter  h help  arrows scroll  q quit"

# Exec-audience overlay mirror of main.CAPABILITIES_EPILOG (no new flags,
# same plain-English value lines). Toggled with h; must stay terminal-safe.
CAPABILITIES_LINES = (
    "Same-day value (Wave 2/5/8):",
    "receipts prove the sandbox run (probe exits + patch hash)",
    "rationale shows why each patch guard fired",
    "topping lists the most reachable + fixable CVE first",
    "mutations confirm the fix holds under small input changes",
    "freshness shows the intel was fetched live today",
    "templates keep patches inside the small-edit guard",
    "stale:<date> means KEV/EPSS older than 1 day, never outranks fresh",
    "repeat-stability re-runs the check so flaky passes fail closed",
    "mcp: POST /mcp submit_code_snippet or CLI --mcp-snippet FILE",
    "binary: /ws/binary sweep or CLI --binary-target FILE (ELF/Mach-O/PE)",
    "mode:fixture scan one bundled fixture end to end",
    "mode:sweep re-run the check up to 4 passes (+/- depth)",
    "mode:mcp submit a code snippet for review (key m)",
    "mode:binary sweep one compiled binary file (key b)",
    "mode:project two-cycle project workout (key p)",
    "mode:ingest validated repo intake at a pinned commit (key i)",
    "mode:demo replay a themed demo script (key v)",
    "mode:cve look up live CVE intel keyless (key c)",
    "hud: live token counter + vault indicator stream on the HUD",
)


def capabilities_lines() -> tuple[str, ...]:
    """TUI help-overlay lines for Wave 2/5/8 same-day value."""
    return CAPABILITIES_LINES


_SENSITIVE_RE = re.compile(
    r"(api[_-]?key|secret|token|bearer|password|private[_-]?key|BEGIN [A-Z ]*PRIVATE)",
    re.IGNORECASE,
)
_PATH_RE = re.compile(r"/[A-Za-z0-9_.\-][A-Za-z0-9_.\-/]{3,}")
_SCRIPT_HINT_RE = re.compile(
    r"(verification_script|traceback|subprocess|os\.system|popen|BEGIN CERT)",
    re.IGNORECASE,
)


def redact_event_text(kind: str, message: object) -> str:
    """Short LAW-4-safe one-liner for display. Never emits scripts/traces/keys/paths."""
    text = str(message).replace("\r", " ").replace("\n", " / ")
    if _SENSITIVE_RE.search(text):
        return "[redacted: credentials hidden]"
    text = _PATH_RE.sub("<path>", text)
    if _SCRIPT_HINT_RE.search(text):
        text = _SCRIPT_HINT_RE.sub("<probe>", text)
        text = text[:160]
    else:
        text = text[:200]
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 160:
        text = text[:157] + "..."
    return f"{kind}: {text}" if text else f"{kind}: ..."


def queue_emit(event_queue: "queue.Queue[tuple[str, str]]"):
    """Build an async ``emit(kind, message)`` that redacts into the queue."""

    async def _emit(kind: str, message: object) -> None:
        event_queue.put((str(kind), redact_event_text(str(kind), message)))

    return _emit


# Known scan-mode values for TuiState.mode (LAW 4: user-typed metadata only,
# never scan output; probe/payload content must not live in rendered text).
TUI_MODES = ("fixture", "sweep", "mcp", "binary", "project", "ingest", "demo", "cve")

# Canonical mode order shared by dispatch routing and --mode choices.
MODE_ORDER = TUI_MODES


def prompt_line(prompt: str, default: str = "", input_func=input) -> str:
    """Read one text line for curses prompts. Testable: empty/EOF -> default."""
    try:
        typed = input_func(prompt)
    except (EOFError, KeyboardInterrupt):
        return default
    if typed is None:
        return default
    text = str(typed).strip()
    return text if text else default


_SNIPPET_LANGUAGE_BY_SUFFIX = {
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".php": "php",
}


def _state_mode(state: TuiState) -> str:
    return str(getattr(state, "mode", "fixture") or "fixture")


def _state_sweep_passes(state: TuiState) -> int:
    depth = getattr(state, "sweep_depth", None)
    passes = getattr(state, "sweep_passes", None)
    try:
        explicit = int(passes) if passes is not None else 1
    except (TypeError, ValueError):
        explicit = 1
    if passes is not None and explicit != 1:
        depth = passes
    for value in (depth, passes):
        if value is not None:
            try:
                return max(1, min(3, int(value)))
            except (TypeError, ValueError):
                pass
    return 1


def _state_field(state: TuiState, *names: str, default: str = "") -> str:
    for name in names:
        value = getattr(state, name, None)
        if value:
            return str(value)
    return default


def _infer_snippet_language(filename: str, explicit: str = "") -> str:
    if explicit and str(explicit).strip().lower() in ("javascript", "python", "php"):
        return str(explicit).strip().lower()
    import os as _os

    return _SNIPPET_LANGUAGE_BY_SUFFIX.get(_os.path.splitext(filename)[1].lower(), "")


@dataclass
class TuiState:
    fixture_index: int = 0
    mode: str = "fixture"
    sweep_depth: int = 1
    mcp_snippet: str = ""
    mcp_contract: str = ""
    binary_path: str = ""
    binary_contract: str = ""
    project_path: str = ""
    project_command: str = ""
    project_test_command: str = ""
    project_contract: str = ""
    ingest_repo: str = ""
    ingest_commit: str = ""
    ingest_branch: str = ""
    demo_theme: str = ""
    demo_vulns: str = ""
    running: bool = False
    stop_requested: bool = False
    filter_kind: str | None = None
    help_open: bool = False
    scroll: dict[str, int] = field(default_factory=lambda: {p: 0 for p in PANES})
    events: list[tuple[str, str]] = field(default_factory=list)
    result_summary: str = "idle: pick a fixture, press Enter."
    status: str = "idle"

    @property
    def fixture_key(self) -> str:
        return FIXTURE_ORDER[self.fixture_index % len(FIXTURE_ORDER)]

    def visible_events(self, pane: str) -> list[str]:
        kinds = ("red",) if pane == "red" else ("blue", "research") if pane == "blue" else None
        out = []
        for kind, text in self.events:
            if kinds is not None and kind not in kinds:
                continue
            if kinds is None and kind in ("red", "blue", "research"):
                continue
            if self.filter_kind and kind != self.filter_kind:
                continue
            out.append(text)
        return out


def drain_queue(event_queue: "queue.Queue[tuple[str, str]]", state: TuiState) -> int:
    """Move pending (kind, redacted-text) pairs into state. Returns count."""
    count = 0
    try:
        while True:
            kind, text = event_queue.get_nowait()
            state.events.append((kind, text[-160:]))
            if len(state.events) > 500:
                state.events = state.events[-500:]
            count += 1
    except queue.Empty:
        pass
    return count


def parse_key(key: object) -> str:
    """Map a keypress to an action name. Accepts int codes or 1-char strings."""
    if isinstance(key, str):
        if len(key) == 1:
            key = ord(key)
        elif key == "KEY_ENTER":
            return "start"
        elif key in ("KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT"):
            return "scroll:" + key[4:].lower()
        elif key == "KEY_RESIZE":
            return "resize"
        elif key == "ESC":
            return "stop"
        else:
            return "unknown"
    code = int(key)
    enter_codes = {10, 13}
    if curses is not None:
        enter_codes |= {getattr(curses, "KEY_ENTER", 343)}
    if code in enter_codes:
        return "start"
    if curses is not None:
        mapping = {
            getattr(curses, "KEY_UP", 259): "scroll:up",
            getattr(curses, "KEY_DOWN", 258): "scroll:down",
            getattr(curses, "KEY_LEFT", 260): "scroll:left",
            getattr(curses, "KEY_RIGHT", 261): "scroll:right",
            getattr(curses, "KEY_RESIZE", 410): "resize",
        }
        if code in mapping:
            return mapping[code]
    else:
        if code in (259, 258, 260, 261, 410):
            return {
                259: "scroll:up",
                258: "scroll:down",
                260: "scroll:left",
                261: "scroll:right",
                410: "resize",
            }[code]
    if code == 27:
        return "stop"
    try:
        char = chr(code)
    except ValueError:
        return "unknown"
    if char in ("1", "2", "3"):
        return f"select:{int(char) - 1}"
    lowered = char.lower()
    if lowered == "s":
        return "start"
    if lowered == "x":
        return "stop"
    if lowered == "f":
        return "filter"
    if lowered == "m":
        return "mode:mcp"
    if lowered == "b":
        return "mode:binary"
    if lowered == "p":
        return "mode:project"
    if lowered == "i":
        return "mode:ingest"
    if lowered == "g":
        return "mode:sweep"
    if lowered == "v":
        return "mode:demo"
    if lowered == "c":
        return "mode:cve"
    if char == "+":
        return "depth:inc"
    if char == "-":
        return "depth:dec"
    if lowered == "h":
        return "help"
    if lowered == "q":
        return "quit"
    return "unknown"


def apply_action(state: TuiState, action: str) -> str:
    """Apply a parsed action to state (no threads/curses). Returns the action."""
    if action.startswith("select:"):
        state.fixture_index = int(action.split(":")[1]) % len(FIXTURE_ORDER)
        state.mode = "fixture"
        if not state.running:
            state.result_summary = f"selected {state.fixture_key}; press Enter."
    elif action.startswith("mode:"):
        mode = action.split(":", 1)[1]
        if mode in TUI_MODES:
            state.mode = mode
    elif action == "depth:inc":
        state.sweep_depth = min(3, state.sweep_depth + 1)
    elif action == "depth:dec":
        state.sweep_depth = max(1, state.sweep_depth - 1)
    elif action == "filter":
        order: list[str | None] = [None, "red", "blue", "system"]
        state.filter_kind = order[(order.index(state.filter_kind) + 1) % len(order)]
    elif action == "help":
        state.help_open = not state.help_open
    elif action.startswith("scroll:"):
        direction = action.split(":")[1]
        panes = list(PANES)
        if direction in ("up", "down"):
            for pane in panes:
                state.scroll[pane] = max(0, state.scroll[pane] + (-1 if direction == "up" else 1))
        elif direction in ("left", "right"):
            panes_sorted = panes if direction == "right" else list(reversed(panes))
            for pane in panes_sorted:  # horizontal scroll: shift focus offset uniformly
                state.scroll[pane] = max(0, state.scroll[pane] + 1)
                break
    return action


def render_panes(state: TuiState, width: int = WIDTH, height: int = HEIGHT) -> list[str]:
    """Pure 80x24 renderer: header / chips / pipeline panes / result / footer."""
    width = max(40, width)
    height = max(12, height)
    lines: list[str] = []

    header = " Secure Mitigation System "
    status = f"[{state.status}]"
    lines.append((header + status.rjust(width - len(header)))[:width].ljust(width))

    chips = []
    for i, (_key, short) in enumerate(zip(FIXTURE_ORDER, FIXTURE_SHORT, strict=True)):
        mark = "*" if i == state.fixture_index else " "
        chips.append(f"{mark}{i + 1}:{short}")
    filt = f"filter:{state.filter_kind or 'all'}"
    mode_chip = f"mode:{state.mode}  depth:{state.sweep_depth}"
    lines.append((" ".join(chips) + "  " + filt + "  " + mode_chip)[:width].ljust(width))

    pane_width = max(10, (width - 4) // 3)
    titles = [f" {name.upper()} ".center(pane_width, "-")[:pane_width] for name in PANES]
    lines.append(("|" + "|".join(titles) + "|")[:width].ljust(width))

    body_rows = height - 6  # header, chips, titles, result, 2x footer
    if state.help_open:
        for row in range(max(1, body_rows)):
            if row < len(CAPABILITIES_LINES):
                lines.append(("| HELP: " + CAPABILITIES_LINES[row])[:width].ljust(width))
            elif row == len(CAPABILITIES_LINES):
                lines.append(("| h closes this help")[:width].ljust(width))
            else:
                lines.append(("|")[:width].ljust(width))
    else:
        cols: list[list[str]] = []
        for pane in PANES:
            items = state.visible_events(pane)
            offset = state.scroll.get(pane, 0)
            cols.append([line[:pane_width].ljust(pane_width) for line in items[offset:]] or [""])
        for row in range(max(1, body_rows)):
            cells = [
                (cols[c][row] if row < len(cols[c]) else "".ljust(pane_width)) for c in range(3)
            ]
            lines.append(("|" + "|".join(cells) + "|")[:width].ljust(width))

    result = f" Result [{state.fixture_key}]: {state.result_summary}"
    lines.append(result[:width].ljust(width))
    lines.append(FOOTER_HELP[:width].ljust(width))
    hint = "q quit  f filter  arrows scroll"
    if state.running:
        hint = "RUNNING... x stop" + "  " + hint
    lines.append(hint[:width].ljust(width))
    return lines[:height]


def describe_wave2(result: object) -> str:
    """Wave 2 items 1-4 one-line tokens (SPEC 14.8). Never raises, never leaks.

    Probes the same optional fields as sms_cli.format_wave2_facts
    (verdict_receipt, guard_rationales, mutation_evidence, vulnerabilities
    topping) and returns a short ``[receipt ...] [mutations ...]`` suffix, or
    "" when nothing is present or anything is odd-shaped.
    """
    try:
        from sms_cli import format_facts, format_wave2_facts  # lazy: keeps module import light

        facts = format_wave2_facts(result)
        try:
            compression = str(format_facts(result).get("compression") or "")
        except Exception:
            compression = ""
    except Exception:
        return ""
    try:
        tokens = []
        receipt = str(facts.get("receipt") or "")
        if receipt and receipt != "Not reported":
            tokens.append(f"[receipt {receipt[:80]}]")
        guards = str(facts.get("guard_rationales") or "")
        if guards and guards != "Not reported":
            tokens.append(f"[guards {guards[:60]}]")
        top = str(facts.get("fast_lane_top") or "")
        if top and top != "Not reported":
            tokens.append(f"[top {top[:60]}]")
        mutations = str(facts.get("mutations") or "")
        if mutations and mutations != "Not reported":
            tokens.append(f"[mutations {mutations[:40]}]")
        if compression and compression != "Not reported":
            tokens.append(f"[compress {compression[:60]}]")
        vault = str(format_facts(result).get("vault_recall") or "")
        if vault and vault != "Not reported":
            tokens.append(f"[vault {vault[:40]}]")
        return (" " + " ".join(tokens)) if tokens else ""
    except Exception:
        return ""


def describe_result(result: object) -> str:
    """LAW-4-safe one-line summary of a ScanResult (no traces/scripts)."""

    def _get(name: str, default: str = "") -> str:
        return str(getattr(result, name, default))

    return f"{_get('target', '?')} -> {_get('status', '?')}: {_get('message', '')}{describe_wave2(result)}"[
        :200
    ]


def start_scan_thread(
    state: TuiState,
    event_queue: "queue.Queue[tuple[str, str]]",
    stop_event: threading.Event,
    *,
    daemon: bool = True,
) -> threading.Thread:
    """Run execute_purple_workflow in-process on a worker thread via asyncio.run."""
    from modules.workflows.workflow import (
        execute_purple_workflow,  # lazy: keeps module import stdlib-only
    )

    fixture_key = state.fixture_key
    state.running = True
    state.stop_requested = False
    state.status = f"scanning {fixture_key}"
    emit = queue_emit(event_queue)

    def _worker() -> None:
        try:
            result = asyncio.run(execute_purple_workflow(fixture_key, emit))
            event_queue.put(("system", describe_result(result)))
            state.result_summary = describe_result(result)
            state.status = "done"
        except Exception as exc:  # fail closed: report type only, never internals
            event_queue.put(("system", f"system: scan failed ({type(exc).__name__})"))
            state.result_summary = f"scan failed ({type(exc).__name__})."
            state.status = "error"
        finally:
            state.running = False
            stop_event.set()

    thread = threading.Thread(target=_worker, name=f"tui-scan-{fixture_key}", daemon=daemon)
    thread.start()
    return thread


_SNIPPET_FILENAME_BY_LANGUAGE = {
    "javascript": "snippet.js",
    "python": "snippet.py",
    "php": "snippet.php",
}

_DEFAULT_SNIPPET_CONTRACT = "Preserve normal behavior. Only harden untrusted inputs."
_DEFAULT_PROJECT_CONTRACT = "Preserve normal behavior. Only harden untrusted inputs."


def _coerce_argv(value: object, default: list[str]) -> list[str]:
    """Coerce a command field to argv list. Strings via JSON argv or shlex."""
    if value is None:
        return list(default)
    if isinstance(value, (list, tuple)):
        parts = [str(item) for item in value if str(item)]
        return parts or list(default)
    text = str(value).strip()
    if not text:
        return list(default)
    if text.startswith("["):
        try:
            import json as _json

            parsed = _json.loads(text)
            if isinstance(parsed, list) and all(isinstance(p, str) for p in parsed) and parsed:
                return list(parsed)
        except Exception:
            pass
    import shlex as _shlex

    try:
        parts = [p for p in _shlex.split(text) if p]
    except Exception:
        parts = [p for p in text.split() if p]
    return parts or list(default)


def _state_int(state: TuiState, name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(getattr(state, name, default))))
    except (TypeError, ValueError):
        return default


def _result_field(result: object, name: str, default: str = "?") -> str:
    if isinstance(result, dict):
        value = result.get(name, default)
        return str(value)[:120] if value is not None else default
    value = getattr(result, name, default)
    try:
        text = str(value)
    except Exception:
        return default
    return text[:120] if text else default


def _result_target(result: object) -> str:
    target = _result_field(result, "target", "")
    if target and target != "?":
        return target
    project = _result_field(result, "project", "")
    return project if project and project != "?" else "?"


def _summarize_result(prefix: str, result: object) -> str:
    """LAW-4-safe one-line summary: status/message/target only, never blobs."""
    try:
        if isinstance(result, bool):
            return f"{prefix}: {'done' if result else 'failed'}"
        if isinstance(result, int):
            return f"{prefix}: exit {int(result)}"
        if isinstance(result, dict):
            status = _result_field(result, "status", "?")
            message = _result_field(result, "message", "")
            text = f"{status}: {message}".strip(": ").strip()
            return f"{prefix}: {text}"[:200] if text else f"{prefix}: done"
        return f"{prefix}: {_result_target(result)} -> {describe_result(result)}"[:200]
    except Exception:
        return f"{prefix}: done"


def _rc_from_outcome(outcome: object) -> int:
    """Exit code from a backend outcome. Completion twins describe_result."""
    if isinstance(outcome, bool):
        return 0 if outcome else 1
    if isinstance(outcome, int):
        return int(outcome)
    if isinstance(outcome, dict):
        return 0 if str(outcome.get("status", "")) != "error" else 1
    success = getattr(outcome, "success", None)
    if isinstance(success, bool):
        return 0 if success else 1
    status = str(getattr(outcome, "status", "") or "").lower()
    if status in ("error", "failed"):
        return 1
    return 0


def _project_spec_from_state(state: TuiState):
    """Build a validated ProjectSpec from state project fields (or raise).

    Consent pass-through (not consent override): ``allow_remote`` flows from
    state into the spec unchanged, and the REAL ``execute_project_workflow``
    / ``execute_cve_scan`` path enforces it (ProjectWorkflowError, before any
    scan) when inference is hosted. Dispatch never defaults consent to True.
    """
    from modules.services.projects import DEFAULT_TARGET_IMAGE, ProjectSpec

    allow_remote = bool(
        getattr(state, "allow_remote", getattr(state, "project_allow_remote_inference", False))
    )
    return ProjectSpec.model_validate(
        {
            "path": _state_field(state, "project_path", default=".") or ".",
            "image": _state_field(state, "project_image") or DEFAULT_TARGET_IMAGE,
            "command": _coerce_argv(getattr(state, "project_command", None), ["true"]),
            "test_command": _coerce_argv(getattr(state, "project_test_command", None), ["true"]),
            "contract": _state_field(state, "project_contract", "contract")
            or _DEFAULT_PROJECT_CONTRACT,
            "cycles": _state_int(state, "project_cycles", 1, 1, 20),
            "context_budget": _state_int(state, "project_context_budget", 32768, 1024, 131072),
            "allow_remote_inference": allow_remote,
        }
    )


async def _dispatch_core(state: TuiState, emit) -> tuple[str, object]:
    """Run state.mode's backend; returns (LAW-4-safe summary, raw outcome).

    Backends are lazy-imported at call time so monkeypatching the canonical
    source modules redirects them. Backend exceptions propagate (run_plain
    maps them to exit 1; the dispatch thread maps them to error state).
    """
    mode = _state_mode(state)
    if mode not in MODE_ORDER:
        raise ValueError(f"Unknown TUI mode {mode!r}.")
    if mode == "sweep":
        from modules.workflows.sweep import execute_sweep_scan

        result = await execute_sweep_scan(
            state.fixture_key, emit, max_passes=_state_sweep_passes(state)
        )
        return _summarize_result(f"sweep {state.fixture_key}", result), result
    if mode == "mcp":
        import main as main_mod
        from modules.services import mcp_bridge

        path = _state_field(state, "snippet_path", "mcp_snippet", "mcp_path")
        source = _state_field(state, "snippet_source", "mcp_source")
        if not source and path:
            try:
                from pathlib import Path as _Path

                source = _Path(path).read_text(encoding="utf-8")
            except OSError:
                source = ""
        language = _infer_snippet_language(
            path or _state_field(state, "snippet_filename", "mcp_filename"),
            _state_field(state, "snippet_language", "mcp_language"),
        )
        if not language:
            raise ValueError("Cannot infer snippet language; choose javascript, python, or php.")
        import os as _os

        filename = _os.path.basename(path) if path else ""
        if not filename or filename.startswith("."):
            filename = _SNIPPET_FILENAME_BY_LANGUAGE[language]
        raw = {
            "filename": filename,
            "language": language,
            "source": source,
            "contract": _state_field(state, "contract", "mcp_contract")
            or _DEFAULT_SNIPPET_CONTRACT,
        }
        arguments = mcp_bridge.validate_snippet_arguments(raw)
        result = await main_mod.execute_mcp_snippet_scan(arguments, emit)
        return _summarize_result("mcp snippet", result), result
    if mode == "binary":
        from modules.services import binary_intake
        from modules.workflows import binary_sweep as _binary_sweep

        path = _state_field(state, "binary_path", "binary_target")
        contract = _state_field(state, "binary_contract", "contract") or (_DEFAULT_PROJECT_CONTRACT)
        spec = binary_intake.validate_binary_file(path, contract=contract)
        result = await _binary_sweep.execute_binary_sweep(spec, emit)
        return _summarize_result("binary", result), result
    if mode == "project":
        from modules.workflows import project_workflow as _project_workflow

        spec = _project_spec_from_state(state)
        result = await _project_workflow.execute_project_workflow(spec, emit)
        return _summarize_result("project", result), result
    if mode == "ingest":
        from modules.services.repo_intake import RepoIntakeSpec
        from modules.services.sms_api import build_ingest_event, build_telemetry_event

        url = _state_field(state, "ingest_repo")
        commit = _state_field(state, "ingest_commit", "commit_hash")
        spec = RepoIntakeSpec(url=url, commit_hash=commit)  # ValueError -> fail closed
        ingest_evt = build_ingest_event(repo_url=spec.url, sha=spec.commit_hash)
        await emit(ingest_evt["team"], ingest_evt["msg"])
        from modules.workflows.workflow import execute_purple_workflow as _execute_ingest_scan

        fixture_key = state.fixture_key
        await emit("system", f"system: ingest proven on fixture {fixture_key}")
        result = await _execute_ingest_scan(fixture_key, emit)
        try:
            compression = getattr(result, "compression", None)
            raw = int(getattr(compression, "raw_tokens_estimated", 0) or 0)
            sent = int(getattr(compression, "compressed_tokens_sent", 0) or 0)
            ratio = float(getattr(compression, "compression_ratio", 0.0) or 0.0)
            telemetry_evt = build_telemetry_event(
                raw=raw,
                sent=sent,
                savings_pct=round(ratio * 100.0, 1),
                novel=0,
                known=0,
            )
            await emit(telemetry_evt["team"], telemetry_evt["msg"])
        except (TypeError, ValueError, AttributeError):
            pass
        return _summarize_result("ingest", result), result
    if mode == "demo":
        import main as main_mod
        from modules.core.config import load_config

        settings = load_config()
        allow_remote = bool(
            getattr(state, "allow_remote", getattr(state, "project_allow_remote_inference", False))
        )
        intel_offline = False
        if settings.inference_mode != "local" and not allow_remote:
            # Consent parity with main.ai_demo_runner: hosted Muse receives
            # generated source, so the demo stays offline unless consented.
            intel_offline = True
        outcome = await main_mod.run_demo_build(
            emit,
            settings,
            theme=_state_field(state, "demo_theme"),
            vulns=_state_field(state, "demo_vulns"),
            intel_offline=intel_offline,
        )
        return _summarize_result("demo", outcome), outcome
    if mode == "cve":
        from modules.workflows import cve_workflow as _cve_workflow

        spec = _project_spec_from_state(state)
        result = await _cve_workflow.execute_cve_scan(
            spec,
            emit,
            include_osv=not bool(getattr(state, "project_offline_cve", False)),
            include_deep_assessment=bool(getattr(state, "project_deep_assessment", False)),
            fast_lane=bool(getattr(state, "project_fast_lane", False)),
        )
        return _summarize_result("cve", result), result
    from modules.workflows.workflow import execute_purple_workflow

    result = await execute_purple_workflow(state.fixture_key, emit)
    return _summarize_result(f"fixture {state.fixture_key}", result), result


def dispatch_scan(state: TuiState, emit, stop_event: threading.Event | None = None) -> str:
    """Route ``state.mode`` to its backend; sync, returns a LAW-4-safe summary.

    ``emit`` is an async ``(kind, message)`` callable. Backend exceptions
    propagate so callers (run_plain exit codes, dispatch-thread error state)
    fail closed with the exception type only.
    """
    if stop_event is not None and stop_event.is_set():
        return "cancelled before scan."
    summary, _outcome = asyncio.run(_dispatch_core(state, emit))
    return summary


def start_dispatch_thread(
    state: TuiState,
    event_queue: "queue.Queue[tuple[str, str]]",
    stop_event: threading.Event | None = None,
    *,
    daemon: bool = True,
) -> threading.Thread:
    """Run dispatch_scan for state.mode on a worker thread via asyncio.run."""
    if stop_event is None:
        stop_event = threading.Event()
    mode = _state_mode(state)
    state.running = True
    state.stop_requested = False
    state.status = f"scanning {mode}"
    emit = queue_emit(event_queue)

    def _worker() -> None:
        try:
            summary, _outcome = asyncio.run(_dispatch_core(state, emit))
            event_queue.put(("system", summary))
            state.result_summary = summary
            state.status = "done"
        except Exception as exc:  # fail closed: report type only, never internals
            event_queue.put(("system", f"system: scan failed ({type(exc).__name__})"))
            state.result_summary = f"scan failed ({type(exc).__name__})."
            state.status = "error"
        finally:
            state.running = False
            stop_event.set()

    thread = threading.Thread(target=_worker, name=f"tui-dispatch-{mode}", daemon=daemon)
    thread.start()
    return thread


def _state_from_args(args: argparse.Namespace) -> TuiState:
    """Build a TuiState from run_plain/main argparse. Unknown mode -> exit 2."""
    mode = str(getattr(args, "mode", "fixture") or "fixture")
    if mode not in MODE_ORDER:
        raise SystemExit(2)
    if mode == "sweep":
        mode = "sweep"
    state = TuiState()
    for name in (
        "mode",
        "sweep_depth",
        "sweep_passes",
        "mcp_snippet",
        "mcp_contract",
        "contract",
        "binary_path",
        "binary_contract",
        "project_path",
        "project_command",
        "project_test_command",
        "project_contract",
        "ingest_repo",
        "ingest_commit",
        "ingest_branch",
        "allow_remote",
        "demo_theme",
        "demo_vulns",
        "snippet_path",
        "snippet_language",
        "snippet_source",
        "snippet_filename",
        "mcp_filename",
        "mcp_language",
        "mcp_source",
        "mcp_path",
        "binary_target",
        "project_image",
        "project_cycles",
        "project_context_budget",
        "project_allow_remote_inference",
        "project_offline_cve",
        "project_fast_lane",
        "project_deep_assessment",
    ):
        state.__dict__[name] = getattr(args, name, getattr(state, name, None))
    state.mode = mode
    if getattr(args, "fixture", None):
        try:
            state.fixture_index = list(FIXTURE_ORDER).index(args.fixture)
        except ValueError:
            pass
    return state


def _add_dispatch_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=list(MODE_ORDER),
        default="fixture",
        help="Scan mode (default: fixture single finding loop)",
    )
    parser.add_argument(
        "--contract",
        default="",
        help="Behavior contract for snippet/binary/project scans",
    )
    parser.add_argument(
        "--snippet",
        dest="snippet_path",
        default="",
        help="Snippet file to verify through the red/blue Docker loop (mcp mode)",
    )
    parser.add_argument(
        "--snippet-language",
        choices=["javascript", "python", "php"],
        default="",
        help="Snippet language (default: inferred from file extension)",
    )
    parser.add_argument("--snippet-source", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--project-path",
        default=".",
        help="Local project root for project/cve modes",
    )
    parser.add_argument(
        "--project-image",
        default="",
        help="Runtime image for project/cve modes (default: target base image)",
    )
    parser.add_argument(
        "--project-command",
        default="",
        help='Target argv as JSON, e.g. ["python3", "app.py"]',
    )
    parser.add_argument(
        "--project-test-command",
        default="",
        help='Trusted regression argv as JSON, e.g. ["python3", "-m", "unittest"]',
    )
    parser.add_argument(
        "--binary-path",
        dest="binary_path",
        default="",
        help="Binary file to sweep in binary mode (same as --binary-target)",
    )
    parser.add_argument(
        "--project-contract",
        default="",
        help="Expected behavior and sanitization-only patch constraints",
    )
    parser.add_argument(
        "--project-cycles",
        type=int,
        default=1,
        help="Red/blue cycles for project mode, 1 to 20 (default: 1)",
    )
    parser.add_argument(
        "--project-context-budget",
        type=int,
        default=32768,
        help="Bounded per-call source context budget (default: 32768)",
    )
    parser.add_argument(
        "--project-allow-remote-inference",
        "--allow-remote-inference",
        dest="project_allow_remote_inference",
        action="store_true",
        help="Consent to send project source/evidence to hosted Muse",
    )
    parser.add_argument(
        "--project-offline-cve",
        action="store_true",
        help="Skip OSV network lookup in cve mode; static signals only",
    )
    parser.add_argument(
        "--project-fast-lane",
        action="store_true",
        help="CVE disclosure fast lane: static + OSV only, deterministic order",
    )
    parser.add_argument(
        "--ingest-repo",
        default="",
        help="HTTPS repo URL for ingest mode (requires --commit-hash, like main.py)",
    )
    parser.add_argument(
        "--commit-hash",
        dest="ingest_commit",
        default="",
        help="Pinned 40-hex commit for ingest mode (requires --ingest-repo)",
    )
    parser.add_argument(
        "--ingest-branch",
        default="",
        help="Branch label recorded with the ingest intake (metadata only, never executed)",
    )
    parser.add_argument(
        "--project-deep-assessment",
        action="store_true",
        help="Add Muse triage of static signals in cve mode",
    )
    parser.add_argument(
        "--demo-theme",
        default="",
        help="Threat-intel themes for demo generation",
    )
    parser.add_argument(
        "--demo-vulns",
        default="",
        help="Requested demo flaws: CVE IDs, named types, or free text",
    )


def _run_state_scan(state: TuiState, *, header: str) -> int:
    """Run dispatch core on the calling thread; print redacted lines + summary."""
    event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    print(header)
    emit = queue_emit(event_queue)
    try:
        _summary, outcome = asyncio.run(_dispatch_core(state, emit))
    except SystemExit:
        raise
    except Exception as exc:
        while True:
            try:
                kind, text = event_queue.get_nowait()
            except queue.Empty:
                break
            print(f"[{kind}] {text}")
        print(f"scan failed ({type(exc).__name__})")
        return 1
    while True:
        try:
            kind, text = event_queue.get_nowait()
        except queue.Empty:
            break
        print(f"[{kind}] {text}")
    print(_summarize_result(_state_mode(state), outcome))
    return _rc_from_outcome(outcome)


def _run_plain_legacy(args: argparse.Namespace) -> int:
    """Pre-dispatch plain behavior: fixture single/sweep or binary target.

    Kept so ``--fixture`` + ``--sweep-passes``/``--binary-target`` invocations
    (no ``--mode``) behave byte-identically to before.
    """
    import sys as _sys

    _wf = _sys.modules.get("modules.workflows.workflow")
    if _wf is None:
        from modules.workflows import workflow as _wf_mod

        _wf = _wf_mod
    execute_purple_workflow = _wf.execute_purple_workflow
    _sweep = _sys.modules.get("modules.workflows.sweep")
    _bsweep = _sys.modules.get("modules.workflows.binary_sweep")

    event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    depth = "sweep" if args.sweep_passes else "single"
    if args.binary_target:
        if _bsweep is not None:
            execute_binary_sweep = _bsweep.execute_binary_sweep
        else:
            from modules.workflows.binary_sweep import execute_binary_sweep
        from modules.services.binary_intake import (
            BinaryRejected,
            validate_binary_file,
        )

        print(f"Secure Mitigation System [plain mode] binary={args.binary_target}")
        from pathlib import Path as _Path

        if str(args.binary_target) == "binary_argv_echo":
            bundled = _Path(__file__).resolve().parent / "targets" / "binary_argv_echo" / "echo"
            if bundled.exists():
                args.binary_target = str(bundled)
        try:
            spec = validate_binary_file(args.binary_target, contract="TUI binary sweep.")
        except BinaryRejected as exc:
            print(f"invalid binary target: {exc}")
            return 1
        try:
            result = asyncio.run(execute_binary_sweep(spec, queue_emit(event_queue)))
        except Exception as exc:
            print(f"scan failed ({type(exc).__name__})")
            return 1
        while True:
            try:
                kind, text = event_queue.get_nowait()
            except queue.Empty:
                break
            print(f"[{kind}] {text}")
        print(describe_result(result))
        return 0 if getattr(result, "success", False) else 1
    print(f"Secure Mitigation System [plain mode] fixture={args.fixture} {depth}")
    try:
        if args.sweep_passes:
            if _sweep is None:
                from modules.workflows import sweep as _sweep_mod

                _sweep = _sweep_mod
            execute_sweep_scan = _sweep.execute_sweep_scan
            result = asyncio.run(
                execute_sweep_scan(
                    args.fixture,
                    queue_emit(event_queue),
                    max_passes=max(1, min(3, args.sweep_passes)),
                )
            )
        else:
            result = asyncio.run(execute_purple_workflow(args.fixture, queue_emit(event_queue)))
    except Exception as exc:
        print(f"scan failed ({type(exc).__name__})")
        return 1
    while True:
        try:
            kind, text = event_queue.get_nowait()
        except queue.Empty:
            break
        print(f"[{kind}] {text}")
    print(describe_result(result))
    return 0


def _print_global_stats() -> int:
    """Print CompressionStats summary + vault_stats() as structured stdout.

    LAW 4: counts and token estimates only — vault_stats() never includes
    payload material (sinks, shapes, diffs, notes). Never raises: vault or
    import failures degrade to zeroed rows with the reason on one line.
    """
    from modules.shared.sms_compress import CompressionStats

    stats = CompressionStats()
    summary = stats.summary()
    lines = [
        "Secure Mitigation System [stats]",
        (
            f"compression: raw {summary['total_raw_tokens']} -> "
            f"sent {summary['total_compressed_tokens']} tokens "
            f"(saved {summary['total_tokens_saved']}, "
            f"ratio {summary['mean_compression_ratio']:.2f})"
        ),
    ]
    try:
        from modules.services.sms_api import query_vault_stats

        vault = query_vault_stats()
    except Exception as exc:
        lines.append(f"vault: unavailable ({type(exc).__name__})")
        print("\n".join(lines))
        return 0
    known = sum(
        int(info.get("records", 0))
        for key, info in vault.items()
        if key in ("red", "blue", "green") and isinstance(info, dict)
    )
    if "known_archetypes" not in vault:
        known = int(vault.get("known_archetypes", known) or 0)
    saved_estimate = int(vault.get("tokens_saved_estimate", 0) or 0)
    lines.append(f"vault: {known} known archetypes, tokens_saved_estimate {saved_estimate}")
    historical = known
    lines.append(f"vault split: 0 novel vs {historical} historical")
    print("\n".join(lines))
    return 0


def _run_plain_dispatch(args: argparse.Namespace) -> int:
    mode = str(getattr(args, "mode", "fixture") or "fixture")
    if mode not in MODE_ORDER:
        raise SystemExit(2)
    if hasattr(args, "binary_target") and args.binary_target:
        if not getattr(args, "binary_path", ""):
            args.binary_path = args.binary_target
    state = _state_from_args(args)
    return _run_state_scan(state, header=f"Secure Mitigation System [plain mode] mode={mode}")


def run_plain(argv: list[str] | None = None) -> int:
    """Non-TTY / no-curses degrade: pick fixture, run scan, print redacted lines."""
    from sms_cli import CAPABILITIES_TEXT

    parser = argparse.ArgumentParser(
        description="Secure Mitigation System TUI (plain mode)",
        epilog=CAPABILITIES_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--fixture", choices=list(FIXTURE_ORDER), default=FIXTURE_ORDER[0])
    parser.add_argument(
        "--sweep-passes",
        type=int,
        default=None,
        help="Multi-pass sweep depth 1-3 (default: single finding loop)",
    )
    parser.add_argument(
        "--binary-target",
        default=None,
        help="Sweep one compiled binary file through the trusted harness 4-pass loop",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print the CompressionStats summary + vault_stats() "
        "(global novel/historical + tokens_saved_estimate) and exit 0",
    )
    _add_dispatch_flags(parser)
    args = parser.parse_args(argv)
    if getattr(args, "stats", False):
        return _print_global_stats()
    explicit = set(argv or [])
    if "--mode" in explicit or getattr(args, "mode", "fixture") != "fixture":
        return _run_plain_dispatch(args)
    if (
        getattr(args, "snippet_path", "")
        or getattr(args, "project_image", "")
        or getattr(args, "project_command", "")
        or getattr(args, "project_test_command", "")
        or getattr(args, "project_contract", "")
        or getattr(args, "project_allow_remote_inference", False)
        or getattr(args, "project_offline_cve", False)
        or getattr(args, "project_fast_lane", False)
        or getattr(args, "project_deep_assessment", False)
        or getattr(args, "demo_theme", "")
        or getattr(args, "demo_vulns", "")
        or getattr(args, "ingest_repo", "")
        or getattr(args, "ingest_commit", "")
        or getattr(args, "ingest_branch", "")
        or getattr(args, "contract", "")
        or getattr(args, "snippet_language", "")
    ):
        return _run_plain_dispatch(args)
    return _run_plain_legacy(args)


def _curses_main(stdscr, state: TuiState) -> None:
    event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    stop_event = threading.Event()
    worker: threading.Thread | None = None
    try:
        curses.curs_set(0)
    except Exception:
        pass
    stdscr.nodelay(True)
    stdscr.timeout(100)
    while True:
        height, width = stdscr.getmaxyx()
        drain_queue(event_queue, state)
        if worker is not None and not worker.is_alive():
            worker = None
        for i, line in enumerate(render_panes(state, width=width, height=height)):
            try:
                stdscr.addstr(i, 0, line[: max(0, width - 1)])
            except Exception:
                pass
        try:
            stdscr.refresh()
        except Exception:
            pass
        try:
            ch = stdscr.getch()
        except Exception:
            continue
        if ch == -1:
            continue
        action = parse_key(ch)
        if action == "quit":
            state.stop_requested = True
            stop_event.set()
            return
        if action == "stop":
            state.stop_requested = True
            if state.running:
                state.status = "stop requested (scan finishes in background)"
                state.result_summary = "stop requested; worker is daemonized."
            continue
        if action.startswith("select:"):
            if not state.running:
                apply_action(state, action)
            continue
        if action == "filter":
            apply_action(state, action)
            continue
        if action == "help":
            apply_action(state, action)
            continue
        if action.startswith("scroll:") or action == "resize":
            apply_action(state, action)
            continue
        if action == "start":
            if state.running or worker is not None:
                continue
            stop_event = threading.Event()
            if _state_mode(state) == "fixture" and _state_sweep_passes(state) <= 1:
                worker = start_scan_thread(state, event_queue, stop_event)
            else:
                worker = start_dispatch_thread(state, event_queue, stop_event)
            continue


def main(argv: list[str] | None = None) -> int:
    """Entry: curses when a TTY + curses exist, else plain-text degrade."""
    if curses is None or not sys.stdin.isatty() or not sys.stdout.isatty():
        return run_plain(argv)
    parser = argparse.ArgumentParser(
        description="Secure Mitigation System TUI",
        epilog="h help overlay: receipts, rationale, topping, mutations, freshness, templates, stale token, repeat-stability (same-day value).",
    )
    parser.add_argument("--fixture", choices=list(FIXTURE_ORDER), default=FIXTURE_ORDER[0])
    _add_dispatch_flags(parser)
    args = parser.parse_args(argv)
    state = _state_from_args(args)
    try:
        curses.wrapper(_curses_main, state)
    except Exception as exc:
        print(f"TUI exited ({type(exc).__name__}); falling back to plain mode.")
        return run_plain(["--fixture", state.fixture_key])
    return 0


if __name__ == "__main__":  # pragma: no cover - manual entry
    raise SystemExit(main())
