# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Dev/prod observability: per-aspect JSONL logs, metrics, and traces (stdlib only).

Layout (never giant blobs): ``<root>/<signal>/<aspect>.jsonl`` with signals
``logs`` | ``metrics`` | ``traces`` and aspects like ``workflows.fixture``.
One JSON object per line; fixed keys (``ts``, ``aspect``, ``event``, ``mode``
+ signal payload) so the tree is trivially ingestible later.

Modes: ``prod`` (default) records milestones — scan start/verdict, errors,
trace open/close. ``dev`` additionally records ~10 detail records per
milestone (phase transitions, payload sizes, durations, decisions), i.e.
roughly 10x the records on the same run. Mode resolves from the explicit
argument, else ``PURPLEBOX_OBSERVABILITY_MODE`` (``dev``|``prod``), else
``prod`` (fail-closed: less output, less surface).

LAW 4: values that look like secrets (``api_key``, ``*token*``,
``*secret*``, ``*password*``, ``sk-``/``sk_``-prefixed strings) are replaced
with ``REDACTED`` before they touch disk. Never logs keys, never intel
verbatim beyond what the caller passes already-redacted.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SIGNALS = ("logs", "metrics", "traces")
DEFAULT_MODE = "prod"
MODES = ("dev", "prod")
ENV_VAR = "PURPLEBOX_OBSERVABILITY_MODE"

#: Detail records emitted per milestone in dev mode (the ~10x factor).
DEV_DETAIL_FANOUT = 10

_lock = threading.Lock()
_state: dict[str, Any] = {"root": None, "mode": DEFAULT_MODE, "metrics": []}


def resolve_mode(explicit: str | None) -> str:
    """Resolve dev|prod: explicit override, else env, else prod default."""
    if explicit is not None:
        if explicit not in MODES:
            raise ValueError(f"observability mode must be dev|prod, got {explicit!r}")
        return explicit
    env = os.getenv(ENV_VAR, "").strip().lower()
    if not env:
        return DEFAULT_MODE
    if env not in MODES:
        raise ValueError(f"{ENV_VAR} must be dev|prod, got {env!r}")
    return env


def init(root: str | Path | None = None, mode: str | None = None) -> str:
    """Open the sink tree. Returns the resolved mode. Idempotent per process."""
    resolved = resolve_mode(mode)
    with _lock:
        _state["root"] = Path(root) if root is not None else Path("logs")
        _state["mode"] = resolved
        _state["metrics"] = []
        for signal in SIGNALS:
            (_state["root"] / signal).mkdir(parents=True, exist_ok=True)
    return resolved


