# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Validated intake for compiled binaries. Never executes on the host.

Magic-byte allowlist (ELF/Mach-O/PE), 8 MiB cap, bare-filename rule, and a
mandatory behavior contract. The binary is staged into stopped containers
and analyzed/executed ONLY inside the air-gapped sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass

BINARY_MAX_BYTES = 8 * 1024 * 1024
BINARY_CONTRACT_MAX_CHARS = 8_192

_ELF_MAGIC = b"\x7fELF"
_PE_MAGIC = b"MZ"
_MACHO_MAGICS = (
    b"\xcf\xfa\xed\xfe",  # MH_MAGIC_64
    b"\xce\xfa\xed\xfe",  # MH_MAGIC
    b"\xca\xfe\xba\xbe",  # FAT_MAGIC
)


class BinaryRejected(ValueError):
    """Intake validation refused the binary."""


@dataclass(frozen=True)
class BinarySpec:
    """Validated binary submission: bytes stay in memory until staging."""

    filename: str
    binary_format: str
    size_bytes: int
    contract: str
    blob: bytes


def detect_binary_format(blob: bytes) -> str | None:
    """Magic-byte format detection. None means not an allowed binary."""
    if blob.startswith(_ELF_MAGIC):
        return "elf"
    if blob.startswith(_PE_MAGIC):
        return "pe"
    if any(blob.startswith(magic) for magic in _MACHO_MAGICS):
        return "macho"
    return None


def validate_binary_blob(blob: bytes, *, filename: str, contract: str) -> BinarySpec:
    """Validate a binary submission; raises BinaryRejected with a safe message."""
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        raise BinaryRejected("Filename must be a bare filename, no paths.")
    if len(filename) > 128:
        raise BinaryRejected("Filename exceeds 128 characters.")
    if not contract or not contract.strip():
        raise BinaryRejected("A behavior contract is required (what must hold).")
    if len(contract) > BINARY_CONTRACT_MAX_CHARS:
        raise BinaryRejected("Contract exceeds the 8 KiB budget.")
    if not blob:
        raise BinaryRejected("Binary is empty.")
    if len(blob) > BINARY_MAX_BYTES:
        raise BinaryRejected("Binary exceeds the 8 MiB intake budget.")
    detected = detect_binary_format(blob)
    if detected is None:
        raise BinaryRejected(
            "Not a recognized compiled binary (need ELF, Mach-O, or PE magic bytes)."
        )
    return BinarySpec(
        filename=filename,
        binary_format=detected,
        size_bytes=len(blob),
        contract=contract,
        blob=blob,
    )


def validate_binary_file(path: str, *, contract: str) -> BinarySpec:
    """Read a binary from disk (host read only, never executed) and validate it."""
    from pathlib import Path

    candidate = Path(path)
    try:
        blob = candidate.read_bytes()
    except OSError as exc:
        raise BinaryRejected(f"Cannot read binary file ({type(exc).__name__}).") from exc
    return validate_binary_blob(blob, filename=candidate.name, contract=contract)
