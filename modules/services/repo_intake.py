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
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import urlparse

_INGEST_DIGEST_DOMAIN = b"purplebox-repo-intake-manifest-v1\0"
_COMMIT_HEX_CHARS = frozenset("0123456789abcdefABCDEF")


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


def intake_repo_to_snapshot(
    spec: RepoIntakeSpec,
    runtime_command: list | tuple,
    *,
    sandbox=None,
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
    """
    if not isinstance(spec, RepoIntakeSpec):
        raise ValueError("spec must be a RepoIntakeSpec")
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
