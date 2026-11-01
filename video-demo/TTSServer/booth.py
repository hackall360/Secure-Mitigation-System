# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Voice listening booth (video-demo pass/fail TUI).

Plain-terminal interactive loop — no curses, no new deps, works over any
terminal. Reuses `try_voice` for rendering/pinning/state; this file is only
the booth flow: batches of 10, play/relisten/pass/fail, volume (default 50%),
stop-or-deal-more at batch end.

Commands (shown in the booth):
  p / play        play current voice (renders on first play, then replays)
  r / relisten    replay current voice
  pass            pin voice (.pt tensor + keep audio), advance
  fail            ban seed, advance to next candidate
  v 0-100         set volume (default 50; playback only, files stay full-scale)
  s / skip        next voice without judging
  more            deal another batch of 10 (at batch end, or anytime)
  q / quit        quit now (state saved)

Batch end: booth asks `another 10? [y/n]` — y deals more, n stops.
"""

import argparse
import random
import subprocess
import sys
from pathlib import Path

BATCH_SIZE = 10
DEFAULT_VOLUME = 0.5
DEFAULT_VARY_TEMPS = (0.1, 0.3, 0.5, 0.7, 0.9)


def variation_schedule(seeds, temps=DEFAULT_VARY_TEMPS):
    """5 temperature variations per pinned seed, seeds in order (20 total)."""
    return [(int(s), float(t)) for s in seeds for t in temps]


class BoothState:
    def __init__(self, volume=DEFAULT_VOLUME):
        self.volume = float(volume)
        self.batch = []
        self.index = 0
        self.banned = set()
        self.passed = []
        self.played_hashes = {}
        self.variation_picks = []
        self.variation_banned = set()

    def set_volume(self, value):
        self.volume = max(0.0, min(1.0, float(value)))

    def deal_batch(self, n, rng=None):
        rng = rng or random.Random()
        pool = [s for s in range(1, 10000) if s not in self.banned]
        self.batch = rng.sample(pool, min(n, len(pool)))
        self.index = 0
        return self.batch

    def current(self):
        if 0 <= self.index < len(self.batch):
            return self.batch[self.index]
        return None

    def batch_done(self):
        return self.index >= len(self.batch)

    def on_fail(self, seed):
        self.banned.add(int(seed))
        self.index += 1

    def on_pass(self, seed, tensor_hash):
        self.passed.append({"seed": int(seed), "tensor": tensor_hash})
        self.index += 1

    def variation_pass(self, seed, temperature, tensor_hash):
        self.variation_picks.append(
            {"seed": int(seed), "temperature": float(temperature), "tensor": tensor_hash}
        )

    def variation_fail(self, seed, temperature):
        self.variation_banned.add((int(seed), float(temperature)))


def play_wav(path, volume):
    """Play a wav at `volume` (0-1). Returns True on audible playback."""
    path = str(path)
    volume = max(0.0, min(1.0, float(volume)))
    # Path 1: sounddevice (TTS venv) with software volume scaling.
    try:
        import array
        import wave

        import sounddevice as sd

        with wave.open(path, "rb") as wav:
            rate = wav.getframerate()
            raw = wav.readframes(wav.getnframes())
        pcm = array.array("h", raw)
        scaled = array.array("h", (int(s * volume) for s in pcm))
        sd.play(scaled, samplerate=rate)
        sd.wait()
        return True
    except Exception:
        pass
    # Path 2: ffmpeg volume filter -> aplay (ALSA, this box).
    scaled_tmp = str(Path(path).with_suffix(".vol.wav"))
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                path,
                "-filter:a",
                f"volume={volume}",
                scaled_tmp,
            ],
            check=True,
            timeout=60,
        )
        subprocess.run(["aplay", "-q", scaled_tmp], check=True, timeout=120)
        return True
    except Exception:
        return False
    finally:
        try:
            Path(scaled_tmp).unlink()
        except OSError:
            pass


def run_booth(
    commands,
    play_fn,
    render_fn,
    rng=None,
    batch_size=BATCH_SIZE,
    volume=DEFAULT_VOLUME,
    fail_silent=True,
):
    """Scripted booth session: commands in, transcript out (no I/O, no model).

    play_fn(seed, volume) plays; render_fn(seed) -> tensor hash (renders on
    first play of a seed). A seed that fails to render (silent/empty) is
    auto-banned and skipped — the session never dies on one bad seed.
    Returns transcript dict.
    """
    rng = rng or random.Random()
    state = BoothState(volume=volume)
    state.deal_batch(batch_size, rng)
    transcript = {
        "played": [],
        "passed": [],
        "banned": [],
        "volumes": [],
        "batches": 1,
        "quit": False,
    }
    rendered = {}

    def safe_render(seed):
        if seed in rendered:
            return rendered[seed]
        try:
            rendered[seed] = render_fn(seed)
            state.played_hashes[seed] = rendered[seed]
            return rendered[seed]
        except Exception as exc:
            if fail_silent:
                state.on_fail(seed)
                transcript["banned"].append(f"{seed} (silent: {exc})")
                return None
            raise

    for raw in commands:
        cmd = raw.strip().lower()
        if cmd in ("q", "quit"):
            transcript["quit"] = True
            break
        if cmd.startswith("v"):
            try:
                pct = float(cmd[1:].strip())
                state.set_volume(pct / 100.0)
                transcript["volumes"].append(state.volume)
            except ValueError:
                pass
            continue
        seed = state.current()
        if cmd in ("more", "m"):
            state.deal_batch(batch_size, rng)
            transcript["batches"] += 1
            continue
        if cmd in ("s", "skip"):
            state.index += 1
        elif cmd in ("p", "play", "r", "relisten"):
            if seed is None:
                continue
            if safe_render(seed) is None:
                continue
            play_fn(seed, state.volume)
            transcript["played"].append(seed)
        elif cmd in ("pass", "y"):
            if seed is None:
                continue
            if safe_render(seed) is None:
                continue
            state.on_pass(seed, rendered[seed])
            transcript["passed"].append(seed)
        elif cmd in ("fail", "f", "n"):
            if seed is None:
                continue
            state.on_fail(seed)
            transcript["banned"].append(seed)
        if state.batch_done():
            transcript["batch_end"] = True
    transcript["state"] = state
    return transcript


def run_variations(seeds, temps, commands, play_fn, render_fn, volume=DEFAULT_VOLUME):
    """Scripted variation pass: (seed, temp) pairs in schedule order.

    play_fn(seed, volume, temperature); render_fn(seed, temperature) -> hash.
    Silent renders auto-ban the pair and advance. Returns transcript.
    """
    state = BoothState(volume=volume)
    schedule = variation_schedule(seeds, temps)
    transcript = {
        "played": [],
        "variation_picks": [],
        "variation_banned": [],
        "quit": False,
        "schedule": schedule,
    }
    rendered = {}
    index = 0

    def safe_render(seed, temperature):
        key = (seed, temperature)
        if key in rendered:
            return rendered[key]
        try:
            rendered[key] = render_fn(seed, temperature)
            return rendered[key]
        except Exception as exc:
            state.variation_fail(seed, temperature)
            transcript["variation_banned"].append(f"{seed}@{temperature} (silent: {exc})")
            return None

    for raw in commands:
        cmd = raw.strip().lower()
        if cmd in ("q", "quit"):
            transcript["quit"] = True
            break
        if index >= len(schedule):
            break
        seed, temperature = schedule[index]
        if cmd in ("p", "play", "r", "relisten"):
            digest = safe_render(seed, temperature)
            if digest is None:
                index += 1
                continue
            play_fn(seed, volume, temperature)
            transcript["played"].append((seed, temperature))
        elif cmd in ("pass", "y"):
            digest = safe_render(seed, temperature)
            if digest is None:
                index += 1
                continue
            state.variation_pass(seed, temperature, digest)
            transcript["variation_picks"].append((seed, temperature))
            index += 1
        elif cmd in ("fail", "f", "n", "s", "skip"):
            state.variation_fail(seed, temperature)
            transcript["variation_banned"].append((seed, temperature))
            index += 1
    transcript["state"] = state
    return transcript


def run_vary_mode(args, chat, tv, text, scratch, keep, state, temperature):
    """Variation pass: 5 temperatures per pinned seed, pass/fail each."""
    import subprocess

    seeds = [int(s) for s in args.vary.split(",") if s.strip()]
    temps = [float(t) for t in args.vary_temps.split(",") if t.strip()]
    schedule = variation_schedule(seeds, temps)
    vary_saved = tv.load_state(args.vary_state)
    picks = list(vary_saved.get("variation_picks", vary_saved.get("passed", [])))
    index = 0
    total = len(schedule)
    print(f"Variation pass: {len(seeds)} seeds x {len(temps)} temps = {total} auditions.")
    print("Commands: p play, r relisten, pass (keep this temp), fail, v 0-100, q quit.")
    while index < len(schedule):
        seed, temp = schedule[index]
        print(
            f"\n[{index + 1}/{total}] seed {seed} @ temp {temp} "
            f"(kept={len(picks)} vol={int(state.volume * 100)}%)"
        )
        try:
            cmd = input("vary> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            tv.save_state(args.vary_state, {"variation_picks": picks})
            print("\nQuit. Variations saved.")
            return 0
        if cmd.startswith("v"):
            try:
                state.set_volume(float(cmd[1:].strip()) / 100.0)
                print(f"volume {int(state.volume * 100)}%")
            except ValueError:
                print("usage: v 0-100")
            continue
        if cmd in ("q", "quit"):
            tv.save_state(args.vary_state, {"variation_picks": picks})
            print("Quit. Variations saved.")
            return 0
        wav = scratch / f"vary_{seed:04d}_{str(temp).replace('.', 'p')}.wav"
        if cmd in ("p", "play", "r", "relisten", "pass", "y"):
            try:
                digest = tv.render_seed(
                    chat,
                    seed,
                    text,
                    wav,
                    literal=not args.expressive,
                    temperature=temp,
                    word_breaks=args.word_breaks,
                )
            except Exception as exc:
                try:
                    wav.unlink(missing_ok=True)
                except OSError:
                    pass
                print(f"seed {seed} @ {temp} failed ({exc}); auto-banned, moving on.")
                index += 1
                continue
            if cmd in ("p", "play", "r", "relisten"):
                if play_wav(wav, state.volume):
                    print(f"(played seed {seed} @ {temp} at {int(state.volume * 100)}%)")
                else:
                    print(f"(no audio device; file kept: {wav})")
                continue
            pt = keep / f"voice_{seed:04d}_t{str(temp).replace('.', 'p')}.pt"
            tv.pin_tensor(chat, seed, pt)
            mp3 = keep / f"voice_{seed:04d}_t{str(temp).replace('.', 'p')}.mp3"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-i", str(wav), str(mp3)],
                    check=True,
                    timeout=120,
                )
                kept = mp3.name
            except Exception:
                kept = wav.name
            picks.append({"seed": seed, "temperature": temp, "tensor": digest, "file": kept})
            tv.save_state(args.vary_state, {"variation_picks": picks})
            print(f"KEPT seed {seed} @ temp {temp}: tensor -> {pt.name}, audio -> {kept}")
            index += 1
        elif cmd in ("fail", "f", "n", "s", "skip"):
            print(f"failed seed {seed} @ {temp}. next.")
            index += 1
        else:
            print("p play, r relisten, pass, fail, v 0-100, q quit")
    tv.save_state(args.vary_state, {"variation_picks": picks})
    print(f"\nVariation pass done. Kept {len(picks)} of {total}.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Voice listening booth")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    parser.add_argument("--state", default="booth.json")
    parser.add_argument(
        "--keep-dir", default="passed", help="where passed voices (.pt + mp3) are saved"
    )
    parser.add_argument(
        "--scratch-dir", default=".booth-scratch", help="temp iteration audio (never committed)"
    )
    parser.add_argument("--text", default=None, help="phrase (default: voice-test line)")
    parser.add_argument("--expressive", action="store_true")
    parser.add_argument("--volume", type=float, default=50.0)
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="sampling temperature (default: README 0.3 lively)",
    )
    parser.add_argument(
        "--word-breaks",
        action="store_true",
        help="README word-level control: prefix sentences with [uv_break]",
    )
    parser.add_argument(
        "--vary",
        default="",
        help="variation pass: comma seeds, e.g. --vary 1869,6420,812,7358",
    )
    parser.add_argument(
        "--vary-temps",
        default=",".join(str(t) for t in DEFAULT_VARY_TEMPS),
        help="comma temperatures for --vary (default 0.1,0.3,0.5,0.7,0.9)",
    )
    parser.add_argument(
        "--vary-state",
        default="variations.json",
        help="where variation picks/bans are recorded",
    )
    args = parser.parse_args(argv)

    try:
        import ChatTTS
    except ImportError:
        print("ChatTTS is not installed: pip install -r requirements-tts.txt", file=sys.stderr)
        return 1
    import try_voice as tv

    scratch = Path(args.scratch_dir)
    scratch.mkdir(parents=True, exist_ok=True)
    keep = Path(args.keep_dir)
    keep.mkdir(parents=True, exist_ok=True)

    state = BoothState(volume=args.volume / 100.0)
    saved = tv.load_state(args.state)
    state.banned = set(saved.get("banned", []))
    state.passed = list(saved.get("passed", []))

    print("Loading ChatTTS weights (cached after first run)...")
    chat = ChatTTS.Chat()
    with tv.quiet_chattts():
        loaded = chat.load(compile=False, source="huggingface")
    if not loaded:
        print("weights failed to load.", file=sys.stderr)
        return 1
    print("Model ready. Commands: p play, r relisten, pass, fail, v 0-100,")
    print("  s skip, more (another batch), q quit. Volume default 50%.")

    rng = random.Random()
    text = args.text or tv.TRY_TEXT
    temperature = args.temperature if args.temperature is not None else tv.DEFAULT_TEMPERATURE

    if args.vary.strip():
        return run_vary_mode(args, chat, tv, text, scratch, keep, state, temperature)

    def render(seed):
        wav = scratch / f"booth_{seed:04d}.wav"
        if wav.is_file() and seed in state.played_hashes:
            return state.played_hashes[seed]
        try:
            digest = tv.render_seed(
                chat,
                seed,
                text,
                wav,
                literal=not args.expressive,
                temperature=temperature,
                word_breaks=args.word_breaks,
            )
            state.played_hashes[seed] = digest
            return digest
        except Exception as exc:
            try:
                wav.unlink(missing_ok=True)
            except OSError:
                pass
            state.on_fail(seed)
            tv.record_fail(args.state, seed)
            print(f"seed {seed} failed to render ({exc}); auto-banned, moving on.")
            return None

    def play(seed, volume):
        wav = scratch / f"booth_{seed:04d}.wav"
        if play_wav(wav, volume):
            print(f"(played seed {seed} at {int(volume * 100)}%)")
        else:
            print(f"(no audio device; file kept: {wav})")

    def persist():
        tv.save_state(args.state, {"banned": sorted(state.banned), "passed": state.passed})

    state.deal_batch(args.batch, rng)
    while True:
        if state.batch_done():
            persist()
            print(f"\nBatch done. passed={len(state.passed)} banned={len(state.banned)}.")
            answer = input("Another 10? [y/n] ").strip().lower()
            if answer.startswith("y"):
                state.deal_batch(args.batch, rng)
            else:
                print("Stopping. State saved.")
                return 0
        seed = state.current()
        print(
            f"\n[{state.index + 1}/{len(state.batch)}] seed {seed} "
            f"(passed={len(state.passed)} banned={len(state.banned)} "
            f"vol={int(state.volume * 100)}%)"
        )
        try:
            cmd = input("booth> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            persist()
            print("\nQuit. State saved.")
            return 0
        if cmd.startswith("v"):
            try:
                state.set_volume(float(cmd[1:].strip()) / 100.0)
                print(f"volume {int(state.volume * 100)}%")
            except ValueError:
                print("usage: v 0-100")
        elif cmd in ("p", "play", "r", "relisten"):
            if render(seed) is None:
                continue
            play(seed, state.volume)
        elif cmd in ("pass", "y"):
            digest = render(seed)
            if digest is None:
                continue
            pt = keep / f"voice_{seed:04d}.pt"
            tv.pin_tensor(chat, seed, pt)
            mp3 = keep / f"voice_{seed:04d}.mp3"
            wav = scratch / f"booth_{seed:04d}.wav"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-i", str(wav), str(mp3)],
                    check=True,
                    timeout=120,
                )
                kept = mp3.name
            except Exception:
                kept = wav.name
            state.on_pass(seed, digest)
            tv.record_pass(args.state, seed, digest, kept)
            state.passed = tv.load_state(args.state)["passed"]
            print(f"PASSED seed {seed}: tensor -> {pt.name}, audio -> {kept}")
        elif cmd in ("fail", "f", "n"):
            state.on_fail(seed)
            tv.record_fail(args.state, seed)
            print(f"failed seed {seed} (banned). next: {state.current()}")
        elif cmd in ("s", "skip"):
            state.index += 1
        elif cmd in ("more", "m"):
            state.deal_batch(args.batch, rng)
        elif cmd in ("q", "quit"):
            persist()
            print("Quit. State saved.")
            return 0
        else:
            print("p play, r relisten, pass, fail, v 0-100, s skip, more, q quit")


if __name__ == "__main__":
    raise SystemExit(main())
