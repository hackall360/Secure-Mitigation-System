# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Generate one voice sample per random seed (video-demo voice gauging).

Each run draws N unique random seeds of fixed digit-length, synthesizes the
same test line once per seed — each with its own sampled speaker voice — and
writes one audio file per seed plus a manifest mapping seed -> file.

Voice control: ChatTTS voices come from `sample_random_speaker()`, which draws
from torch's global RNG. Seeding `torch.manual_seed(seed)` before sampling
pins the voice deterministically (verified against ChatTTS `model/speaker.py`:
`torch.randn` with no generator argument). Same seed => same voice.

Usage:
    python sample_voices.py [--count 10] [--digits 4] [--out samples]
                            [--format mp3|wav] [--compile] [--device cuda]

Needs `requirements-tts.txt` + weights (first run downloads the 2Noise/ChatTTS
snapshot into the HF cache — OUTSIDE the repo). mp3 encoding shells to ffmpeg;
wav is the fallback when ffmpeg is absent.
"""

import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

SAMPLE_TEXT = (
    "This is a voice test! I hope you enjoy how I sound. "
    "Pen pineapple apple pen. Pen, Pineapple, Apple, pen."
)
SAMPLE_RATE = 24000

# Seeds the user rejected (word-merging batch, 2026-11-01) — never reuse.
BANNED_SEEDS = frozenset({5923, 8059, 6623, 6338, 4545, 2235, 3823, 7908, 3217, 4967})

# Literal-mode sampling: verbatim path (skip refine, empty prompt) with
# upstream lively sampling (temperature 0.3, top_K 20) — the manual_seed pin
# carries determinism, so delivery stays expressive AND repeatable. Near-zero
# temperatures were tried and sounded monotone (brief 2026-11-01-monotone-fix).
LITERAL_TEMPERATURE = 0.3
LITERAL_TOP_K = 20


def literal_params(temperature=LITERAL_TEMPERATURE):
    """Build (infer_code, refine_text, infer_kwargs) for verbatim delivery.

    Needs the real ChatTTS classes, so this imports ChatTTS lazily and is only
    called on synthesis paths — unit tests that pin these values run against
    the installed package, not a stub.
    """
    import ChatTTS

    infer_code = ChatTTS.Chat.InferCodeParams(temperature=LITERAL_TEMPERATURE, top_K=LITERAL_TOP_K)
    refine_text = ChatTTS.Chat.RefineTextParams(prompt="")
    return infer_code, refine_text, {"skip_refine_text": True}


def generate_seeds(count, digits, rng=None):
    """Draw `count` UNIQUE ints with exactly `digits` digits (length 4: 1000-9999).

    The 10 user-rejected seeds (BANNED_SEEDS) are never returned.
    """
    if digits < 1:
        raise ValueError("digits must be >= 1")
    lo = 10 ** (digits - 1) if digits > 1 else 0
    hi = (10**digits) - 1
    pool = [s for s in range(lo, hi + 1) if s not in BANNED_SEEDS]
    if count > len(pool):
        raise ValueError(f"cannot draw {count} unique {digits}-digit seeds")
    rng = rng or random.Random()
    return rng.sample(pool, count)


def sample_filename(seed, ext):
    return f"voice_{int(seed):04d}.{ext}"


def check_audio_non_silent(path, min_seconds=0.5):
    """Fail closed: refuse to ship a missing/empty/near-silent file."""
    import wave

    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        seconds = frames / wav.getframerate()
        raw = wav.readframes(frames)
    if seconds < min_seconds:
        raise RuntimeError(f"{path}: only {seconds:.2f}s, expected >= {min_seconds}s")
    peak = max(
        abs(int.from_bytes(raw[i : i + 2], "little", signed=True)) for i in range(0, len(raw), 2)
    )
    if peak < 100:
        raise RuntimeError(f"{path}: peak amplitude {peak}, looks silent")
    return seconds


def write_wav(path, frames, sample_rate=SAMPLE_RATE):
    import array
    import wave

    pcm = array.array("h")
    for sample in frames:
        pcm.append(int(max(-1.0, min(1.0, float(sample))) * 32767))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def to_mp3(wav_path, mp3_path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    result = subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-i", str(wav_path), str(mp3_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0 or not mp3_path.is_file():
        print(f"[voices] ffmpeg failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def synthesize_for_seed(chat, seed, literal=True):
    """Pin voice via torch seed, sample speaker, synthesize the test line.

    literal=True (default): skip the refine pass and decode greedily so the
    model reads the words as written. literal=False restores the original
    expressive behavior (oral/laugh/break refine prompt, temperature 0.3).
    """
    import torch

    torch.manual_seed(int(seed))
    spk = chat.sample_random_speaker()
    if literal:
        params_infer, params_refine, infer_kwargs = literal_params()
        params_infer.spk_emb = spk
        wavs = chat.infer(
            [SAMPLE_TEXT],
            params_refine_text=params_refine,
            params_infer_code=params_infer,
            **infer_kwargs,
        )
    else:
        params_infer = chat.InferCodeParams(spk_emb=spk, temperature=0.3)
        params_refine = chat.RefineTextParams(prompt="[oral_2][laugh_0][break_4]")
        wavs = chat.infer(
            [SAMPLE_TEXT],
            skip_refine_text=False,
            params_refine_text=params_refine,
            params_infer_code=params_infer,
        )
    if not wavs:
        raise RuntimeError(f"seed {seed}: ChatTTS returned no audio")
    audio = wavs[0]
    return audio.flatten() if len(audio.shape) > 1 else audio


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sample one voice per random seed")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--digits", type=int, default=4)
    parser.add_argument("--out", default="samples")
    parser.add_argument("--format", choices=("mp3", "wav"), default="mp3")
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--expressive",
        action="store_true",
        help="restore the original oral/laugh/break refine style (default is literal)",
    )
    args = parser.parse_args(argv)

    try:
        import ChatTTS
    except ImportError:
        print("ChatTTS is not installed: pip install -r requirements-tts.txt", file=sys.stderr)
        return 1

    seeds = generate_seeds(args.count, args.digits)
    print(f"[voices] seeds: {seeds}")

    chat = ChatTTS.Chat()
    load_kwargs = {"compile": args.compile, "source": "huggingface"}
    if args.device != "auto":
        import torch

        load_kwargs["device"] = torch.device(args.device)
    print("[voices] loading ChatTTS weights (first run downloads ~2GB, takes minutes)...")
    if not chat.load(**load_kwargs):
        print("[voices] ChatTTS failed to load weights.", file=sys.stderr)
        return 1
    print("[voices] model ready.")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"text": SAMPLE_TEXT, "sample_rate": SAMPLE_RATE, "samples": []}

    for seed in seeds:
        print(f"[voices] synthesizing seed {seed}...")
        frames = synthesize_for_seed(chat, seed, literal=not args.expressive)
        wav_path = out_dir / sample_filename(seed, "wav")
        write_wav(wav_path, frames)
        seconds = check_audio_non_silent(wav_path)
        final = wav_path
        if args.format == "mp3":
            mp3_path = out_dir / sample_filename(seed, "mp3")
            if to_mp3(wav_path, mp3_path):
                final = mp3_path
            else:
                print(f"[voices] seed {seed}: keeping wav (no ffmpeg/mp3).")
        manifest["samples"].append({"seed": seed, "file": final.name, "seconds": round(seconds, 2)})
        print(f"[voices] seed {seed} -> {final.name} ({seconds:.1f}s)")

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[voices] done: {len(manifest['samples'])} files + {manifest_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
