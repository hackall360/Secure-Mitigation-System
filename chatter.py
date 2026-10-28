# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Agent chatter: safe, minor, persona-voiced status summaries for the live dashboard.

Chatter rules (enforced here, not by the model):
- Only SAFE summaries: persona name, stage, counts, exit codes, path names.
- NEVER: probe source, payloads, output excerpts, file contents, secrets, CVE
  details beyond IDs, or anything that could reconstruct an exploit.
- Server builds every chatter line from trusted workflow facts. The model never
  authors chatter text. Personas select TONE templates only.
"""

from __future__ import annotations

import random
from typing import Literal

_CHATTER: dict[str, list[str]] = {
    "red_start": [
        "{persona} slipping along the shoreline, reading {path} for a way in. Security looks smug here.",
        "{persona} rattling gates in {path}. Most are locked. One feels loose.",
        "{persona} picking up a scent trail from {path}. Following it to the sink.",
    ],
    "red_proof": [
        "{persona} bottled a proof: exit {code} on {path}. Taking it to the verifier.",
        "{persona} got a bite on {path} (exit {code}). Confirming it is real, not a fluke.",
    ],
    "red_done": [
        "{persona} handed one claim to the verifier. No freelancing, one proof, done.",
        "{persona} reporting back: one testable claim, rest is noise.",
    ],
    "blue_start": [
        "{persona} raising a wall around {path}. Small wall, strong mortar.",
        "{persona} threading a needle near {path}. Tiniest stitch that holds.",
    ],
    "blue_done": [
        "{persona} patch set: exit {code} after re-probe. The gate holds and the road stays open.",
        "{persona} stitched it shut. Valid input still flows, the probe does not.",
    ],
    "leader_red": [
        "Warlord splitting the surface into {n} sectors. Hunters, take your ground. One proof each.",
        "Warlord: {n} hunters out, {n} sectors. Report back with evidence or silence.",
    ],
    "leader_blue": [
        "Warden raising {n} walls. Defenders, hold your line. Smallest patch that holds.",
        "Warden: {n} defenders on the boundary. No grand redesigns. Stitch and verify.",
    ],
    "green": [
        "Greenhouse planted a new demo: {n} wobbly joints and one CVE-inspired weed. Have fun, you two.",
        "Greenhouse: fresh seedlings in {path}. I left the gaps in. Do not ask me about security.",
    ],
}


def chatter(
    kind: str,
    *,
    persona: str = "",
    path: str = "",
    code: int | None = None,
    n: int = 0,
    seed: int | None = None,
) -> str:
    """Build one safe chatter line. All inputs are trusted workflow facts or names."""
    templates = _CHATTER.get(kind, ["{persona} checking in."])
    rng = random.Random(seed if seed is not None else hash((kind, persona, path, code, n)))
    template = rng.choice(templates)
    # Keep path to basename to avoid leaking deep structure; never include contents.
    short_path = path.rsplit("/", 1)[-1][:64] if path else "the boundary"
    line = template.format(persona=persona[:24] or "Agent", path=short_path, code=code, n=n)
    # Hard ceiling: minor summaries only.
    return line[:220]


def wire_chatter(
    emit,
    team: Literal["red", "blue", "system", "green"],
    kind: str,
    **kwargs,
):
    """Return an async sender for one chatter line over the log pipeline."""

    async def _send():
        try:
            await emit(
                team if team in ("red", "blue", "system") else "system", chatter(kind, **kwargs)
            )
        except Exception:
            pass

    return _send
