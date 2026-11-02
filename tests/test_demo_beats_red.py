# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (P1-3/Wave 1.2): 3-minute demo beat sheet contract. Now GREEN.

- `docs/DEMO_SCRIPT.md` is a timed beat sheet: 7+ beats with `MM:SS-MM:SS`
  ranges, cumulative end <= 180.0 s, per-beat narration stems (one line,
  <= 200 chars each, <= 2400 chars total, text-only TTS stems).
- `web/js/stream/scenario.js` carries a pure-data `BEATS` array whose
  timestamps/stems/stages match the doc beats 1:1 (stage keys must be real
  `STAGES` keys from `web/js/core/palette.js`, i.e. stages `caption()` in
  `web/js/pages/demo.js` understands).
- TTS stems are TEXT ONLY (booth seed 6420 @ t0.3): no audio rendering.

RED proof: pre-change run fails (files absent).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "DEMO_SCRIPT.md"
SCENARIO = ROOT / "web" / "js" / "stream" / "scenario.js"
PALETTE = ROOT / "web" / "js" / "core" / "palette.js"

HEADER_RE = re.compile(
    r"^## Beat (\d+) - (.+?) \((\d+:\d+)-(\d+:\d+), stage: (\w+), stem: ([\w-]+)\)"
)
NARR_RE = re.compile(r'^- Narration: "([^"]*)"')
JS_BEAT_RE = re.compile(
    r"\{\s*range:\s*'(\d+:\d+-\d+:\d+)'\s*,\s*stage:\s*'(\w+)'\s*,"
    r"\s*stem:\s*'([\w-]+)'\s*,\s*narration:\s*'([^']*)'",
)


def mmss(s):
    m, sec = s.split(":")
    return int(m) * 60 + int(sec)


def parse_doc_beats():
    assert DOC.exists(), f"RED: missing beat sheet {DOC}"
    text = DOC.read_text()
    beats = []
    current = None
    for line in text.splitlines():
        h = HEADER_RE.match(line.strip())
        if h:
            if current:
                beats.append(current)
            num, _title, start, end, stage, stem = h.groups()
            current = {
                "num": int(num),
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
    return text, beats


def test_doc_beats_timed_and_speakable():
    text, beats = parse_doc_beats()
    assert len(beats) >= 7, f"RED: need 7+ beats, found {len(beats)}"
    assert [b["num"] for b in beats] == list(range(1, len(beats) + 1)), (
        "RED: beats must be numbered 1..N contiguously"
    )
    assert mmss(beats[0]["start"]) == 0, "RED: beat sheet must start at 0:00"
    for prev, cur in zip(beats, beats[1:], strict=False):
        assert mmss(cur["start"]) == mmss(prev["end"]), (
            f"RED: gap/overlap between beats ending {prev['end']} and starting {cur['start']}"
        )
    total_end = mmss(beats[-1]["end"])
    assert total_end <= 180.0, f"RED: cumulative {total_end}s exceeds 180.0 s budget"
    total_chars = 0
    for b in beats:
        assert b["narration"], f"RED: beat {b['num']} missing one-line Narration stem"
        assert len(b["narration"]) <= 200, (
            f"RED: beat {b['num']} stem {len(b['narration'])} chars exceeds 200"
        )
        total_chars += len(b["narration"])
    assert total_chars <= 2400, (
        f"RED: total narration {total_chars} chars exceeds 2400 (800 chars/min over 3 min)"
    )


def test_doc_tts_text_only():
    text, _ = parse_doc_beats()
    assert "6420" in text, "RED: doc must reference booth seed 6420 (@ t0.3)"
    assert ".wav" not in text.lower(), "RED: no audio files may be generated"
    assert "text-only" in text.lower(), "RED: stems must be declared text-only"


def parse_js_beats():
    assert SCENARIO.exists(), f"RED: missing replay rig {SCENARIO}"
    src = SCENARIO.read_text()
    assert "BEATS" in src, "RED: scenario.js has no BEATS array"
    m = re.search(r"(?:const|var|let)\s+BEATS\s*=\s*\[(.*?)\];", src, re.S)
    assert m, "RED: scenario.js must define a BEATS array literal"
    beats = [
        {"range": r, "stage": s, "stem": t, "narration": n}
        for (r, s, t, n) in JS_BEAT_RE.findall(m.group(1))
    ]
    assert beats, "RED: BEATS array has no parseable {range, stage, stem, narration} entries"
    return src, beats


def test_js_beats_match_doc_one_to_one():
    _, doc_beats = parse_doc_beats()
    _, js_beats = parse_js_beats()
    assert len(js_beats) == len(doc_beats), (
        f"RED: BEATS count {len(js_beats)} != doc beats {len(doc_beats)}"
    )
    for doc, js in zip(doc_beats, js_beats, strict=True):
        want = f"{doc['start']}-{doc['end']}"
        assert js["range"] == want, f"RED: BEATS range {js['range']} != doc {want}"
        assert js["stage"] == doc["stage"], (
            f"RED: BEATS stage {js['stage']} != doc {doc['stage']} ({want})"
        )
        assert js["stem"] == doc["stem"], (
            f"RED: BEATS stem {js['stem']} != doc {doc['stem']} ({want})"
        )
        assert js["narration"] == doc["narration"], (
            f"RED: BEATS narration != doc narration ({want})"
        )


def test_js_beat_stages_presenter_valid():
    _, js_beats = parse_js_beats()
    pal = PALETTE.read_text()
    m = re.search(r"const STAGES = \[(.*?)\]", pal, re.S)
    assert m, "RED: cannot find STAGES list in palette.js"
    valid = set(re.findall(r"'(\w+)'", m.group(1)))
    assert valid, "RED: no stage keys parsed from palette.js"
    for b in js_beats:
        assert b["stage"] in valid, (
            f"RED: stage '{b['stage']}' not understood by caption() (valid: {sorted(valid)})"
        )
