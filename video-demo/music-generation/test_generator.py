"""DawDreamer smoke harness: render a 440 Hz sine via Faust, write test_render.wav.

Headless: no audio device needed, RenderEngine renders offline to a buffer.
Run from this directory with the fixture venv:
    ./.venv/bin/python test_generator.py
"""

# NOTE: within third-party imports, dawdreamer must stay first: it must be
# imported before any LLVM-based libraries (jax, numba, torchscript, ...)
# or LLVM init conflicts can segfault.
# Reference: https://github.com/DBraun/DawDreamer (Known Issues).
from pathlib import Path

import dawdreamer as daw
import numpy as np
from scipy.io import wavfile

SAMPLE_RATE = 44100
BLOCK_SIZE = 512
DURATION_SECONDS = 3.0
OUTPUT_NAME = "test_render.wav"

FAUST_DSP = """
declare name "MySine";
import("stdfaust.lib");
freq = hslider("freq", 440, 0, 20000, 0.1);
gain = hslider("vol[unit:dB]", -6, -120, 20, 0.1) : ba.db2linear;
process = freq : os.osc : _ * gain <: si.bus(2);
"""


def main() -> Path:
    engine = daw.RenderEngine(SAMPLE_RATE, BLOCK_SIZE)

    faust_processor = engine.make_faust_processor("my_sine")
    faust_processor.set_dsp_string(FAUST_DSP)

    engine.load_graph([(faust_processor, [])])

    faust_processor.set_parameter("/MySine/freq", 440.0)
    faust_processor.set_parameter("/MySine/vol", -6.0)

    engine.render(DURATION_SECONDS)
    audio = engine.get_audio()
    if audio is None or audio.size == 0:
        raise RuntimeError("RenderEngine produced an empty audio buffer")

    stereo = np.asarray(audio.T, dtype=np.float32)
    expected_frames = int(SAMPLE_RATE * DURATION_SECONDS)
    if stereo.shape[0] < expected_frames:
        raise RuntimeError(
            f"Rendered {stereo.shape[0]} frames, expected at least {expected_frames}"
        )

    out_path = Path(__file__).resolve().parent / OUTPUT_NAME
    wavfile.write(str(out_path), SAMPLE_RATE, stereo)
    peak = float(np.max(np.abs(stereo)))
    print(
        f"Rendered {stereo.shape[0]} frames "
        f"({stereo.shape[0] / SAMPLE_RATE:.2f}s) "
        f"shape={stereo.shape} peak={peak:.4f} -> {out_path}"
    )
    if peak <= 0.0:
        raise RuntimeError("Rendered audio is silent; expected a 440 Hz sine tone")
    return out_path


if __name__ == "__main__":
    main()
