# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Validated git-repo intake feeding the snapshot-based project pipeline.

Phase-1 contract (Wave 4): validate the remote (HTTPS-only, no ``git://``/
``ssh:``/``scp``-style URLs) plus a 40-hex pinned commit, then stage through
Docker staging-container semantics (``network_mode="none"``, never started,
no host mounts, no host paths). The clone itself is a later wave; this wave
records the staging plan on a manifest snapshot so the pipeline shape is
``snapshot_project``-compatible. LAW 4: no network clones in tests, no
exploit material, intake never touches host paths.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import urlparse

_INGEST_DIGEST_DOMAIN = b"purplebox-repo-intake-manifest-v1\0"
_COMMIT_HEX_CHARS = frozenset("0123456789abcdefABCDEF")

# LAW 4/10I: detection is pure string matching over file names and file
# contents. It never executes, never opens host paths, never touches the
# network. Adversarial names (``requirements.txt; rm -rf /``) only match on
# exact equality, so shell metacharacters can never trigger a runtime.
_MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.\-]*)\s*:(?![=:])", re.MULTILINE)
_MAKEFILE_NAMES = frozenset({"Makefile", "makefile", "GNUmakefile"})
_PYTHON_ENTRY_CANDIDATES = ("main.py", "app.py", "src/main.py", "src/app.py")
_PHP_ENTRY_CANDIDATES = ("public/index.php", "index.php", "src/index.php")

# Deterministic precedence when several manifests are present: the most
# specific ecosystem manifest wins; a generic Makefile loses to all of them.
_DETECT_PRECEDENCE = ("package.json", "composer.json", "python", "makefile")

_ACTIONABLE_SUFFIX = (
    "pass an explicit runtime_command argv "
    "(e.g. ['python3', 'main.py']) to intake_repo_to_snapshot"
)


@dataclass(frozen=True)
class RepoIntakeSpec:
    """Validated repo-intake request: HTTPS remote + pinned 40-hex commit.

    Rejects non-HTTPS schemes (``git://``, ``ssh://``, scp-style
    ``host:path``) and blank/short/non-hex commit hashes. No ``host_path``
    attribute exists by design: intake never touches host paths.
    """

    url: str
    commit_hash: str

    def __post_init__(self) -> None:
        parsed = urlparse(self.url) if isinstance(self.url, str) else None
        host = (parsed.hostname or "") if parsed is not None else ""
        if (
            parsed is None
            or parsed.scheme != "https"
            or not host
            or any(part in ("", ".", "..") for part in host.split("."))
            or " " in self.url
        ):
            raise ValueError("repo URL must be an https:// remote")
        commit = self.commit_hash
        if (
            not isinstance(commit, str)
            or len(commit) != 40
            or any(char not in _COMMIT_HEX_CHARS for char in commit)
        ):
            raise ValueError("commit_hash must be a 40-hex pinned commit")


@dataclass(frozen=True)
class RepoIntakeSnapshot:
    """Staging manifest for a validated repo intake (snapshot-compatible)."""

    files: MappingProxyType
    url: str
    commit_hash: str
    runtime_command: tuple
    digest: str


def _manifest_digest(spec: RepoIntakeSpec, runtime_command: tuple) -> str:
    digest = hashlib.sha256()
    digest.update(_INGEST_DIGEST_DOMAIN)
    digest.update(spec.url.encode("utf-8"))
    digest.update(b"\0")
    digest.update(spec.commit_hash.encode("utf-8"))
    digest.update(b"\0")
    digest.update(json.dumps(list(runtime_command)).encode("utf-8"))
    return digest.hexdigest()


def _normalise_file_entries(source) -> tuple[tuple[str, str | None], ...]:
    """Normalise the accepted ``detect_runtime`` inputs to (name, content)."""
    if source is None:
        return ()
    files_attr = getattr(source, "files", None)
    if isinstance(files_attr, dict):
        items = list(files_attr.items())
    elif files_attr is not None and not isinstance(files_attr, str):
        try:
            items = list(files_attr.items())  # type: ignore[union-attr]
        except (AttributeError, TypeError):
            items = None
        if items is None:
            return ()
    elif isinstance(source, dict):
        items = list(source.items())
    elif isinstance(source, (list, tuple)):
        items = []
        for entry in source:
            if isinstance(entry, str):
                items.append((entry, None))
            elif isinstance(entry, dict) and len(entry) == 1:
                name, content = next(iter(entry.items()))
                items.append((name, content))
            elif (
                isinstance(entry, (list, tuple))
                and len(entry) == 2
                and isinstance(entry[0], str)
            ):
                items.append((entry[0], entry[1]))
            else:
                raise ValueError(
                    "file entries must be names, {name: content} dicts, "
                    "or (name, content) pairs"
                )
    else:
        raise ValueError(
            "source must be a file-name list, a name->content mapping, "
            "or a snapshot with a .files mapping"
        )
    normalised: list[tuple[str, str | None]] = []
    for name, content in items:
        if not isinstance(name, str) or not name or not name.strip():
            raise ValueError("file names must be non-empty strings")
        if content is not None and not isinstance(content, (str, bytes)):
            raise ValueError("file contents must be str, bytes, or omitted")
        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                content = None
        normalised.append((_safe_relpath(name), content))
    return tuple(normalised)


def _safe_relpath(name: str) -> str:
    cleaned = name.strip().replace("\\", "/").lstrip("/")
    parts = [part for part in cleaned.split("/") if part not in ("", ".", "..")]
    return "/".join(parts)


def _basename(relpath: str) -> str:
    return relpath.rsplit("/", 1)[-1]


