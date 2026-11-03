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
import ipaddress
import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import urlparse

_INGEST_DIGEST_DOMAIN = b"purplebox-repo-intake-manifest-v1\0"
_COMMIT_HEX_CHARS = frozenset("0123456789abcdefABCDEF")

# Shell-active characters: rejected from intake URLs as defense-in-depth.
# The clone path below uses argv-list exec (no shell), so these bytes could
# not execute there — but a future caller routing a URL through a shell
# must not inherit a live injection. `rm`, separators, substitution,
# quoting, globbing, and whitespace are all refused.
_SHELL_METACHARS = frozenset("$`;&|(){}[]!#*?~<>\\'\"\n\r\t ")

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
    "pass an explicit runtime_command argv (e.g. ['python3', 'main.py']) to intake_repo_to_snapshot"
)


@dataclass(frozen=True)
class RepoIntakeSpec:
    """Validated repo-intake request: HTTPS remote + optional pinned 40-hex commit.

    Rejects non-HTTPS schemes (``git://``, ``ssh://``, scp-style
    ``host:path``) and blank/short/non-hex commit hashes. ``commit_hash=None``
    (the default) means the remote's default-branch HEAD as-is. No ``host_path``
    attribute exists by design: intake never touches host paths.
    """

    url: str
    commit_hash: str | None = None

    def __post_init__(self) -> None:
        # Error messages name the rule only: the URL may carry credentials.
        if not isinstance(self.url, str):
            raise ValueError("repo URL must be an https:// remote")
        parsed = urlparse(self.url)
        if "@" in parsed.netloc:
            raise ValueError("Repository URL must not embed credentials.")
        try:
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("Repository URL must not embed credentials.")
            parsed.port  # noqa: B018 - raises ValueError on a malformed port
        except ValueError as exc:
            if "credentials" in str(exc):
                raise
            raise ValueError("repo URL must be an https:// remote") from None
        host = (parsed.hostname or "").rstrip(".").lower()
        bad = next((c for c in self.url if c in _SHELL_METACHARS), None)
        if (
            parsed.scheme != "https"
            or not host
            or any(part in ("", ".", "..") for part in host.split("."))
            or bad is not None
        ):
            raise ValueError("repo URL must be an https:// remote")
        if _is_blocked_host(host):
            raise ValueError(
                "Repository URL host must be public (no loopback, private, link-local, "
                "reserved, multicast, or internal names)."
            )
        commit = self.commit_hash
        if commit is None:
            return
        if (
            not isinstance(commit, str)
            or len(commit) != 40
            or any(char not in _COMMIT_HEX_CHARS for char in commit)
        ):
            raise ValueError("commit_hash must be a 40-hex pinned commit (or None for HEAD)")


_BLOCKED_HOSTNAMES = frozenset({"localhost", "metadata.google.internal"})
_BLOCKED_HOST_SUFFIXES = (".localhost", ".internal", ".local")


def _is_blocked_host(host: str) -> bool:
    """True for internal names and non-public IP literals (SSRF guard)."""
    if host in _BLOCKED_HOSTNAMES or host.endswith(_BLOCKED_HOST_SUFFIXES):
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    return bool(
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
        or not addr.is_global
    )


@dataclass(frozen=True)
class RepoIntakeSnapshot:
    """Staging manifest for a validated repo intake (snapshot-compatible)."""

    files: MappingProxyType
    url: str
    commit_hash: str | None
    runtime_command: tuple
    digest: str


def _digest_commit(commit: str | None) -> bytes:
    return b"" if commit is None else commit.encode("utf-8")


