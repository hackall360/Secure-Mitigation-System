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
import stat
import tempfile
import time
from enum import Enum
from pathlib import Path

try:  # POSIX only; non-POSIX keeps unlocked index updates (no fcntl there).
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None  # type: ignore[assignment]

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict

from library.shared.sms_observability import get_aspect
from library.shared.sms_observability import log as obs_log
from library.shared.sms_observability import record_metric as obs_record_metric
from library.shared.sms_observability import trace as obs_trace

VAULT_KEY_BYTES = 32
VAULT_NONCE_BYTES = 12
_BLOB_VERSION = 1

_VAULT_ASPECT = get_aspect("intel.vault")


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
        try:
            path = Path(override).expanduser()
        except RuntimeError as exc:
            raise VaultError(
                "Vault directory unavailable: set PURPLEBOX_VAULT_DIR or HOME."
            ) from exc
        if not path.is_absolute():
            raise VaultError("PURPLEBOX_VAULT_DIR must be an absolute path.")
        return path
    try:
        home = Path.home()
    except (RuntimeError, KeyError, OSError) as exc:
        raise VaultError("Vault directory unavailable: set PURPLEBOX_VAULT_DIR or HOME.") from exc
    return home / ".cache" / "secure-mitigation-system" / "vault"


_STALE_TMP_SECONDS = 3600


def _enforce_mode(path: Path, mode: int) -> None:
    """chmod to an owner-only mode and, on POSIX, verify it stuck.

    Non-POSIX (Windows) has no meaningful group/other mode bits: chmod only
    toggles read-only, so verification would always fail and is skipped.
    """
    try:
        path.chmod(mode)
    except OSError:
        pass
    if os.name != "posix":
        return
    try:
        actual = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        raise VaultError(f"Vault permissions could not be checked ({type(exc).__name__}).") from exc
    if actual & 0o077:
        raise VaultError(
            "Vault permissions could not be restricted "
            "(filesystem does not support owner-only modes)."
        )


