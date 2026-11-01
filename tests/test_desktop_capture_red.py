"""RED-first contract for the headless desktop-capture sandbox.

Pins the brief's hard requirements without needing PipeWire/gamescope
running: file layout, clean-room C source properties (single locked
1920x1080@60 I420 format, MemFd/MemPtr negotiation, raw-stdin ingestion,
no JPEG/scale libraries), sandbox script piping, and isolated audio
routing. Pre-implementation every test fails with FileNotFoundError
(functional absence, not syntax).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "video-demo" / "desktop-capture"
DESKCAP = ROOT / "deskcap"
GAMESCOPE = ROOT / "gamescope"
PIPEWIRE = ROOT / "pipewire"

SRC = DESKCAP / "pwcam_desktop.c"
MAKEFILE = DESKCAP / "Makefile"
SANDBOX = GAMESCOPE / "launch_sandbox.sh"
SETUP = PIPEWIRE / "setup_audio_sink.sh"
TEARDOWN = PIPEWIRE / "teardown_audio_sink.sh"
AUDIO_README = PIPEWIRE / "README.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_deskcap_source_exists():
    assert SRC.is_file(), f"missing clean-room source: {SRC}"


def test_deskcap_makefile_exists():
    assert MAKEFILE.is_file(), f"missing build file: {MAKEFILE}"


def test_deskcap_free_of_jpeg_and_scale_deps():
    src = _read(SRC)
    for banned in (
        "turbojpeg",
        "tjDecompress",
        "swscale",
        "sws_scale",
        "libavutil",
        "AV_PIX_FMT",
        "SwsContext",
    ):
        assert banned not in src, f"banned dependency leaked in: {banned}"


def test_deskcap_frame_size_constant():
    src = _read(SRC)
    assert "3110400" in src, "must read exact 1920*1080*1.5 = 3110400 bytes"


def test_deskcap_locked_single_format():
    src = _read(SRC)
    assert "SPA_VIDEO_FORMAT_I420" in src
    assert "1920" in src and "1080" in src
    assert re.search(r"\b60\b", src), "must lock 60fps"
    for other in ("SPA_VIDEO_FORMAT_NV12", "SPA_VIDEO_FORMAT_YUY2"):
        assert other not in src, f"must lock I420 only, found {other}"


def test_deskcap_negotiates_memfd_memptr_buffers():
    src = _read(SRC)
    assert "SPA_PARAM_Buffers" in src
    assert "SPA_DATA_MemFd" in src
    assert "SPA_DATA_MemPtr" in src


def test_deskcap_reader_thread_and_process_memcpy():
    src = _read(SRC)
    assert "reader_thread" in src
    assert "on_process" in src
    assert "memcpy" in src
    assert "Video/Source" in src


def test_deskcap_compiles_and_links_clean():
    proc = subprocess.run(["make", "-C", str(DESKCAP)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"make failed:\n{proc.stdout}\n{proc.stderr}"
    binary = DESKCAP / "deskcap"
    assert binary.is_file()
    ldd = subprocess.run(["ldd", str(binary)], capture_output=True, text=True, timeout=30)
    assert ldd.returncode == 0
    for banned in ("turbojpeg", "swscale", "avutil"):
        assert banned not in ldd.stdout, f"binary links banned lib: {banned}"


def test_launch_sandbox_pipes_recorder_into_deskcap():
    sh = _read(SANDBOX)
    assert "gamescope" in sh
    assert "1920x1080" in sh or ("1920" in sh and "1080" in sh)
    assert "WAYLAND_DISPLAY" in sh
    assert "wf-recorder" in sh
    assert "rawvideo" in sh and "yuv420p" in sh
    assert "deskcap" in sh and "|" in sh, "wf-recorder stdout must pipe into deskcap"
    assert "trap" in sh, "must trap exit and kill children"


def test_audio_sink_isolated_setup_and_teardown():
    setup = _read(SETUP)
    assert "module-null-sink" in setup
    assert "IsolatedAppAudio" in setup
    assert "PULSE_SINK" in setup
    assert re.search(r"ffmpeg|pw-record", setup), "monitor-only record one-liner"
    assert "monitor" in setup.lower()
    teardown = _read(TEARDOWN)
    assert "IsolatedAppAudio" in teardown or "module-null-sink" in teardown
    assert re.search(r"unload|pactl", teardown)
    readme = _read(AUDIO_README)
    assert "PULSE_SINK=IsolatedAppAudio" in readme
    assert "IsolatedAppAudio" in readme