def _manifest_digest(spec: RepoIntakeSpec, runtime_command: tuple) -> str:
    digest = hashlib.sha256()
    digest.update(_INGEST_DIGEST_DOMAIN)
    digest.update(spec.url.encode("utf-8"))
    digest.update(b"\0")
    digest.update(_digest_commit(spec.commit_hash))
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
            elif isinstance(entry, (list, tuple)) and len(entry) == 2 and isinstance(entry[0], str):
                items.append((entry[0], entry[1]))
            else:
                raise ValueError(
                    "file entries must be names, {name: content} dicts, or (name, content) pairs"
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
            "could not detect runtime_command from repo contents; " + _ACTIONABLE_SUFFIX
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
        candidates["package.json"] = _package_json_command(_content_for("package.json"))
    if "requirements.txt" in basenames or "pyproject.toml" in basenames:
        candidates["python"] = _python_command(names)
    if "composer.json" in basenames:
        candidates["composer.json"] = _php_command(names)
    makefile_hit = basenames & _MAKEFILE_NAMES
    if makefile_hit:
        candidates["makefile"] = _makefile_command(_content_for(*sorted(makefile_hit)))
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
    clone=False,
    clone_dir="/repo",
    clone_timeout_seconds=120,
    clone_image: str | None = None,
    **kwargs,
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
    if kwargs:
        unexpected = sorted(kwargs)
        raise TypeError(
            f"intake_repo_to_snapshot() got unexpected keyword(s) {unexpected}; "
            "intake can never be pointed at host paths"
        )
    if runtime_command is None:
        if file_list is None:
            raise ValueError(
                "runtime_command is required when file_list is not given; " + _ACTIONABLE_SUFFIX
            )
        runtime_command = detect_runtime(file_list)
    if not isinstance(runtime_command, (list, tuple)) or not runtime_command:
        raise ValueError("runtime_command must be a non-empty argv list")
    if any(not isinstance(item, str) or not item for item in runtime_command):
        raise ValueError("runtime_command entries must be non-empty strings")
    # Staging plan (clone=True): one run-to-completion container clones the
    # pinned commit into tmpfs /work, bytes leave via get_archive, and the
    # container is removed in ``finally``. See ``_clone_in_staging``.
    manifest = MappingProxyType(
        {
            "repo.url": spec.url.encode("utf-8"),
            "repo.commit_hash": _digest_commit(spec.commit_hash),
            "repo.runtime_command": json.dumps(list(runtime_command)).encode("utf-8"),
        }
    )
    if not clone:
        return RepoIntakeSnapshot(
            files=manifest,
            url=spec.url,
            commit_hash=spec.commit_hash,
            runtime_command=tuple(runtime_command),
            digest=_manifest_digest(spec, tuple(runtime_command)),
        )
    return _clone_in_staging(
        spec,
        tuple(runtime_command),
        manifest,
        sandbox=sandbox,
        clone_dir=clone_dir,
        clone_timeout_seconds=clone_timeout_seconds,
        clone_image=clone_image,
    )


_CLONE_SCRIPT_HEAD = (
    "git -c protocol.allow=never -c protocol.https.allow=always "
    "-c submodule.recurse=false clone --depth 1 --no-recurse-submodules "
    '-- "$1" /work/repo'
)
_CLONE_SCRIPT_PINNED = _CLONE_SCRIPT_HEAD + (
    " && "
    "git -C /work/repo -c protocol.allow=never -c protocol.https.allow=always "
    '-c submodule.recurse=false fetch --depth 1 origin "$2" && '
    'git -C /work/repo -c submodule.recurse=false checkout --detach "$2"'
)
# Back-compat alias: the pinned-commit script keeps the historic name.
_CLONE_SCRIPT = _CLONE_SCRIPT_PINNED


def _resolve_commit(spec: RepoIntakeSpec) -> tuple[str, list[str]]:
    """Pick the clone script and positional argv for ``spec``.

    Returns ``(script, argv)`` where ``argv`` is ``[url]`` for a ``None``
    commit (default-branch HEAD as-is: no ``fetch``/``checkout`` steps) or
    ``[url, commit]`` for a pinned 40-hex commit. The URL and commit stay
    positional ``sh -c`` arguments (``$1``/``$2``), never interpolated into
    the script text.
    """
    if spec.commit_hash is None:
        return _CLONE_SCRIPT_HEAD, [spec.url]
    return _CLONE_SCRIPT_PINNED, [spec.url, spec.commit_hash]


_NO_GIT_MESSAGE = (
    "staging clone unavailable: no git in the staging image; build or pass a clone image with git"
)


def _clone_in_staging(
    spec: RepoIntakeSpec,
    runtime_command: tuple,
    manifest,
    *,
    sandbox=None,
    clone_dir="/repo",
    clone_timeout_seconds=120,
    clone_image: str | None = None,
) -> RepoIntakeSnapshot:
    """Perform the real staging-container clone (opt-in ``clone=True``).

    Shape (F-202): a single run-to-completion container via
    ``client.containers.run(image, command=[...], detach=True)`` then
    ``container.wait(timeout=clone_timeout_seconds)``. Exec on a
    never-started container is a Docker 409, so create+exec is not used.

    LAW 4 isolation: the clone container has a bridge network for the git
    fetch only, no host mounts, bounded pids/mem/cpu, runs as uid 10001
    with all capabilities dropped and ``no-new-privileges``, and writes only
    to tmpfs ``/work``. URL and commit are positional ``sh -c`` arguments
    (``$1``/``$2``), never interpolated into the script; ``--`` precedes the
    URL; git is limited to https with submodules off; prompts and LFS smudge
    are disabled. Bytes leave only via ``get_archive`` tar streaming. Exit
    127 (no git in the image) fails closed; nothing is ever installed.
    ``clone_dir`` is retained for compatibility; the clone lives at
    ``/work/repo``.
    """
    import io
    import tarfile

    del clone_dir  # clone always lands in tmpfs /work/repo
    if sandbox is None:
        raise ValueError("clone=True requires a sandbox (DockerSandboxManager or test double)")
    client = getattr(sandbox, "client", None)
    if client is None:
        raise ValueError("clone=True requires a sandbox with a Docker client")
    config = getattr(sandbox, "config", None)
    clone_configured = getattr(config, "clone_base_image", None)
    # Legacy backstop: test doubles built before clone_base_image existed only
    # carry target_base_image; prefer them over the "sms-clone" literal so
    # those doubles keep resolving a real configured tag.
    legacy_configured = getattr(config, "target_base_image", None)
    image = (
        clone_image
        or (clone_configured if isinstance(clone_configured, str) else None)
        or (legacy_configured if isinstance(legacy_configured, str) else None)
        or "sms-clone"
    )
    if not isinstance(image, str) or not image:
        raise ValueError("clone=True requires a clone image (sandbox.config.clone_base_image)")
    host = urlparse(spec.url).hostname or "?"
    commit = spec.commit_hash or "HEAD"
    where = f"{host} @ {commit[:12]}"
    script, argv = _resolve_commit(spec)
    container = client.containers.run(
        image,
        command=["sh", "-c", script, "sh", *argv],
        detach=True,
        network_mode="bridge",
        user="10001",
        working_dir="/work",
        tmpfs={"/work": "rw,nosuid,nodev,size=64m,uid=10001,gid=10001,mode=0700"},
        environment={
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": "/work",
        },
        pids_limit=128,
        mem_limit="512m",
        nano_cpus=1_000_000_000,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        read_only=True,
        entrypoint=[],
    )
    try:
        try:
            status = container.wait(timeout=clone_timeout_seconds)
        except Exception:
            raise ValueError(f"staging clone failed (timeout or wait error) for {where}") from None
        code = status.get("StatusCode", 1) if isinstance(status, dict) else 1
        if code == 127:
            raise ValueError(_NO_GIT_MESSAGE)
        if code != 0:
            raise ValueError(f"staging clone failed for {where} (exit {code})")
        stream, _stat = container.get_archive("/work/repo")
        chunks = list(stream) if not isinstance(stream, (bytes, bytearray)) else [bytes(stream)]
        tar_bytes = b"".join(chunks)
        files: dict[str, bytes] = {}
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                name = member.name
                # Strip the .git tree: untrusted bytes stay bounded.
                if (
                    "/.git/" in name
                    or name.startswith(".git/")
                    or name.rstrip("/").endswith("/.git")
                ):
                    continue
                rel = name
                if rel.startswith("."):
                    rel = rel[1:].lstrip("/")
                if not rel or ".." in rel.split("/"):
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                content = extracted.read()
                if len(files) >= 2000 or sum(map(len, files.values())) + len(content) > 8_000_000:
                    break
                files[rel] = content
        return RepoIntakeSnapshot(
            files=MappingProxyType(dict(manifest) | {f"tree/{k}": v for k, v in files.items()}),
            url=spec.url,
            commit_hash=spec.commit_hash,
            runtime_command=tuple(runtime_command),
            digest=_manifest_digest(spec, tuple(runtime_command)),
        )
    finally:
        try:
            container.remove(force=True)
        except Exception:
            pass
