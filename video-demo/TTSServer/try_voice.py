# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Try a voice, pass it or fail it (video-demo voice iteration loop).

Pass saves (pins the speaker tensor to `.pt` + keeps the audio); fail bans
the seed and regenerates the next candidate. Nothing is permanent until a
pass — iteration audio lives in a scratch dir, never in `samples/`.

The pin that actually holds: `torch.manual_seed(seed)` before
`sample_random_speaker()` fixes the voice embedding, AND `manual_seed=seed`
inside `InferCodeParams` fixes the token stream (installed `model/gpt.py`
samples with unseeded `torch.multinomial` otherwise — same voice, different
audio across runs; that is the drift this loop eliminates). NOTE: the
"tensor" here is ChatTTS's base16384-encoded embedding STRING (what
`sample_random_speaker()` returns); `InferCodeParams` accepts it directly
(`speaker.py:apply` takes `str | Tensor`), so the `.pt` file pins the voice
exactly as sampled. Web research (ComfyUI seed-speaker node, upstream issue
#228) confirms the pattern: manual_seed locks voice AND performance, and
lower temperature further fixes the delivery (issue #228 suggests near-zero
for maximum fixity — booth exposes `--temperature` for this).

Usage:
    python try_voice.py --seed 28 --text "Line to hear." [--out /tmp/vox]
    python try_voice.py --next --state loop.json   # draw outside banned
    python try_voice.py --pass --state loop.json --seed 28 --tensor <sha>
    python try_voice.py --fail --state loop.json --seed 29

`--seed` renders one temp file and prints the tensor hash. Listen, then
`--pass` (pins) or `--fail` (bans + draws the next candidate for you).
"""

import argparse
import contextlib
import hashlib
import json
import random
import sys
from pathlib import Path

TRY_TEXT = (
    "This is a voice test! Can you hear how I sound, from a whisper to a "
    "shout? Do you like it, really? The slow golden sunset fades over "
    "quiet lakes... while bright voices rise and fall."
)

# Best-known delivery default: upstream README lively values
# (temperature 0.3, top_P 0.7, top_K 20 — Advanced Usage pins all three), with
# the full manual_seed pin for determinism. Near-zero temperatures flatten
# prosody (user verdict 2026-11-01) — the pin, not the flatness, is what makes
# repeats identical, so this stays lively AND repeatable.
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TOP_P = 0.7
DEFAULT_TOP_K = 20

# README sentence-level expressive control (Advanced Usage) — break_6, not
# the self-intro break_4 we used before.
EXPRESSIVE_PROMPT = "[oral_2][laugh_0][break_6]"


def apply_word_breaks(text, enabled=True):
    """Opt-in README word-level control: prefix each sentence with [uv_break].

    Mirrors the self-introduction example pattern; literal default keeps clean
    text. Only ever emits [uv_break] — one of the three token-level controls
    the released model supports ([laugh], [uv_break], [lbreak]).
    """
    if not enabled:
        return text
    import re

    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return " ".join(f"[uv_break]{p}" for p in parts)


def speak_params(seed, literal=True):
    """Exact infer kwargs: verbatim path + token stream pinned to `seed`.

    Pins the full README sampling triple so our params can't silently drift
    with upstream dataclass defaults.
    """
    return {
        "skip_refine_text": bool(literal),
        "infer_seed": int(seed),
        "refine_prompt": "",
        "params_pin": {
            "manual_seed": int(seed),
            "temperature": DEFAULT_TEMPERATURE,
            "top_P": DEFAULT_TOP_P,
            "top_K": DEFAULT_TOP_K,
        },
    }


def next_candidate(banned, rng=None):
    """Draw a seed from 1-9999 outside `banned`."""
    rng = rng or random.Random()
    pool = [s for s in range(1, 10000) if s not in set(banned)]
    if not pool:
        raise ValueError("banned set exhausted the 4-digit pool")
    return rng.choice(pool)


def load_state(path):
    path = Path(path)
    if not path.is_file():
        return {"banned": [], "passed": []}
    state = json.loads(path.read_text())
    return {"banned": list(state.get("banned", [])), "passed": list(state.get("passed", []))}


def save_state(path, state):
    Path(path).write_text(json.dumps(state, indent=2))


def record_fail(state_path, seed):
    state = load_state(state_path)
    if int(seed) not in state["banned"]:
        state["banned"].append(int(seed))
    save_state(state_path, state)
    return state


def record_pass(state_path, seed, tensor_hash, filename):
    state = load_state(state_path)
    state["passed"].append({"seed": int(seed), "tensor": tensor_hash, "file": filename})
    save_state(state_path, state)
    return state


def tensor_hash(spk_emb):
    """Stable id for a speaker embedding (str or tensor)."""
    if isinstance(spk_emb, str):
        return hashlib.sha256(spk_emb.encode()).hexdigest()[:16]
    try:
        import torch

        if isinstance(spk_emb, torch.Tensor):
            return hashlib.sha256(bytes(spk_emb.detach().cpu().numpy())).hexdigest()[:16]
    except ImportError:
        pass
    return hashlib.sha256(repr(spk_emb).encode()).hexdigest()[:16]


@contextlib.contextmanager
def quiet_chattts(disabled=True):
    """Silence ChatTTS chatter (normalizer warnings, weight/infer bars).

    Display-only: ChatTTS logger levels to ERROR, HF-hub progress bars off
    (the 182-file "Loading weights" bar comes from huggingface_hub inside
    chat.load), tqdm bars off via show_tqdm=False on our params. All restored
    in the finally. Sampling path untouched — hashes are unaffected.
    """
    import logging
    import os

    targets = ["ChatTTS", "ChatTTS.core", "ChatTTS.norm", "ChatTTS.model", "utils"]
    saved_levels = {}
    saved_env = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")
    saved_tqdm = os.environ.get("TQDM_DISABLE")
    try:
        for name in targets:
            logger = logging.getLogger(name)
            saved_levels[name] = logger.level
            logger.setLevel(logging.ERROR)
        if disabled:
            os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
            os.environ["TQDM_DISABLE"] = "1"
            try:
                from huggingface_hub.utils import disable_progress_bars

                disable_progress_bars()
            except ImportError:
                pass
            try:
                from transformers.utils import logging as hf_logging

                hf_logging.disable_progress_bar()
            except ImportError:
                pass
        yield
    finally:
        for name, level in saved_levels.items():
            logging.getLogger(name).setLevel(level)
        if saved_env is None:
            os.environ.pop("HF_HUB_DISABLE_PROGRESS_BARS", None)
        else:
            os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = saved_env
        if saved_tqdm is None:
            os.environ.pop("TQDM_DISABLE", None)
        else:
            os.environ["TQDM_DISABLE"] = saved_tqdm
        try:
            from huggingface_hub.utils import enable_progress_bars

            enable_progress_bars()
        except ImportError:
            pass
        try:
            from transformers.utils import logging as hf_logging

            hf_logging.enable_progress_bar()
        except ImportError:
            pass


def render_seed(
    chat, seed, text, out_path, literal=True, temperature=DEFAULT_TEMPERATURE, word_breaks=False
):
    """Pin voice + token stream, synthesize, write wav. Returns hash.

    Applies the README sampling triple on top of the temperature override so
    `--temperature` tunes delivery without dropping the top_P/top_K pins.
    """
    import torch
    from sample_voices import check_audio_non_silent, write_wav

    spec = speak_params(seed, literal=literal)
    torch.manual_seed(spec["infer_seed"])
    spk_emb = chat.sample_random_speaker()
    digest = tensor_hash(spk_emb)
    params_infer = chat.InferCodeParams(spk_emb=spk_emb, temperature=temperature)
    for key, value in spec["params_pin"].items():
        if key != "temperature":
            setattr(params_infer, key, value)
    params_infer.show_tqdm = False
    if literal:
        params_refine = chat.RefineTextParams(prompt=spec["refine_prompt"], show_tqdm=False)
    else:
        params_refine = chat.RefineTextParams(prompt=EXPRESSIVE_PROMPT, show_tqdm=False)
    with quiet_chattts():
        wavs = chat.infer(
            [apply_word_breaks(text, enabled=word_breaks)],
            skip_refine_text=spec["skip_refine_text"],
            params_refine_text=params_refine,
            params_infer_code=params_infer,
        )
    if not wavs:
        raise RuntimeError(f"seed {seed}: ChatTTS returned no audio")
    audio = wavs[0]
    frames = audio.flatten() if len(audio.shape) > 1 else audio
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_wav(out_path, frames)
    check_audio_non_silent(out_path)
    return digest


def pin_tensor(chat, seed, pt_path):
    """Re-derive the speaker tensor for `seed` and save it to `.pt`."""
    import torch

    torch.manual_seed(int(seed))
    spk_emb = chat.sample_random_speaker()
    digest = tensor_hash(spk_emb)
    torch.save(spk_emb, str(pt_path))
    return digest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Try a voice: pass pins, fail bans")
    parser.add_argument("--seed", type=int, help="seed to try (renders temp audio)")
    parser.add_argument("--text", default=TRY_TEXT, help="phrase to synthesize")
    parser.add_argument("--out", default="try_voice.wav", help="temp output path")
    parser.add_argument("--literal", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument(
        "--word-breaks",
        action="store_true",
        help="README word-level control: prefix sentences with [uv_break]",
    )
    parser.add_argument("--next", action="store_true", help="draw next unbanned seed")
    parser.add_argument("--pass", dest="do_pass", action="store_true")
    parser.add_argument("--fail", dest="do_fail", action="store_true")
    parser.add_argument("--state", default="loop.json")
    parser.add_argument("--tensor", default="", help="tensor hash for --pass")
    parser.add_argument("--file", default="", help="audio filename for --pass")
    parser.add_argument("--pin-to", default="", help="save pinned .pt voice here")
    args = parser.parse_args(argv)

    if args.do_fail:
        if args.seed is None:
            print("--fail needs --seed", file=sys.stderr)
            return 1
        state = record_fail(args.state, args.seed)
        nxt = next_candidate(state["banned"])
        print(f"seed {args.seed} banned ({len(state['banned'])} banned). next: {nxt}")
        print(f"try it: python try_voice.py --seed {nxt} --text {args.text!r}")
        return 0

    if args.do_pass:
        if args.seed is None:
            print("--pass needs --seed", file=sys.stderr)
            return 1
        state = record_pass(
            args.state, args.seed, args.tensor, args.file or f"voice_{args.seed:04d}.mp3"
        )
        print(f"seed {args.seed} PASSED and pinned ({len(state['passed'])} passed).")
        if args.pin_to:
            try:
                import ChatTTS
            except ImportError:
                print("ChatTTS needed to pin the tensor; state recorded anyway.", file=sys.stderr)
                return 0
            chat = ChatTTS.Chat()
            if not chat.load(compile=False, source="huggingface"):
                print("weights failed to load; state recorded anyway.", file=sys.stderr)
                return 0
            digest = pin_tensor(chat, args.seed, args.pin_to)
            print(f"tensor saved to {args.pin_to} (hash {digest})")
        return 0

    if args.next:
        state = load_state(args.state)
        nxt = next_candidate(state["banned"])
        print(nxt)
        return 0

    if args.seed is None:
        print("give --seed to try, or --next / --pass / --fail", file=sys.stderr)
        return 1
    try:
        import ChatTTS
    except ImportError:
        print("ChatTTS is not installed: pip install -r requirements-tts.txt", file=sys.stderr)
        return 1
    chat = ChatTTS.Chat()
    print("[try] loading weights (cached after first run)...")
    with quiet_chattts():
        loaded = chat.load(compile=False, source="huggingface")
    if not loaded:
        print("[try] weights failed to load.", file=sys.stderr)
        return 1
    try:
        digest = render_seed(
            chat,
            args.seed,
            args.text,
            args.out,
            literal=args.literal,
            temperature=args.temperature,
            word_breaks=args.word_breaks,
        )
    except RuntimeError as exc:
        print(f"[try] seed {args.seed} failed: {exc}", file=sys.stderr)
        print("suggest: --fail this seed and try the next one", file=sys.stderr)
        return 1
    print(f"[try] seed {args.seed} -> {args.out} (tensor {digest})")
    print("listen, then: --pass (pins) or --fail (bans + next)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
