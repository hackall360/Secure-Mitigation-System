# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Machine driver for the 3-minute demo beat sheet (rubric P2-5, Wave 1.2).

Reads the beat file ``docs/DEMO_SCRIPT.md`` and either prints the timed
plan (``--dry-run``, the default), walks an operator through it live
against a running server (``--live``), or asserts the doc beats match the
replay-rig ``BEATS`` array in ``web/js/stream/scenario.js`` 1:1
(``--check-beats``).

Stdlib only (``urllib``, ``json``, ``argparse``, ``time``; plus ``re`` and
``pathlib`` for beat parsing); localhost + short timeout on every I/O call
per LAW 10I, mirroring ``scripts/mcp_client_demo.py`` patterns.

NO-AUDIO GUARANTEE: this driver never renders audio, never contacts a TTS
server, and never spawns a browser. Narration stems are printed as text for
the human presenter (or a future agent presenter step) to speak. The
``/ws/demo`` endpoint is a websocket, so ``--live`` does not POST beats to
it; instead it prints a ``T+Xs`` schedule the operator follows and
busy-polls ``GET /api/health`` between beats to prove the server is alive.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC = ROOT / "docs" / "DEMO_SCRIPT.md"
DEFAULT_SCENARIO = ROOT / "web" / "js" / "stream" / "scenario.js"

#: Demo driver talks to loopback only; short timeout bounds every I/O call.
DEFAULT_TIMEOUT = 10.0

#: Hard 3-minute budget for the whole beat sheet.
BUDGET_SECONDS = 180.0

# NOTE: the three regexes below are copied verbatim from
# tests/test_demo_beats_red.py. Keep them character-identical so the driver
# and the contract test can never drift apart.
HEADER_RE = re.compile(
    r"^## Beat (\d+) - (.+?) \((\d+:\d+)-(\d+:\d+), stage: (\w+), stem: ([\w-]+)\)"
)
NARR_RE = re.compile(r'^- Narration: "([^"]*)"')
JS_BEAT_RE = re.compile(
    r"\{\s*range:\s*'(\d+:\d+-\d+:\d+)'\s*,\s*stage:\s*'(\w+)'\s*,"
    r"\s*stem:\s*'([\w-]+)'\s*,\s*narration:\s*'([^']*)'",
)


def mmss(s: str) -> float:
    """Parse an ``M:SS`` timestamp into seconds."""
    m, sec = s.split(":")
    return float(int(m) * 60 + int(sec))


def parse_doc_beats(doc: Path | None = None) -> list[dict]:
    """Parse beat headers + narration stems from the beat file.

    Uses the same header/narration regexes as ``test_demo_beats_red.py``.
    Returns one dict per beat: ``num/start/end/stage/stem/narration``.
    """
    path = Path(doc) if doc is not None else DEFAULT_DOC
    beats: list[dict] = []
    current: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        h = HEADER_RE.match(line.strip())
        if h:
            if current:
                beats.append(current)
            num, title, start, end, stage, stem = h.groups()
            current = {
                "num": int(num),
                "title": title,
                "start": start,
                "end": end,
                "stage": stage,
                "stem": stem,
                "narration": None,
            }
            continue
        if current and current["narration"] is None:
            n = NARR_RE.match(line.strip())
            if n:
                current["narration"] = n.group(1)
    if current:
        beats.append(current)
    return beats


def parse_js_beats(scenario: Path | None = None) -> list[dict]:
    """Parse the ``BEATS`` array literal from ``web/js/stream/scenario.js``."""
    path = Path(scenario) if scenario is not None else DEFAULT_SCENARIO
    src = path.read_text(encoding="utf-8")
    m = re.search(r"(?:const|var|let)\s+BEATS\s*=\s*\[(.*?)\];", src, re.S)
    if not m:
        return []
    return [
        {"range": r, "stage": s, "stem": t, "narration": n}
        for (r, s, t, n) in JS_BEAT_RE.findall(m.group(1))
    ]