def _mkdir_private(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise VaultError(f"Vault directory not writable ({type(exc).__name__}).") from exc
    _enforce_mode(path, 0o700)


def _key_path(vault_dir: Path) -> Path:
    return vault_dir / "vault.key"


def load_or_create_key(vault_dir: Path) -> bytes:
    """Load the local 32-byte vault key, creating it owner-only if absent."""
    _mkdir_private(vault_dir)
    key_path = _key_path(vault_dir)
    if key_path.exists():
        try:
            raw = key_path.read_bytes()
        except OSError as exc:
            raise VaultError(f"Vault key unreadable ({type(exc).__name__}).") from exc
        if len(raw) != VAULT_KEY_BYTES:
            raise VaultError(
                "Vault key has an unexpected length; refusing to use it. "
                "Restore the original vault.key or move the vault directory aside "
                "to start fresh (existing records will not decrypt)."
            )
        _enforce_mode(key_path, 0o600)
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
    _enforce_mode(key_path, 0o600)
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


_COMMENT_PREFIXES = ("#", "//", "--", "*", "<!--")


def fingerprint_source(source: str) -> str:
    """Deterministic 64-hex fingerprint of a target's sink/flow structure.

    Normalizes away string literals, numbers, comments, and whitespace so
    cosmetic rewrites fingerprint identically, while any change to the
    identifier/operator skeleton (the part attackers and patches touch)
    flips the digest.

    Vacuous lines still contribute a kind tag (code vs comment vs blank)
    so an empty source never digests identically to a comment-only one:
    that collision would let a novel empty target recall as KNOWN.
    """
    normalized_lines: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            normalized_lines.append("blank|")
            continue
        if stripped.startswith(_COMMENT_PREFIXES):
            normalized_lines.append("comment|")
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
        _mkdir_private(self.namespace_dir)
        self._clean_stale_tmp()

    def _clean_stale_tmp(self) -> None:
        """Best-effort removal of crash-orphaned *.tmp files older than 1h."""
        try:
            cutoff = time.time() - _STALE_TMP_SECONDS
            for tmp in self.namespace_dir.glob("*.tmp"):
                try:
                    if tmp.stat().st_mtime < cutoff:
                        tmp.unlink()
                except OSError:
                    continue
        except Exception:
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
        # POSIX: advisory flock on a sidecar serializes read-modify-write
        # across threads and processes (flock binds to the open file
        # description, so separate opens contend). Non-POSIX: unlocked,
        # as before; a lost update only degrades the index, never records.
        lock_fd = None
        try:
            if fcntl is not None:
                lock_fd = os.open(
                    str(self.namespace_dir / "index.lock"), os.O_RDWR | os.O_CREAT, 0o600
                )
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            counts = self._read_index() or {}
            counts[fingerprint] = counts.get(fingerprint, 0) + 1
            encoded = json.dumps(counts, sort_keys=True).encode("utf-8")
            if len(encoded) > 1_000_000:
                return
            path = self._index_path()
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self.namespace_dir), prefix="_fingerprints.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(tmp_name, 0o600)
                os.replace(tmp_name, path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            _enforce_mode(path, 0o600)
        except (OSError, ValueError, TypeError):
            pass
        finally:
            if lock_fd is not None:
                try:
                    if fcntl is not None:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)

    def commit(self, payload: dict, *, fingerprint: str = "") -> str:
        """Encrypt + persist one payload; returns its deterministic record id.

        Atomic: bytes land in a sibling temp file and are renamed over the
        final path, so a crash can never leave a truncated .vault blob
        that count() would count but nothing could decrypt.
        """
        if not isinstance(payload, dict):
            raise VaultError("Vault payload must be a mapping.")
        record_id = _record_id(self.namespace, fingerprint, payload)
        stored = {"fingerprint": fingerprint, "payload": payload}
        blob = encrypt_blob(stored, key=self._key)
        path = self._blob_path(record_id)
        tmp_fd = None
        try:
            tmp_fd, tmp_name = tempfile.mkstemp(
                dir=str(path.parent), prefix=record_id + ".", suffix=".tmp"
            )
            try:
                with os.fdopen(tmp_fd, "wb") as handle:
                    tmp_fd = None
                    handle.write(blob)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(tmp_name, 0o600)
                os.replace(tmp_name, path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
        except OSError as exc:
            raise VaultError(f"Vault write failed ({type(exc).__name__}).") from exc
        finally:
            if tmp_fd is not None:
                os.close(tmp_fd)
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
        scan when the index is missing or corrupt.
        Fallback scan fails closed: blobs present but none decryptable
        raises VaultError instead of reporting an empty (NOVEL) result.
        """
        indexed = self._read_index()
        if indexed is not None:
            return dict(indexed)
        counts: dict[str, int] = {}
        unreadable = 0
        try:
            paths = list(self.namespace_dir.glob("*.vault"))
        except OSError as exc:
            raise VaultError(f"Vault list failed ({type(exc).__name__}).") from exc
        for path in paths:
            try:
                stored = decrypt_blob(path.read_bytes(), key=self._key)
            except VaultError:
                unreadable += 1
                continue
            fingerprint = stored.get("fingerprint", "")
            if isinstance(fingerprint, str) and fingerprint:
                counts[fingerprint] = counts.get(fingerprint, 0) + 1
        if unreadable and not counts:
            raise VaultError("Vault blobs present but none decryptable; refusing empty result.")
        return counts

    def count(self) -> int:
        try:
            return len(list(self.namespace_dir.glob("*.vault")))
        except OSError as exc:
            raise VaultError(f"Vault list failed ({type(exc).__name__}).") from exc


def query_vault(source: str, vault_dir: Path | str | None = None) -> VaultQueryResult:
    """Fingerprint a target and report KNOWN_ARCHETYPE vs NOVEL_SURFACE.

    LAW 4: the fingerprint is a one-way digest (safe to log); `source`
    text, namespaces beyond their names, payloads, keys, and blobs are
    never logged. Only the operation name, status, record count, and
    namespace names (fixed enum values) are recorded.
    """
    started = time.monotonic()
    obs_log(
        _VAULT_ASPECT,
        "vault.query.start",
        message="vault query started",
        operation="query",
    )
    status = "NOVEL_SURFACE"
    fingerprint = ""
    try:
        with obs_trace(_VAULT_ASPECT, "vault.query"):
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
            result = VaultQueryResult(
                status="KNOWN_ARCHETYPE" if hits else "NOVEL_SURFACE",
                fingerprint=fingerprint,
                record_count=total,
                namespaces=sorted(hits),
            )
    except Exception:
        status = "error"
        raise
    else:
        status = result.status
        return result
    finally:
        duration_ms = round((time.monotonic() - started) * 1000, 3)
        fields: dict[str, object] = {"operation": "query", "status": status}
        if status != "error":
            try:
                fields["record_count"] = result.record_count
                fields["namespaces"] = list(result.namespaces)
            except Exception:
                pass
        # Fingerprint is a sha256 hex digest, not key material — safe to keep
        # in the returned record (callers already receive it); only counts
        # and the fixed status string go to the log.
        obs_log(
            _VAULT_ASPECT,
            "vault.query.result",
            message="vault query finished",
            duration_ms=duration_ms,
            **fields,
        )
        obs_record_metric(_VAULT_ASPECT, "vault.query.duration_ms", duration_ms, unit="ms")


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

    LAW 4: only the namespace name (fixed enum value) is logged — never the
    source text, payload keys/values, record id (opaque handle), key bytes,
    or blobs.
    """
    started = time.monotonic()
    obs_log(
        _VAULT_ASPECT,
        "vault.commit.start",
        message="vault commit started",
        operation="commit",
        namespace=namespace.value,
    )
    status = "ok"
    try:
        with obs_trace(_VAULT_ASPECT, "vault.commit"):
            fingerprint = fingerprint_source(source)
            base = Path(vault_dir) if vault_dir is not None else default_vault_dir()
            store = VaultStore(namespace, vault_dir=base)
            record_id = store.commit(payload, fingerprint=fingerprint)
    except Exception:
        status = "error"
        raise
    else:
        return record_id
    finally:
        duration_ms = round((time.monotonic() - started) * 1000, 3)
        obs_log(
            _VAULT_ASPECT,
            "vault.commit.result",
            message="vault commit finished",
            operation="commit",
            namespace=namespace.value,
            status=status,
            duration_ms=duration_ms,
        )
        obs_record_metric(_VAULT_ASPECT, "vault.commit.duration_ms", duration_ms, unit="ms")


def vault_stats(vault_dir: Path | str | None = None) -> dict:
    """Redacted telemetry: per-namespace counts + savings estimate.

    Never includes payload material (sinks, shapes, diffs, notes) — only
    counts and a rough token-saving estimate (known archetypes save a
    red-analysis round trip each).

    LAW 4: the returned dict is already redacted (counts only); the
    observability milestone logs the same counts, never anything more.
    """
    started = time.monotonic()
    base = Path(vault_dir) if vault_dir is not None else default_vault_dir()
    stats = {"known_archetypes": 0, "tokens_saved_estimate": 0}
    try:
        with obs_trace(_VAULT_ASPECT, "vault.stats"):
            stats = {}
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
    except Exception:
        raise
    else:
        return stats
    finally:
        duration_ms = round((time.monotonic() - started) * 1000, 3)
        try:
            known_logged = int(stats.get("known_archetypes", 0))
        except Exception:
            known_logged = -1
        obs_log(
            _VAULT_ASPECT,
            "vault.stats.result",
            message="vault stats finished",
            operation="stats",
            known_archetypes=known_logged,
            duration_ms=duration_ms,
        )
        obs_record_metric(_VAULT_ASPECT, "vault.stats.duration_ms", duration_ms, unit="ms")
