# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Shared paced HTTP+JSON leaf: one discipline for every keyless intel call.

Extracted-module authorship: the pacing/backoff/cap logic used to live as
`research._pace` / `research._get_json` / `research._post_json`. It moved
here (not copied); `research.py` re-exports the new names for backward
compat. All keyless transports (`research`, `intel_search`, `deep_scan`,
`scanner_dtrack`) route through this leaf so pacing, retry, and response
caps stay identical everywhere.

Perf notes (opt-perf lane):
- Per-host pacing: `_last_calls` is keyed by URL host, so a slow NVD
  backoff no longer stalls unrelated OSV/CIRCL calls sharing the process.
- Every helper takes an explicit `max_bytes` cap; oversize bodies are
  rejected before JSON parsing, never buffered unbounded.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "Secure-Mitigation-System/0.1 research-sidecar (+https://github.com)"
MIN_GAP_SECONDS = 1.0
DEFAULT_MAX_BYTES = 1 * 1024 * 1024

# Rate-limit graceful: jittered exponential backoff with a cap, and a capped
# honor of the server's Retry-After on 429. Attempts are always bounded by the
# caller's `tries` (normalized to >= 1); there is no infinite retry loop.
BACKOFF_MAX_SECONDS = 30.0
BACKOFF_JITTER_SECONDS = 1.0
RETRY_AFTER_MAX_SECONDS = 60.0

# Per-host pacing state: host -> monotonic timestamp of the last request.
_last_calls: dict[str, float] = {}


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header (delta-seconds only); None when absent/invalid."""
    if not value:
        return None
    try:
        return max(float(value.strip()), 0.0)
    except (TypeError, ValueError):
        return None


def _backoff_seconds(attempt: int, retry_after: float | None = None) -> float:
    """Jittered exponential backoff for retry `attempt` (0-based), capped."""
    if retry_after is not None:
        base = min(max(retry_after, 0.0), RETRY_AFTER_MAX_SECONDS)
    else:
        base = min(2.0**attempt, BACKOFF_MAX_SECONDS)
    return base + random.uniform(0, BACKOFF_JITTER_SECONDS)


def _retry_after_of(exc: BaseException) -> float | None:
    """Retry-After seconds from an HTTPError, else None. 429 only."""
    if not isinstance(exc, urllib.error.HTTPError) or exc.code != 429:
        return None
    try:
        return _parse_retry_after(exc.headers.get("Retry-After"))
    except Exception:
        return None


def _host_of(url: str) -> str:
    """Lowercased URL host used as the pacing key. Empty on unparseable URLs."""
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""


def _pace(host: str = "") -> None:
    """Enforce a jittered minimum gap between requests to one host."""
    now = time.monotonic()
    wait = MIN_GAP_SECONDS + random.uniform(0, 1.0) - (now - _last_calls.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_calls[host] = time.monotonic()


def paced_request_json(
    method: str,
    url: str,
    *,
    body: dict | list | None = None,
    headers: dict | None = None,
    timeout: float = 20.0,
    tries: int = 3,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict | list:
    """One paced JSON round-trip with backoff-with-jitter and a response cap."""
    heads = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        heads["Content-Type"] = "application/json"
    if headers:
        heads.update(headers)
    data = json.dumps(body).encode() if body is not None else None
    host = _host_of(url)
    last: Exception | None = None
    attempts = max(int(tries), 1)  # never zero: one attempt minimum, never unbounded
    for attempt in range(attempts):
        _pace(host)
        request = urllib.request.Request(url, data=data, headers=heads, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise ValueError(f"intel response exceeded the {max_bytes} byte cap")
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:  # network, HTTP error, bad JSON: back off
            last = exc
            if attempt >= attempts - 1:
                break  # budget exhausted: surface, never loop forever
            time.sleep(_backoff_seconds(attempt, _retry_after_of(exc)))
    raise RuntimeError(f"intel request failed after {attempts} tries: {last}") from last


def paced_get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 20.0,
    tries: int = 3,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict | list:
    """GET JSON with pacing, backoff-with-jitter, and a response cap."""
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    return paced_request_json(
        "GET", url + query, headers=headers, timeout=timeout, tries=tries, max_bytes=max_bytes
    )


def paced_post_json(
    url: str,
    payload: dict | list,
    timeout: float = 20.0,
    tries: int = 3,
    max_bytes: int = DEFAULT_MAX_BYTES,
    headers: dict | None = None,
) -> dict | list:
    """POST JSON with the same pacing/backoff/cap discipline as paced_get_json."""
    return paced_request_json(
        "POST",
        url,
        body=payload,
        headers=headers,
        timeout=timeout,
        tries=tries,
        max_bytes=max_bytes,
    )


def raw_get_json(
    url: str,
    headers: dict | None = None,
    timeout: float = 20.0,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict | list:
    """Single-attempt GET JSON with a response cap. No pacing, no retries."""
    heads = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        heads.update(headers)
    request = urllib.request.Request(url, headers=heads, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f"intel response exceeded the {max_bytes} byte cap")
    return json.loads(raw.decode("utf-8"))