def cumulative_end(beats: list[dict]) -> float:
    """Cumulative end of the sheet in seconds (end of the last beat)."""
    if not beats:
        return 0.0
    return mmss(beats[-1]["end"])


def check_beats(
    doc: Path | None = None, scenario: Path | None = None
) -> list[str]:
    """Assert doc beats == scenario.js BEATS 1:1; return drift lines (empty = clean)."""
    doc_beats = parse_doc_beats(doc)
    js_beats = parse_js_beats(scenario)
    drift: list[str] = []
    if len(js_beats) != len(doc_beats):
        drift.append(
            f"count drift: BEATS has {len(js_beats)} entries, doc has {len(doc_beats)} beats"
        )
        return drift
    for doc_b, js_b in zip(doc_beats, js_beats, strict=True):
        want = f"{doc_b['start']}-{doc_b['end']}"
        for key, got in (
            ("range", js_b["range"]),
            ("stage", js_b["stage"]),
            ("stem", js_b["stem"]),
            ("narration", js_b["narration"]),
        ):
            want_val = want if key == "range" else doc_b[key]
            if got != want_val:
                drift.append(
                    f"{key} drift at doc beat {doc_b['num']} ({want}): "
                    f"BEATS {got!r} != doc {want_val!r}"
                )
    return drift


def run_dry_run(doc: Path | None = None) -> int:
    """Print the timed beat plan with cumulative timestamps; exit 0 iff <= budget."""
    beats = parse_doc_beats(doc)
    if not beats:
        print("dry-run failed: no beats parsed from the beat file")
        return 1
    elapsed = 0.0
    for i, b in enumerate(beats, start=1):
        dur = mmss(b["end"]) - mmss(b["start"])
        print(
            f"Beat {i}/{len(beats)} T+{elapsed:.1f}s "
            f"({b['start']}-{b['end']}, {dur:.1f}s) "
            f"[{b['stage']}] {b['stem']}: \"{b['narration']}\""
        )
        elapsed = mmss(b["end"])
    total = cumulative_end(beats)
    status = "OK" if total <= BUDGET_SECONDS else "OVER BUDGET"
    print(
        f"Total: {len(beats)} beats, cumulative end T+{total:.1f}s "
        f"<= {BUDGET_SECONDS:.1f}s budget — {status}"
    )
    return 0 if total <= BUDGET_SECONDS else 1


def _health_poll(base_url: str, *, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """GET ``<base_url>/api/health`` and return the decoded JSON body.

    Localhost only; fail closed with ``ConnectionError``/``TimeoutError``/
    ``ValueError`` exactly like ``mcp_client_demo._post_rpc``.
    """
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(f"demo driver connects to localhost only, got {base_url!r}")
    url = base_url.rstrip("/") + "/api/health"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.URLError as exc:
        reason = exc.reason
        detail = str(reason) if reason is not None else str(exc)
        lowered = detail.lower()
        if "refused" in lowered:
            raise ConnectionError(f"connection refused at {url} ({detail})") from exc
        if "timed out" in lowered or isinstance(reason, TimeoutError):
            raise TimeoutError(f"health poll timed out after {timeout}s at {url}") from exc
        raise ConnectionError(f"health endpoint unreachable at {url} ({detail})") from exc
    except TimeoutError as exc:
        raise TimeoutError(f"health poll timed out after {timeout}s at {url}") from exc
    except OSError as exc:
        raise ConnectionError(f"health endpoint failed at {url} ({exc})") from exc
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"health endpoint returned non-JSON at {url}") from exc
    if not isinstance(body, dict):
        raise ValueError(f"health endpoint returned a non-object body at {url}")
    return body


