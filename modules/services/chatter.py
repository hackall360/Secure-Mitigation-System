# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Agent chatter: safe, minor, persona-voiced status summaries for the live dashboard.

Chatter rules (enforced here, not by the model):
- Only SAFE summaries: persona name, stage, counts, exit codes, path names.
- NEVER: probe source, payloads, output excerpts, file contents, secrets, CVE
  details beyond IDs, or anything that could reconstruct an exploit.
- Server builds every chatter line from trusted workflow facts. The model never
  authors chatter text. Personas select TONE templates only.
- Model-active lines ("model_active") report which Muse model is active, which
  phase (usage role), and token/reasoning facts already in pricing.CallUsage.
  No prompts, completions, payloads, or secrets — counts and ids only.
"""

from __future__ import annotations

import random

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
    # Model-active lines: which Muse model is active, which phase (usage role),
    # and how much it reasoned (reasoning tokens, already in pricing.CallUsage).
    # Counts and ids only — never prompts, completions, or payloads.
    "model_active": [
        "{persona} has {model} on the {phase} phase: {n} reasoning tokens banked, reading the boundary before writing.",
        "{persona} letting {model} reason through {phase}: {n} thought-tokens counted, ledger open, no shortcuts.",
        "{persona} watching {model} work {phase}: {n} reasoning tokens so far, every one on the ledger.",
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
    model: str = "",
    phase: str = "",
) -> str:
    """Build one safe chatter line. All inputs are trusted workflow facts or names."""
    templates = _CHATTER.get(kind, ["{persona} checking in."])
    rng = random.Random(seed if seed is not None else hash((kind, persona, path, code, n)))
    template = rng.choice(templates)
    # Keep path to basename to avoid leaking deep structure; never include contents.
    # Collapse whitespace (incl. newlines) so hostile names cannot inject log lines.
    short_path = path.rsplit("/", 1)[-1][:64] if path else "the boundary"
    short_path = " ".join(short_path.split())
    safe_persona = " ".join((persona[:24] or "Agent").split())
    # Model-active lines name a Muse model id and a usage phase (role): ids only,
    # never prompts or completions. Allowlist chars so hostile ids stay inert text.
    safe_model = "".join(c for c in model[:48] if c.isalnum() or c in "._-") or "unknown-model"
    safe_phase = "".join(c for c in phase[:24] if c.isalnum() or c in "_-") or "unknown-phase"
    try:
        safe_code = int(code) if code is not None else 0
    except (TypeError, ValueError):
        safe_code = 0
    try:
        safe_n = int(n)
    except (TypeError, ValueError):
        safe_n = 0
    line = template.format(
        persona=safe_persona,
        path=short_path,
        code=safe_code,
        n=safe_n,
        model=safe_model,
        phase=safe_phase,
    )
    # Minor summaries must not carry code-shaped runs (e.g. dunders from hostile
    # punctuation); collapse them so fuzzed names stay inert text.
    while "__" in line:
        line = line.replace("__", "_")
    # Hard ceiling: minor summaries only.
    return line[:220]


def socket_emit(socket):
    """Build a WebSocket Emit: forwards (team, message) as log frames to one client."""

    async def emit(team: str, message: str) -> None:
        await socket.send_json({"team": team, "msg": message, "type": "log"})

    return emit