def shutdown() -> None:
    """Flush the per-run metrics summary. Safe to call without init."""
    with _lock:
        root = _state["root"]
        if root is None:
            return
        summary = {
            "ts": _now(),
            "mode": _state["mode"],
            "metrics": list(_state["metrics"]),
        }
        (root / "metrics" / "_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        _state["root"] = None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() % 1 * 1000):03d}Z"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("REDACTED" if _looks_secret(k, v) else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    if isinstance(value, str) and _looks_secret("", value):
        return "REDACTED"
    return value


def _looks_secret(key: str, value: Any = None) -> bool:
    lowered = key.lower()
    if any(token in lowered for token in ("api_key", "apikey", "token", "secret", "password", "auth")):
        return True
    if isinstance(value, str) and len(value) >= 12:
        marker = value[:7].lower().replace("_", "-")
        if marker.startswith("sk-live") or marker.startswith("sk-ant") or marker.startswith("sk-"):
            return True
    return False


def _append(signal: str, aspect: str, record: dict[str, Any]) -> None:
    with _lock:
        root = _state["root"]
        if root is None:
            return
        path = root / signal / f"{aspect}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


class Aspect:
    """One named surface (e.g. ``workflows.fixture``). Cheap handle; no I/O."""

    def __init__(self, name: str):
        self.name = name


def get_aspect(name: str) -> Aspect:
    """Return the handle for an aspect (dots separate area from surface)."""
    if not name or not all(part.isidentifier() for part in name.split(".")):
        raise ValueError(f"aspect must be dotted identifiers, got {name!r}")
    return Aspect(name)


def _dev_details(event: str, fields: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Expand one milestone into ~10 dev-only detail records."""
    details = [
        ("phase_enter", {"phase": event}),
        ("phase_fields", {"field_count": len(fields)}),
        ("payload_shape", {"keys": sorted(str(k) for k in fields)}),
        ("decision_point", {"event": event}),
        ("pre_state", {"event": event}),
        ("post_state", {"event": event}),
        ("timing_mark", {"event": event}),
        ("context_sizes", {k: len(str(v)) for k, v in list(fields.items())[:4] or [("empty", 0)]}),
        ("why", {"reason": f"{event} reached in dev trace"}),
        ("where", {"aspect_hint": event}),
    ]
    return details[:DEV_DETAIL_FANOUT]


def log(aspect: Aspect | str, event: str, message: str = "", **fields: Any) -> None:
    """Record a log line (prod: milestone; dev: milestone + details)."""
    name = aspect.name if isinstance(aspect, Aspect) else aspect
    with _lock:
        mode = _state["mode"]
    clean = _redact(fields)
    base: dict[str, Any] = {
        "ts": _now(),
        "aspect": name,
        "event": event,
        "mode": mode,
        "message": message,
    }
    if clean:
        base["fields"] = clean
    _append("logs", name, base)
    if mode == "dev":
        for detail_event, detail_fields in _dev_details(event, clean if isinstance(clean, dict) else {}):
            _append(
                "logs",
                name,
                {
                    "ts": _now(),
                    "aspect": name,
                    "event": f"{event}.{detail_event}",
                    "mode": mode,
                    "message": f"dev detail: {detail_event} for {event}",
                    "fields": _redact(detail_fields),
                },
            )


def record_metric(aspect: Aspect | str, name: str, value: float | int, unit: str = "count") -> None:
    """Record one metric sample + accumulate it for the run summary."""
    aspect_name = aspect.name if isinstance(aspect, Aspect) else aspect
    with _lock:
        mode = _state["mode"]
        entry = {"name": name, "value": value, "unit": unit, "aspect": aspect_name}
        _state["metrics"].append(entry)
    _append(
        "metrics",
        aspect_name,
        {"ts": _now(), "aspect": aspect_name, "event": name, "mode": mode, "value": value, "unit": unit},
    )


class Span:
    """Open trace span; ``trace()`` fills status/duration on close."""

    def __init__(self, aspect: str, operation: str):
        self.aspect = aspect
        self.operation = operation
        self.trace_id = uuid.uuid4().hex
        self.span_id = uuid.uuid4().hex[:16]
        self.status = "ok"
        self.error: dict[str, Any] = {}
        self._start = time.monotonic()

    @property
    def duration_ms(self) -> float:
        return round((time.monotonic() - self._start) * 1000, 3)


@contextmanager
def trace(aspect: Aspect | str, operation: str):
    """Open a span; writes one trace record on close (ok or error)."""
    name = aspect.name if isinstance(aspect, Aspect) else aspect
    with _lock:
        mode = _state["mode"]
    span = Span(name, operation)
    try:
        yield span
    except Exception as exc:  # noqa: BLE001 (trace must record, then re-raise)
        span.status = "error"
        span.error = {"type": type(exc).__name__, "message": str(exc)[:500]}
        raise
    finally:
        record: dict[str, Any] = {
            "ts": _now(),
            "aspect": name,
            "event": operation,
            "mode": mode,
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "duration_ms": span.duration_ms,
            "status": span.status,
        }
        if span.error:
            record["error"] = _redact(span.error)
        _append("traces", name, record)
