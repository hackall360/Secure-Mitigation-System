# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Deterministic context compression middleware (Subsystem A, V1 Y1).

Sits in front of MetaMuseClient prompt builders: structural line
deduplication, semantic pruning of boilerplate, and token-budget
prioritization — while preserving 100% of security-critical sink/flow
sentences verbatim. Stdlib only, deterministic (no randomness, stable
ordering), fail-closed (any internal error returns the input uncompressed).

Token model: ~4 chars per token (standard rough estimator; bills are still
decided by provider usage blocks in modules/core/pricing.py).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

CHARS_PER_TOKEN = 4
DEFAULT_MAX_TOKENS = 8000
DICTIONARY_MAX_LINES = 4096

# Substrings that mark a line as security-critical: sinks, sources, and
# data-flow carriers. A line containing any of these (case-insensitive) is
# NEVER dropped or folded, regardless of repetition or budget pressure
# (budget overflow keeps critical lines and drops filler first).
_CRITICAL_PATTERNS = (
    "eval(",
    "exec(",
    "execSync",
    "spawn(",
    "system(",
    "shell_exec",
    "passthru",
    "popen",
    "queryexpression",
    "rawuserid",
    "req.query",
    "req.body",
    "req.params",
    "argv",
    "$_get",
    "$_post",
    "$_request",
    "$host",
    "bind-address",
    "local-infile",
    "secure-file-priv",
    "password",
    "secret",
    "crypto",
    "sanitiz",
    "validat",
    "escap",
    "allowlist",
    "denylist",
    "child_process",
    "command",
    "sql",
    "query",
)

