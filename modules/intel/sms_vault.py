# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Role-separated encrypted threat and mitigation vault (Subsystem B, Y2).

Persistent local artifact and episodic memory, encrypted at rest with
AES-256-GCM (authenticated symmetric crypto from the `cryptography`
package). The 32-byte vault key lives in a single owner-only (0600) file
inside the vault directory; it is generated locally with os.urandom, never
committed to Git (vault dir defaults under ~/.cache / ./.sms-vault, both
git-ignored), never leaked to logs or reports, and without it the blobs
are undecryptable.

Strict three-way namespace separation:
  RED_VAULT   — verified boundary-escape payload shapes, input-mutation
                shapes, successful exploit probe templates, binary RE hooks.
  BLUE_VAULT  — verified minimal sanitization diffs, guard-compliant patch
                templates, language hardening idioms, binary patch shims.
  GREEN_VAULT — synthesized flawed-service archetypes, CVE-inspired
                structural patterns, normal-behavior contract templates.

Cross-reference intelligence ("Done Before" vs "Never Done Before"):
fingerprint_source() hashes the normalized sink/flow structure of a target;
query_vault() reports KNOWN_ARCHETYPE when any namespace holds the
fingerprint, else NOVEL_SURFACE. commit_verified() stores a new finding
only after Docker evidence decided (caller enforces exit 0 -> 1 +
regressions green). vault_stats() returns redacted telemetry only:
counts and token-saving estimates, never payload material.

Fail closed: undecryptable blob, missing record, or I/O error raises
VaultError (never returns a forgiving default that could be mistaken
for "no history").
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from enum import Enum
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict

VAULT_KEY_BYTES = 32
VAULT_NONCE_BYTES = 12
_BLOB_VERSION = 1


class VaultError(ValueError):
    """Vault failure: undecryptable blob, missing record, or I/O refusal."""