def _package_json_command(content: str | None) -> list[str]:
    if content:
        try:
            manifest = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            manifest = None
        if isinstance(manifest, dict):
            scripts = manifest.get("scripts")
            if isinstance(scripts, dict) and scripts.get("start"):
                return ["npm", "start"]
            main = manifest.get("main")
            if isinstance(main, str) and main.strip():
                return ["node", main.strip()]
    return ["npm", "start"]


def _python_command(names: set[str]) -> list[str]:
    for candidate in _PYTHON_ENTRY_CANDIDATES:
        if candidate in names:
            return ["python3", candidate]
    return ["python3", "main.py"]


def _php_command(names: set[str]) -> list[str]:
    for candidate in _PHP_ENTRY_CANDIDATES:
        if candidate in names:
            return ["php", candidate]
    return ["php", "index.php"]


def _makefile_command(content: str | None) -> list[str]:
    if content:
        targets = [match.group(1) for match in _MAKE_TARGET_RE.finditer(content)]
        for preferred in ("run", "start", "serve", "up"):
            if preferred in targets:
                return ["make", preferred]
        seen: set[str] = set()
        ordered = [name for name in targets if not (name in seen or seen.add(name))]  # type: ignore[func-returns-value]
        if ordered:
            return ["make", ordered[0]]
    return ["make"]


def detect_runtime(file_list_or_snapshot) -> list[str]:
    """Map repo contents to a runtime argv without executing anything.

    Pure function on file names and (optionally) file contents: no
    subprocesses, no filesystem reads, no network. Accepts a list of file
    names (plain strings), ``{name: content}`` entries or ``(name, content)``
    pairs, a name-to-content mapping, or a snapshot-like object with a
    ``.files`` mapping. Unknown repos raise ``ValueError`` with an actionable
    message so callers fail closed with an explicit command required.
    """
    entries = _normalise_file_entries(file_list_or_snapshot)
    if not entries:
        raise ValueError(
            "could not detect runtime_command from repo contents; "
            + _ACTIONABLE_SUFFIX
        )
    names = {name for name, _ in entries}
    basenames = {_basename(name) for name in names}

    def _content_for(*wanted: str) -> str | None:
        for name, content in entries:
            if _basename(name) in wanted and content:
                return content
        return None

    candidates: dict[str, list[str]] = {}
    if "package.json" in basenames:
        candidates["package.json"] = _package_json_command(
            _content_for("package.json")
        )
    if "requirements.txt" in basenames or "pyproject.toml" in basenames:
        candidates["python"] = _python_command(names)
    if "composer.json" in basenames:
        candidates["composer.json"] = _php_command(names)
    makefile_hit = basenames & _MAKEFILE_NAMES
    if makefile_hit:
        candidates["makefile"] = _makefile_command(
            _content_for(*sorted(makefile_hit))
        )
    for key in _DETECT_PRECEDENCE:
        if key in candidates:
            return candidates[key]
    raise ValueError(
        "could not detect runtime_command from repo contents "
        f"({len(entries)} file(s) seen); " + _ACTIONABLE_SUFFIX
    )


def intake_repo_to_snapshot(
    spec: RepoIntakeSpec,
    runtime_command: list | tuple | None = None,
    *,
    sandbox=None,
    file_list=None,
) -> RepoIntakeSnapshot:
    """Stage a validated repo intake via Docker staging-container semantics.

    Phase-1 contract: validates ``spec`` (type + field validators run at
    construction), records the staging plan — clone inside a non-started
    ``network_mode="none"`` container with no host mounts, ``git checkout``
    the pinned commit, snapshot the tree — as manifest metadata, and returns
    a snapshot-compatible manifest with a ``.files`` mapping. ``sandbox``
    accepts the session's ``DockerSandboxManager`` (or a mock in tests);
    any other keyword (e.g. ``host_path=...``) raises ``TypeError`` so
    intake can never be pointed at host paths. No network clone happens in
    this wave.

    Runtime auto-detect (opt-in): pass ``runtime_command=None`` together with
    ``file_list=...`` (anything ``detect_runtime`` accepts) to derive the
    argv from repo contents. An explicit ``runtime_command`` always wins and
    ``file_list`` is then ignored for detection. Omitting both fails closed
    with ``ValueError``.
    """
    if not isinstance(spec, RepoIntakeSpec):
        raise ValueError("spec must be a RepoIntakeSpec")
    if runtime_command is None:
        if file_list is None:
            raise ValueError(
                "runtime_command is required when file_list is not given; "
                + _ACTIONABLE_SUFFIX
            )
        runtime_command = detect_runtime(file_list)
    if not isinstance(runtime_command, (list, tuple)) or not runtime_command:
        raise ValueError("runtime_command must be a non-empty argv list")
    if any(not isinstance(item, str) or not item for item in runtime_command):
        raise ValueError("runtime_command entries must be non-empty strings")
    # Staging plan (Phase-1 record; real clone lands in a later wave):
    # 1. manager.client.containers.create(base, command=["true"],
    #        network_mode="none", **manager._options("verifier")) — never started.
    # 2. git clone <url> inside the staged container filesystem only.
    # 3. git checkout <commit_hash>; snapshot tree via snapshot_project path.
    # 4. stage.remove(force=True); cleanup removes session images/networks.
    manifest = MappingProxyType(
        {
            "repo.url": spec.url.encode("utf-8"),
            "repo.commit_hash": spec.commit_hash.encode("utf-8"),
            "repo.runtime_command": json.dumps(list(runtime_command)).encode("utf-8"),
        }
    )
    return RepoIntakeSnapshot(
        files=manifest,
        url=spec.url,
        commit_hash=spec.commit_hash,
        runtime_command=tuple(runtime_command),
        digest=_manifest_digest(spec, tuple(runtime_command)),
    )
