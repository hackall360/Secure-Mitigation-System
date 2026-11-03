"""F-211: filename hygiene, pre-read size checks, base64 budget helper."""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import pytest

from library.services import binary_intake as bi

ELF = b"\x7fELF" + b"\x00" * 16


@pytest.mark.parametrize(
    "name",
    ["a\x00b", "a\nb", "a\tb", "x\x7f", "   ", "\t", " lead", "trail ", "\x1b[31m"],
)
def test_bad_filenames_rejected_without_echo(name: str) -> None:
    with pytest.raises(bi.BinaryRejected) as exc:
        bi.validate_binary_blob(ELF, filename=name, contract="must hold")
    if name.strip():
        assert name not in str(exc.value)


def test_good_filename_still_accepted() -> None:
    spec = bi.validate_binary_blob(ELF, filename="my tool.bin", contract="c")
    assert spec.filename == "my tool.bin"


def test_directory_rejected(tmp_path: Path) -> None:
    with pytest.raises(bi.BinaryRejected):
        bi.validate_binary_file(str(tmp_path), contract="c")


@pytest.mark.skipif(os.name != "posix", reason="FIFO needs posix")
def test_fifo_rejected_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "pipe.bin"
    os.mkfifo(fifo)
    with pytest.raises(bi.BinaryRejected):
        bi.validate_binary_file(str(fifo), contract="c")


def test_sparse_oversize_rejected_before_read(tmp_path: Path, monkeypatch) -> None:
    big = tmp_path / "big.bin"
    with open(big, "wb") as f:
        f.truncate(bi.BINARY_MAX_BYTES + 1)

    def boom(*_a, **_k):
        raise AssertionError("file was read before size check")

    monkeypatch.setattr(Path, "read_bytes", boom)
    monkeypatch.setattr(Path, "open", boom)
    monkeypatch.setattr(builtins, "open", boom)
    with pytest.raises(bi.BinaryRejected, match="8 MiB"):
        bi.validate_binary_file(str(big), contract="c")


def test_regular_file_ok(tmp_path: Path) -> None:
    p = tmp_path / "ok.bin"
    p.write_bytes(ELF)
    assert bi.validate_binary_file(str(p), contract="c").size_bytes == len(ELF)


def test_b64_budget() -> None:
    assert bi.max_b64_chars_for(8 * 1024 * 1024) == 11184812
    assert bi.max_b64_chars_for(1) == 4
    assert bi.max_b64_chars_for(3) == 4
    assert bi.max_b64_chars_for(4) == 8
    assert bi.BINARY_MAX_B64_CHARS == bi.max_b64_chars_for(bi.BINARY_MAX_BYTES)