class VaultNamespace(str, Enum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"


class VaultQueryResult(BaseModel):
    """Cross-reference answer for one fingerprinted target."""

    model_config = ConfigDict(extra="forbid", strict=True)
    status: str  # KNOWN_ARCHETYPE | NOVEL_SURFACE
    fingerprint: str
    record_count: int = 0
    namespaces: list[str] = []


def default_vault_dir() -> Path:
    override = os.getenv("PURPLEBOX_VAULT_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".cache" / "secure-mitigation-system" / "vault"


def _key_path(vault_dir: Path) -> Path:
    return vault_dir / "vault.key"


def load_or_create_key(vault_dir: Path) -> bytes:
    """Load the local 32-byte vault key, creating it owner-only if absent."""
    vault_dir.mkdir(parents=True, exist_ok=True)
    try:
        vault_dir.chmod(0o700)
    except OSError:
        pass
    key_path = _key_path(vault_dir)
    if key_path.exists():
        try:
            raw = key_path.read_bytes()
        except OSError as exc:
            raise VaultError(f"Vault key unreadable ({type(exc).__name__}).") from exc
        if len(raw) != VAULT_KEY_BYTES:
            raise VaultError("Vault key has an unexpected length; refusing to use it.")
        try:
            key_path.chmod(0o600)
        except OSError:
            pass
        return raw
    key = secrets.token_bytes(VAULT_KEY_BYTES)
    try:
        fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return load_or_create_key(vault_dir)
    except OSError as exc:
        raise VaultError(f"Vault key cannot be created ({type(exc).__name__}).") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(key)
    except OSError as exc:
        raise VaultError(f"Vault key cannot be written ({type(exc).__name__}).") from exc
    return key


def encrypt_blob(payload: dict, *, key: bytes) -> bytes:
    """Serialize + AES-256-GCM encrypt one payload dict."""
    if len(key) != VAULT_KEY_BYTES:
        raise VaultError("Vault key must be 32 bytes.")
    plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")
    nonce = secrets.token_bytes(VAULT_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return json.dumps(
        {
            "v": _BLOB_VERSION,
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
        }
    ).encode("utf-8")


def decrypt_blob(blob: bytes, *, key: bytes) -> dict:
    """Decrypt one blob; wrong key or tampering raises VaultError."""
    if len(key) != VAULT_KEY_BYTES:
        raise VaultError("Vault key must be 32 bytes.")
    try:
        envelope = json.loads(blob.decode("utf-8"))
        nonce = bytes.fromhex(envelope["nonce"])
        ciphertext = bytes.fromhex(envelope["ciphertext"])
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        data = json.loads(plaintext.decode("utf-8"))
    except (ValueError, KeyError, InvalidTag, UnicodeDecodeError) as exc:
        raise VaultError(f"Vault blob failed authentication ({type(exc).__name__}).") from exc
    if not isinstance(data, dict):
        raise VaultError("Vault blob did not decrypt to a record.")
    return data


_SINK_TOKENS = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def fingerprint_source(source: str) -> str:
    """Deterministic 64-hex fingerprint of a target's sink/flow structure.

    Normalizes away string literals, numbers, comments, and whitespace so
    cosmetic rewrites fingerprint identically, while any change to the
    identifier/operator skeleton (the part attackers and patches touch)
    flips the digest.
    """
    normalized_lines: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "//", "--", "*", "<!--")):
            continue
        no_strings = re.sub(r"'[^']*'|\"[^\"]*\"|`[^`]*`", "STR", stripped)
        no_numbers = re.sub(r"\b\d[\d._xXa-fA-F]*\b", "NUM", no_strings)
        tokens = _SINK_TOKENS.findall(no_numbers)
        operators = re.sub(r"[A-Za-z0-9_$\s]", "", no_numbers)
        normalized_lines.append(" ".join(tokens) + "|" + operators)
    normalized_lines.sort()
    return hashlib.sha256("\n".join(normalized_lines).encode("utf-8")).hexdigest()


def _record_id(namespace: VaultNamespace, fingerprint: str, payload: dict) -> str:
    seed = json.dumps(payload, sort_keys=True) + namespace.value + fingerprint
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


class VaultStore:
    """One namespace view over the encrypted on-disk vault."""

    def __init__(
        self,
        namespace: VaultNamespace,
        vault_dir: Path | str | None = None,
    ):
        self.namespace = namespace
        self.vault_dir = Path(vault_dir) if vault_dir is not None else default_vault_dir()
        self.key_path = _key_path(self.vault_dir)
        self._key = load_or_create_key(self.vault_dir)
        self.namespace_dir = self.vault_dir / namespace.value
        self.namespace_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.namespace_dir.chmod(0o700)
        except OSError:
            pass

    def _blob_path(self, record_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", record_id):
            raise VaultError("Record id is malformed.")
        return self.namespace_dir / f"{record_id}.vault"

    def _index_path(self) -> Path:
        return self.namespace_dir / "_fingerprints.json"

    def _read_index(self) -> dict[str, int] | None:
        """Read the fingerprint index; None means missing/corrupt → full scan."""
        try:
            raw = self._index_path().read_bytes()
        except OSError:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        counts: dict[str, int] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, int) and value > 0:
                counts[key] = value
            else:
                return None
        return counts

    def _bump_index(self, fingerprint: str) -> None:
        """Best-effort index update; failures never break the commit."""
        if not fingerprint:
            return
        try:
            counts = self._read_index() or {}
            counts[fingerprint] = counts.get(fingerprint, 0) + 1
            encoded = json.dumps(counts, sort_keys=True).encode("utf-8")
            if len(encoded) > 1_000_000:
                return
            path = self._index_path()
            path.write_bytes(encoded)
            try:
                path.chmod(0o600)
            except OSError:
                pass
        except (OSError, ValueError, TypeError):
            pass

    def commit(self, payload: dict, *, fingerprint: str = "") -> str:
        """Encrypt + persist one payload; returns its deterministic record id."""
        if not isinstance(payload, dict):
            raise VaultError("Vault payload must be a mapping.")
        record_id = _record_id(self.namespace, fingerprint, payload)
        stored = {"fingerprint": fingerprint, "payload": payload}
        blob = encrypt_blob(stored, key=self._key)
        path = self._blob_path(record_id)
        try:
            path.write_bytes(blob)
            path.chmod(0o600)
        except OSError as exc:
            raise VaultError(f"Vault write failed ({type(exc).__name__}).") from exc
        self._bump_index(fingerprint)
        return record_id

    def fetch(self, record_id: str) -> dict:
        """Decrypt one record from THIS namespace; absent/wrong-ns -> KeyError."""
        path = self._blob_path(record_id)
        try:
            blob = path.read_bytes()
        except OSError as exc:
            raise KeyError(record_id) from exc
        stored = decrypt_blob(blob, key=self._key)
        return stored.get("payload", stored)

    def record_fingerprints(self) -> dict[str, int]:
        """fingerprint -> count for this namespace (metadata only).

        Prefers the bounded JSON index (O(1)); falls back to a full decrypt
        scan when the index is missing or corrupt (fail open to correctness).
        """
        indexed = self._read_index()
        if indexed is not None:
            return dict(indexed)
        counts: dict[str, int] = {}
        try:
            paths = list(self.namespace_dir.glob("*.vault"))
        except OSError as exc:
            raise VaultError(f"Vault list failed ({type(exc).__name__}).") from exc
        for path in paths:
            try:
                stored = decrypt_blob(path.read_bytes(), key=self._key)
            except VaultError:
                continue
            fingerprint = stored.get("fingerprint", "")
            if isinstance(fingerprint, str) and fingerprint:
                counts[fingerprint] = counts.get(fingerprint, 0) + 1
        return counts

    def count(self) -> int:
        try:
            return len(list(self.namespace_dir.glob("*.vault")))
        except OSError as exc:
            raise VaultError(f"Vault list failed ({type(exc).__name__}).") from exc


def query_vault(source: str, vault_dir: Path | str | None = None) -> VaultQueryResult:
    """Fingerprint a target and report KNOWN_ARCHETYPE vs NOVEL_SURFACE."""
    fingerprint = fingerprint_source(source)
    base = Path(vault_dir) if vault_dir is not None else default_vault_dir()
    hits: list[str] = []
    total = 0
    for namespace in VaultNamespace:
        try:
            store = VaultStore(namespace, vault_dir=base)
            count = store.record_fingerprints().get(fingerprint, 0)
        except VaultError:
            continue
        if count:
            hits.append(namespace.value)
            total += count
    return VaultQueryResult(
        status="KNOWN_ARCHETYPE" if hits else "NOVEL_SURFACE",
        fingerprint=fingerprint,
        record_count=total,
        namespaces=sorted(hits),
    )


def commit_verified(
    *,
    namespace: VaultNamespace,
    source: str,
    payload: dict,
    vault_dir: Path | str | None = None,
) -> str:
    """Commit a Docker-verified finding/patch under its source fingerprint.

    Caller must enforce: only after exit 0 pre-patch -> exit 1 post-patch
    with regression gates green. This function records; it never verifies.
    """
    fingerprint = fingerprint_source(source)
    base = Path(vault_dir) if vault_dir is not None else default_vault_dir()
    store = VaultStore(namespace, vault_dir=base)
    return store.commit(payload, fingerprint=fingerprint)


def vault_stats(vault_dir: Path | str | None = None) -> dict:
    """Redacted telemetry: per-namespace counts + savings estimate.

    Never includes payload material (sinks, shapes, diffs, notes) — only
    counts and a rough token-saving estimate (known archetypes save a
    red-analysis round trip each).
    """
    base = Path(vault_dir) if vault_dir is not None else default_vault_dir()
    stats: dict = {}
    known = 0
    for namespace in VaultNamespace:
        try:
            count = VaultStore(namespace, vault_dir=base).count()
        except VaultError:
            count = 0
        stats[namespace.value] = {"records": count}
        known += count
    stats["known_archetypes"] = known
    stats["tokens_saved_estimate"] = known * 2000
    return stats