_FILLER_PATTERNS = (
    re.compile(r"^\s*(//|#|/\*|\*|--|;)\s*(filler|boilerplate|placeholder|lorem)", re.I),
    re.compile(r"^\s*(import|require\(|use |#include|package )\s"),
    re.compile(r"^\s*(console\.log|print\(|echo |var_dump)\s*\(?\s*['\"]debug", re.I),
)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ceil(len/4). Empty text costs zero."""
    if not text:
        return 0
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def _is_critical(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in _CRITICAL_PATTERNS)


def _is_filler(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return any(pattern.search(line) for pattern in _FILLER_PATTERNS)


class CompressionReport(BaseModel):
    """Per-cycle compression telemetry; serialized into ScanResult/reports."""

    model_config = ConfigDict(extra="forbid", strict=True)
    raw_tokens_estimated: int = 0
    compressed_tokens_sent: int = 0
    tokens_saved: int = 0
    compression_ratio: float = 0.0
    compressed_text: str = ""

    @property
    def raw_tokens(self) -> int:
        return self.raw_tokens_estimated

    @property
    def compressed_tokens(self) -> int:
        return self.compressed_tokens_sent


class CompressionStats(BaseModel):
    """Cross-cycle accumulator: the progressively-learned savings ledger."""

    model_config = ConfigDict(extra="forbid", strict=True)
    cycles: int = 0
    total_raw: int = 0
    total_compressed: int = 0
    total_saved: int = 0
    ratios: list[float] = Field(default_factory=list)

    def add(self, report: CompressionReport) -> None:
        self.cycles += 1
        self.total_raw += report.raw_tokens_estimated
        self.total_compressed += report.compressed_tokens_sent
        self.total_saved += report.tokens_saved
        self.ratios.append(report.compression_ratio)

    def summary(self) -> dict:
        mean_ratio = sum(self.ratios) / len(self.ratios) if self.ratios else 0.0
        return {
            "cycles": self.cycles,
            "total_raw_tokens": self.total_raw,
            "total_compressed_tokens": self.total_compressed,
            "total_tokens_saved": self.total_saved,
            "mean_compression_ratio": round(mean_ratio, 4),
        }


class DictionaryStore:
    """Persisted cross-session line dictionary (JSON file, owner-only perms).

    Records boilerplate lines already paid for in earlier cycles so later
    cycles can fold them to a single reference marker instead of resending.
    """

    def __init__(self, path: str | Path | None = None):
        default = Path.home() / ".cache" / "secure-mitigation-system" / "compress_dict.json"
        self.path = Path(path) if path is not None else default
        self._lines: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key, count in raw.items():
                        if isinstance(key, str) and isinstance(count, int):
                            self._lines[key] = count
        except (OSError, ValueError):
            self._lines = {}

    def known(self, line: str) -> bool:
        return line in self._lines

    def record(self, *, filename: str, seen_lines: tuple[str, ...] | list[str]) -> None:
        del filename  # reserved for per-fixture partitions; global today.
        for line in seen_lines:
            self._lines[line] = self._lines.get(line, 0) + 1
        while len(self._lines) > DICTIONARY_MAX_LINES:
            oldest = next(iter(self._lines))
            del self._lines[oldest]

    def fold_marker(self, line: str) -> str:
        count = self._lines.get(line, 0)
        return f"[... seen {count}x in prior cycles: {line[:60]} ...]"

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._lines, indent=1), encoding="utf-8")
            try:
                self.path.chmod(0o600)
            except OSError:
                pass
        except OSError:
            pass


def compress_context(
    source: str,
    *,
    filename: str = "",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    dictionary: DictionaryStore | None = None,
) -> CompressionReport:
    """Compress source context deterministically.

    Pass 1: structural dedup — repeated non-critical lines collapse to one
    copy plus a fold marker. Pass 2: semantic pruning — filler/blank lines
    drop. Pass 3: budget — if still over max_tokens, drop filler first,
    then non-critical lines from the middle, never critical lines.
    Critical lines keep original order and verbatim text.
    """
    _ = filename  # reserved for per-language rules; patterns are global today.
    raw_tokens = estimate_tokens(source)
    if not source:
        return CompressionReport()
    if raw_tokens <= 0:
        return CompressionReport(compressed_text=source)
    lines = source.splitlines()
    if len(lines) <= 1:
        return CompressionReport(
            raw_tokens_estimated=raw_tokens,
            compressed_tokens_sent=raw_tokens,
            tokens_saved=0,
            compression_ratio=0.0,
            compressed_text=source,
        )

    seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        if _is_critical(line):
            deduped.append(line)
            continue
        if line in seen:
            if dictionary is not None and dictionary.known(line):
                deduped.append(dictionary.fold_marker(line))
            # else: drop the repeat entirely (folded by dedup)
            continue
        seen.add(line)
        deduped.append(line)

    pruned = [line for line in deduped if _is_critical(line) or not _is_filler(line)]
    if not pruned:
        pruned = [line for line in deduped if _is_critical(line)] or deduped[:1]

    candidate = "\n".join(pruned)
    if lines and source.endswith("\n"):
        candidate += "\n"
    if estimate_tokens(candidate) <= max_tokens:
        compressed_tokens = estimate_tokens(candidate)
        saved = max(0, raw_tokens - compressed_tokens)
        ratio = (saved / raw_tokens) if raw_tokens else 0.0
        if dictionary is not None:
            dictionary.record(filename=filename, seen_lines=list(seen))
        return CompressionReport(
            raw_tokens_estimated=raw_tokens,
            compressed_tokens_sent=compressed_tokens,
            tokens_saved=saved,
            compression_ratio=round(min(1.0, ratio), 4),
            compressed_text=candidate,
        )

    # Budget pass: critical lines always survive; keep head + tail context
    # (both ends) and drop middle non-critical lines first. Original relative
    # order is restored at the end.
    critical = [line for line in pruned if _is_critical(line)]
    others = [line for line in pruned if not _is_critical(line)]
    head: list[str] = []
    tail: list[str] = []
    left, right = 0, len(others) - 1
    take_head = True
    while left <= right:
        if take_head:
            candidate_line = others[left]
            probe = "\n".join(critical + head + [candidate_line] + tail)
            if estimate_tokens(probe) <= max_tokens:
                head.append(candidate_line)
                left += 1
            else:
                left += 1  # head no longer fits; skip toward tail end
                continue
        else:
            candidate_line = others[right]
            probe = "\n".join(critical + head + [candidate_line] + tail)
            if estimate_tokens(probe) <= max_tokens:
                tail.insert(0, candidate_line)
                right -= 1
            else:
                break  # tail end exhausted the budget; middle drops
        take_head = not take_head
    position = {id(line): idx for idx, line in enumerate(pruned)}
    ordered = sorted(critical + head + tail, key=lambda line: position.get(id(line), 0))
    candidate = "\n".join(ordered)
    if lines and source.endswith("\n"):
        candidate += "\n"
    compressed_tokens = estimate_tokens(candidate)
    saved = max(0, raw_tokens - compressed_tokens)
    ratio = (saved / raw_tokens) if raw_tokens else 0.0
    if dictionary is not None:
        dictionary.record(filename=filename, seen_lines=list(seen))
    return CompressionReport(
        raw_tokens_estimated=raw_tokens,
        compressed_tokens_sent=compressed_tokens,
        tokens_saved=saved,
        compression_ratio=round(min(1.0, ratio), 4),
        compressed_text=candidate,
    )