def run_live(
    base_url: str,
    doc: Path | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    pace: float = 1.0,
) -> int:
    """Walk the operator through the beats with sleep pacing.

    Prints one ``T+Xs: <stage> — <narration>`` line per beat (text only, no
    audio, no TTS, no browser), sleeps each beat's duration scaled by
    ``pace``, and busy-polls ``GET /api/health`` between beats to prove the
    server is alive. Fail closed (non-zero exit) when the server is
    unreachable at the start.
    """
    beats = parse_doc_beats(doc)
    if not beats:
        print("live failed: no beats parsed from the beat file")
        return 1
    try:
        _health_poll(base_url, timeout=timeout)
    except (ConnectionError, TimeoutError, ValueError) as exc:
        print(f"live failed: server not alive at {base_url} ({exc})")
        return 1
    print(f"live: server alive at {base_url}; {len(beats)} beats, operator follows:")
    for b in beats:
        start = mmss(b["start"])
        print(f"T+{start:.0f}s: <{b['stage']}> {b['stem']} \u2014 {b['narration']}")
        dur = (mmss(b["end"]) - start) * pace
        if dur > 0 and pace > 0:
            time.sleep(dur)
        try:
            _health_poll(base_url, timeout=timeout)
            print(f"  [health ok @ T+{mmss(b['end']):.0f}s]")
        except (ConnectionError, TimeoutError, ValueError) as exc:
            print(f"  [health WARNING @ T+{mmss(b['end']):.0f}s: {exc}]")
    print(f"live: done, cumulative end T+{cumulative_end(beats):.1f}s")
    return 0


def run_check_beats(doc: Path | None = None, scenario: Path | None = None) -> int:
    """Exit 0 iff doc beats == scenario.js BEATS 1:1 (range/stage/stem/narration)."""
    drift = check_beats(doc, scenario)
    if drift:
        print(f"check-beats FAILED: {len(drift)} drift line(s):")
        for line in drift:
            print(f"  - {line}")
        return 1
    print(
        f"check-beats OK: {len(parse_doc_beats(doc))} doc beats "
        "match scenario.js BEATS 1:1"
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Machine driver for docs/DEMO_SCRIPT.md: print the timed beat "
        "plan (--dry-run, default), walk an operator through it live (--live), "
        "or assert the doc beats match scenario.js BEATS 1:1 (--check-beats). "
        "Text only: never renders audio, never contacts TTS, never spawns a browser.",
        epilog="Beat file: docs/DEMO_SCRIPT.md (7 beats, cumulative end 180.0 s). "
        "Replay rig: web/js/stream/scenario.js BEATS array.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the timed beat plan with cumulative timestamps (default action)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Emit the T+Xs operator schedule with sleep pacing against a live server",
    )
    parser.add_argument(
        "--check-beats",
        action="store_true",
        help="Assert doc beats == scenario.js BEATS 1:1, exit non-zero on drift",
    )
    parser.add_argument(
        "--base",
        default="http://127.0.0.1:8000",
        help="Server base URL for --live (localhost only; default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--doc",
        default=str(DEFAULT_DOC),
        help="Beat file to parse (default: docs/DEMO_SCRIPT.md)",
    )
    parser.add_argument(
        "--scenario",
        default=str(DEFAULT_SCENARIO),
        help="Replay rig to compare (default: web/js/stream/scenario.js)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Seconds per health-poll HTTP call (default: {DEFAULT_TIMEOUT:g})",
    )
    parser.add_argument(
        "--pace",
        type=float,
        default=1.0,
        help="Sleep scale for --live beat pacing, 0 disables sleeps (default: 1.0)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry: dispatch one action, return the exit code (no SystemExit)."""
    args = _build_parser().parse_args(argv)
    doc = Path(args.doc)
    scenario = Path(args.scenario)
    if not doc.exists():
        print(f"demo driver failed: beat file not found: {doc}")
        return 1
    if args.check_beats:
        if not scenario.exists():
            print(f"demo driver failed: scenario rig not found: {scenario}")
            return 1
        return run_check_beats(doc, scenario)
    if args.live:
        return run_live(args.base, doc, timeout=args.timeout, pace=args.pace)
    return run_dry_run(doc)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
