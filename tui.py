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

FOOTER_HELP = "1/2/3 fixture  Enter/s start  x/Esc stop  f filter  arrows scroll  q quit"

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


@dataclass
class TuiState:
    fixture_index: int = 0
    running: bool = False
    stop_requested: bool = False
    filter_kind: str | None = None
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
    if lowered == "q":
        return "quit"
    return "unknown"


def apply_action(state: TuiState, action: str) -> str:
    """Apply a parsed action to state (no threads/curses). Returns the action."""
    if action.startswith("select:"):
        state.fixture_index = int(action.split(":")[1]) % len(FIXTURE_ORDER)
        if not state.running:
            state.result_summary = f"selected {state.fixture_key}; press Enter."
    elif action == "filter":
        order: list[str | None] = [None, "red", "blue", "system"]
        state.filter_kind = order[(order.index(state.filter_kind) + 1) % len(order)]
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
    lines.append((" ".join(chips) + "  " + filt)[:width].ljust(width))

    pane_width = max(10, (width - 4) // 3)
    titles = [f" {name.upper()} ".center(pane_width, "-")[:pane_width] for name in PANES]
    lines.append(("|" + "|".join(titles) + "|")[:width].ljust(width))

    body_rows = height - 6  # header, chips, titles, result, 2x footer
    cols: list[list[str]] = []
    for pane in PANES:
        items = state.visible_events(pane)
        offset = state.scroll.get(pane, 0)
        cols.append([line[:pane_width].ljust(pane_width) for line in items[offset:]] or [""])
    for row in range(max(1, body_rows)):
        cells = [(cols[c][row] if row < len(cols[c]) else "".ljust(pane_width)) for c in range(3)]
        lines.append(("|" + "|".join(cells) + "|")[:width].ljust(width))

    result = f" Result [{state.fixture_key}]: {state.result_summary}"
    lines.append(result[:width].ljust(width))
    lines.append(FOOTER_HELP[:width].ljust(width))
    hint = "q quit  f filter  arrows scroll"
    if state.running:
        hint = "RUNNING... x stop" + "  " + hint
    lines.append(hint[:width].ljust(width))
    return lines[:height]


def describe_result(result: object) -> str:
    """LAW-4-safe one-line summary of a ScanResult (no traces/scripts)."""

    def _get(name: str, default: str = "") -> str:
        return str(getattr(result, name, default))

    return f"{_get('target', '?')} -> {_get('status', '?')}: {_get('message', '')}"[:160]


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


def run_plain(argv: list[str] | None = None) -> int:
    """Non-TTY / no-curses degrade: pick fixture, run scan, print redacted lines."""
    parser = argparse.ArgumentParser(description="Secure Mitigation System TUI (plain mode)")
    parser.add_argument("--fixture", choices=list(FIXTURE_ORDER), default=FIXTURE_ORDER[0])
    args = parser.parse_args(argv)
    from modules.workflows.workflow import (
        execute_purple_workflow,  # lazy import for stdlib-only module top
    )

    event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    print(f"Secure Mitigation System [plain mode] fixture={args.fixture}")
    try:
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
        if action.startswith("scroll:") or action == "resize":
            apply_action(state, action)
            continue
        if action == "start":
            if state.running or worker is not None:
                continue
            stop_event = threading.Event()
            worker = start_scan_thread(state, event_queue, stop_event)
            continue


def main(argv: list[str] | None = None) -> int:
    """Entry: curses when a TTY + curses exist, else plain-text degrade."""
    if curses is None or not sys.stdin.isatty() or not sys.stdout.isatty():
        return run_plain(argv)
    parser = argparse.ArgumentParser(description="Secure Mitigation System TUI")
    parser.add_argument("--fixture", choices=list(FIXTURE_ORDER), default=FIXTURE_ORDER[0])
    args = parser.parse_args(argv)
    state = TuiState(fixture_index=list(FIXTURE_ORDER).index(args.fixture))
    try:
        curses.wrapper(_curses_main, state)
    except Exception as exc:
        print(f"TUI exited ({type(exc).__name__}); falling back to plain mode.")
        return run_plain(["--fixture", state.fixture_key])
    return 0


if __name__ == "__main__":  # pragma: no cover - manual entry
    raise SystemExit(main())
