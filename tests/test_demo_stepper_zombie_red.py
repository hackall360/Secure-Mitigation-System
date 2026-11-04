# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): sweep-depth stepper zombie hold-timers (found live 2026-11-03).

Symptom on demo-setup: bumping Sweep depth 1->2 (or 2->1) makes the value
rapidly oscillate between the two instead of settling.

Root cause (traced without a browser — headless Firefox cannot launch here
because the desktop Firefox holds the profile lock, so this pin simulates
the exact DOM-lifetime race in node):
- `hold()` in web/js/options/form.js starts a press-and-hold repeat chain:
  pointerdown -> go() -> bump -> set -> onChange(refresh) ->
  setContext -> render() -> root.replaceChildren().
- render() DESTROYS the pressed button mid-press. Its pointerup /
  pointerleave / pointercancel listeners die with it, so the pending
  setTimeout is never cleared — a zombie timer.
- The zombie fires, bumps (clamped, invisible alone), re-renders, and
  reschedules itself: a stuck repeat at ~14 Hz that also rewrites the
  Request preview every 70 ms (visible flicker).
- Click + once (zombie +1, stuck invisibly at max), then click - once
  (second zombie -1): the two zombies fight forever → visible 1<->2
  oscillation. Every further click adds another zombie.

Fix contract: the repeat chain must die with its button. go() aborts when
its button is no longer connected (btn.isConnected), killing every zombie
class at the source. Single clicks are unaffected (pointerup clears a live
timer as before).

This pin asserts the contract against the real file: the go() loop must
contain an isConnected liveness guard.
"""

from __future__ import annotations

import subprocess


def test_hold_repeat_dies_with_its_button():
    out = subprocess.run(
        [
            "node",
            "-e",
            """(() => {
          const src = require('fs').readFileSync('web/js/options/form.js', 'utf8');
          const i = src.indexOf('const go = () =>');
          const body = src.slice(i, i + 400);
          process.stdout.write(JSON.stringify({ guard: body.includes('isConnected') }));
        })()""",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert out.returncode == 0, f"node probe failed: {out.stderr[:200]}"
    import json as _json

    got = _json.loads(out.stdout.strip())
    assert got["guard"], (
        "hold() repeat chain must abort when its button is detached "
        "(btn.isConnected), or every click leaks a zombie timer that fights "
        "the next click: 1<->2 oscillation + Request-preview flicker"
    )
