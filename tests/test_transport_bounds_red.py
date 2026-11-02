# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first pins for sms_http transport clamp invariants (overnight task-008).

Every keyless intel call routes through paced_request_json/paced_get_json,
whose timeout/tries/max_bytes are clamped to sane ranges. These tests pin
the bounds so a future edit cannot silently widen them or break the
garbage/NaN never-raise posture. Additive only: no behavior change.
"""

import math

import modules.shared.sms_http as leaf


def test_clamp_timeout_bounds_and_garbage():
    assert leaf._clamp_timeout(0.1) == leaf.MIN_TIMEOUT_SECONDS
    assert leaf._clamp_timeout(3600.0) == leaf.MAX_TIMEOUT_SECONDS
    assert leaf._clamp_timeout(20.0) == 20.0
    assert leaf._clamp_timeout("garbage") == 20.0
    assert leaf._clamp_timeout(None) == 20.0
    assert leaf._clamp_timeout(math.nan) == 20.0


def test_clamp_tries_bounds_and_garbage():
    assert leaf._clamp_tries(0) == leaf.MIN_TRIES
    assert leaf._clamp_tries(100) == leaf.MAX_TRIES
    assert leaf._clamp_tries(3) == 3
    assert leaf._clamp_tries("garbage") == 3
    assert leaf._clamp_tries(None) == 3
    # inf/-inf are unconvertible: same never-raise garbage path as "abc".
    assert leaf._clamp_tries(float("inf")) == 3
    assert leaf._clamp_tries(float("-inf")) == 3


def test_clamp_max_bytes_bounds_and_garbage():
    assert leaf._clamp_max_bytes(10) == leaf.MIN_MAX_BYTES
    assert leaf._clamp_max_bytes(10**9) == leaf.MAX_MAX_BYTES
    assert leaf._clamp_max_bytes(65536) == 65536
    assert leaf._clamp_max_bytes("garbage") == leaf.DEFAULT_MAX_BYTES
    assert leaf._clamp_max_bytes(None) == leaf.DEFAULT_MAX_BYTES
    # inf/-inf are unconvertible: same never-raise garbage path as "abc".
    assert leaf._clamp_max_bytes(float("inf")) == leaf.DEFAULT_MAX_BYTES
    assert leaf._clamp_max_bytes(float("-inf")) == leaf.DEFAULT_MAX_BYTES


def test_paced_request_honors_clamped_tries_no_infinite_loop(monkeypatch):
    """tries=10**9 must still terminate: clamped to MAX_TRIES attempts."""
    import urllib.error

    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(timeout)
        raise urllib.error.URLError("down")

    monkeypatch.setattr(leaf.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(leaf.time, "sleep", lambda s: None)
    monkeypatch.setattr(leaf, "_pace", lambda host="": None)
    try:
        leaf.paced_request_json("GET", "http://127.0.0.1:9/x", tries=10**9)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError after clamped budget")
    assert len(calls) == leaf.MAX_TRIES
    assert all(leaf.MIN_TIMEOUT_SECONDS <= t <= leaf.MAX_TIMEOUT_SECONDS for t in calls)
