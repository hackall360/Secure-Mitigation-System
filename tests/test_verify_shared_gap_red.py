# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first gap tests for library/shared/ (P4 verification sweep).

Targets the lowest-coverage shared functions measured with
`.jcode/tools/verify_cov.py` over the pre-existing shared tests
(test_sms_leaves, test_compression, test_transport_bounds_red,
test_observability_modes_red, test_compress_hud_red,
test_sms_history_redact). Baseline (<100% line-covered):
sms_async 36.8%, sms_http 75.3%, sms_text 78.9%, sms_compress 86.7%,
sms_scan_parse 91.8%, sms_observability 95.2%.
sms_budget/sms_redact/sms_records were already 100%: no tests here.

LAW 9 RED-first: written from a reading of the code, BEFORE running.
First run must FAIL for a functional reason. Failures caused by a wrong
expectation in THIS file are fixed here, never in library/. If a test
exposes a REAL library bug, stop and report [FT] with a trace.
"""

import asyncio
import json
import threading
import time
import urllib.parse
from urllib.error import HTTPError

import pytest

import modules.shared.sms_async as sms_async
import modules.shared.sms_compress as comp
import modules.shared.sms_http as http
import modules.shared.sms_observability as obs
import modules.shared.sms_scan_parse as scan
import modules.shared.sms_text as text


class _FakeResp:
    """Minimal urlopen context manager returning canned JSON bytes."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self, n=-1):
        if n is None or n < 0:
            return self._payload
        return self._payload[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --- sms_text gaps: bounded passthrough (line 18), take_utf8_prefix
# --- exact-fit (29), non-positive budget (26), too-small budget (34).


def test_bounded_passthrough_when_within_limit():
    assert text.bounded("abc", 10) == "abc"
    assert text.bounded("1234567890", 10) == "1234567890"
    assert text.bounded("", 5) == ""


def test_take_utf8_prefix_exact_fit_returns_empty_rest():
    assert text.take_utf8_prefix("hello", 5) == ("hello", "")
    assert text.take_utf8_prefix("abc😀def", 3) == ("abc", "😀def")


def test_take_utf8_prefix_rejects_nonpositive_budget():
    with pytest.raises(ValueError):
        text.take_utf8_prefix("abc", 0)
    with pytest.raises(ValueError):
        text.take_utf8_prefix("abc", -2)


def test_take_utf8_prefix_mid_character_split_and_too_small():
    assert text.take_utf8_prefix("aé", 2) == ("a", "é")
    with pytest.raises(ValueError):
        text.take_utf8_prefix("😀", 1)


# --- sms_scan_parse gaps: vendor_map non-dict (57), any-vendor
# --- fallback (64), cvss_best non-dict skip (72), bad-score skip (80).


def test_vendor_map_non_dict_is_empty():
    assert scan.cvss_from_vendor_map(None) == ""
    assert scan.cvss_from_vendor_map([("nvd", {"V3Score": 9.8})]) == ""
    assert scan.cvss_from_vendor_map("nvd") == ""


def test_vendor_map_falls_back_to_any_vendor():
    assert scan.cvss_from_vendor_map({"other": {"V3Score": 8.0}}) == "8.0"
    assert (
        scan.cvss_from_vendor_map({"nvd": {"V2Score": None}, "other": {"V3Score": 8.0}})
        == "8.0"
    )
    assert scan.cvss_from_vendor_map({"nvd": "junk", "other": {"V3Score": 8.0}}) == "8.0"


def test_cvss_best_skips_non_dict_entries():
    assert scan.cvss_best([None, "junk", 42, {"metrics": {"baseScore": 4.5}}]) == "4.5"
    assert scan.cvss_best(None) == ""
    assert scan.cvss_best([]) == ""


def test_cvss_best_skips_unparseable_scores():
    # Contract (read from code): the FIRST non-None score is kept verbatim
    # (`if not best or ...` short-circuits, no float comparison on first
    # hit); unparseable LATER scores are skipped (float raises -> continue).
    assert scan.cvss_best([{"metrics": {"baseScore": "high"}}]) == "high"
    assert (
        scan.cvss_best([{"metrics": {"baseScore": 6.0}}, {"metrics": {"baseScore": "high"}}])
        == "6.0"
    )
    assert scan.cvss_best([{"metrics": None}, {"metrics": {"baseScore": 6.0}}]) == "6.0"


# --- sms_http gaps: _parse_retry_after (59-64), _backoff_seconds
# --- (69-73), _retry_after_of 429 path (80-83), _host_of (88-91),
# --- _pace (125-129), request build/success/cap (162-172),
# --- get/post wrappers (190-191, 205-213).


def test_parse_retry_after_shapes():
    assert http._parse_retry_after(None) is None
    assert http._parse_retry_after("") is None
    assert http._parse_retry_after("30") == 30.0
    assert http._parse_retry_after("  2.5 ") == 2.5
    assert http._parse_retry_after("-4") == 0.0
    assert http._parse_retry_after("soon") is None


def test_backoff_seconds_range_and_caps():
    for _ in range(25):
        assert 1.0 <= http._backoff_seconds(0) <= 2.0
        assert 30.0 <= http._backoff_seconds(99) <= 31.0
        assert 60.0 <= http._backoff_seconds(0, retry_after=10_000.0) <= 61.0
        assert 0.0 <= http._backoff_seconds(0, retry_after=-9.0) <= 1.0


def test_retry_after_of_429_vs_others():
    err429 = HTTPError("http://h/x", 429, "Too Many", {"Retry-After": "7"}, None)
    assert http._retry_after_of(err429) == 7.0
    bare = HTTPError("http://h/x", 429, "Too Many", {}, None)
    assert http._retry_after_of(bare) is None
    err500 = HTTPError("http://h/x", 500, "Boom", {"Retry-After": "7"}, None)
    assert http._retry_after_of(err500) is None
    assert http._retry_after_of(ValueError("nope")) is None


def test_host_of_lowercases_and_empty_on_garbage():
    assert http._host_of("HTTPS://Example.COM:8443/p?q=1") == "example.com:8443"
    assert http._host_of("http://[::1") == ""
    assert http._host_of("") == ""


def test_pace_records_host_without_initial_sleep():
    saved = dict(http._last_calls)
    host = "gap-first-hit-host"
    http._last_calls.pop(host, None)
    try:
        before = time.monotonic()
        http._pace(host)
        assert time.monotonic() - before < 1.0
        assert host in http._last_calls
    finally:
        http._last_calls.clear()
        http._last_calls.update(saved)


def test_pace_second_call_waits_out_gap():
    saved = dict(http._last_calls)
    host = "gap-pace-host-example"
    http._last_calls.pop(host, None)
    try:
        http._pace(host)
        assert host in http._last_calls
        before = time.monotonic()
        http._pace(host)
        assert time.monotonic() - before >= 0.9
        assert host in http._last_calls
    finally:
        http._last_calls.clear()
        http._last_calls.update(saved)


def test_paced_request_success_returns_parsed_json(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["req"] = request
        seen["timeout"] = timeout
        return _FakeResp(b'{"ok": true}')

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(http, "_pace", lambda host="": None)
    out = http.paced_request_json("GET", "http://127.0.0.1:9/x", tries=1)
    assert out == {"ok": True}
    assert seen["req"].get_method() == "GET"
    assert seen["req"].full_url == "http://127.0.0.1:9/x"
    assert 1.0 <= seen["timeout"] <= 60.0


def test_paced_request_posts_json_body_with_headers(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["req"] = request
        return _FakeResp(b"[1, 2]")

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(http, "_pace", lambda host="": None)
    out = http.paced_request_json(
        "POST", "http://127.0.0.1:9/x", body={"k": "v"}, headers={"X-Test": "1"}, tries=1
    )
    assert out == [1, 2]
    req = seen["req"]
    assert req.get_method() == "POST"
    assert json.loads(req.data.decode("utf-8")) == {"k": "v"}
    hdrs = {k.lower(): v for k, v in req.header_items()}
    assert hdrs["content-type"] == "application/json"
    assert hdrs["x-test"] == "1"


def test_paced_request_oversize_body_is_runtime_error(monkeypatch):
    monkeypatch.setattr(
        http.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp(b"x" * 2000)
    )
    monkeypatch.setattr(http, "_pace", lambda host="": None)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="intel request failed"):
        http.paced_request_json("GET", "http://127.0.0.1:9/x", tries=1, max_bytes=1024)


def test_paced_request_malformed_url_is_runtime_error(monkeypatch):
    monkeypatch.setattr(http, "_pace", lambda host="": None)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="intel request failed"):
        http.paced_request_json("GET", "notaurl", tries=1)


def test_paced_get_encodes_query_params(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["req"] = request
        return _FakeResp(b'{"r": 1}')

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(http, "_pace", lambda host="": None)
    params = {"q": "a b", "tag": "x/y"}
    out = http.paced_get_json("http://127.0.0.1:9/s", params=params, tries=1)
    assert out == {"r": 1}
    assert seen["req"].full_url == "http://127.0.0.1:9/s?" + urllib.parse.urlencode(params)


def test_paced_post_sends_payload(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["req"] = request
        return _FakeResp(b'{"saved": true}')

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(http, "_pace", lambda host="": None)
    out = http.paced_post_json("http://127.0.0.1:9/submit", {"a": 1}, tries=1)
    assert out == {"saved": True}
    assert seen["req"].get_method() == "POST"
    assert json.loads(seen["req"].data.decode("utf-8")) == {"a": 1}


# --- sms_compress gaps: blank-line filler (89), corrupt dict load
# --- (162), eviction (172-173), fold_marker (176-177), save failure
# --- (188), dict fold on repeat (230), all-filler fallback (238),
# --- fast-path record (248), head-skip budget branch (274-275),
# --- budget-path record (318).


def test_blank_lines_are_filler_and_drop():
    report = comp.compress_context("const a = 1;\n\nconst b = 2;\n", filename="a.js")
    assert "\n\n" not in report.compressed_text
    assert "const a = 1;" in report.compressed_text
    assert "const b = 2;" in report.compressed_text


def test_dictionary_fold_marker_for_known_repeats(tmp_path):
    store = comp.DictionaryStore(path=tmp_path / "d.json")
    store.record(filename="a.js", seen_lines=["const a = 1;"])
    src = "const a = 1;\nconst a = 1;\nconst b = 2;\nconst c = 3;\n"
    report = comp.compress_context(src, filename="a.js", dictionary=store)
    assert "[... seen 1x in prior cycles: const a = 1; ...]" in report.compressed_text
    assert store.known("const b = 2;")


def test_dictionary_evicts_oldest_past_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(comp, "DICTIONARY_MAX_LINES", 3)
    store = comp.DictionaryStore(path=tmp_path / "d.json")
    store.record(filename="a.py", seen_lines=["l0", "l1", "l2", "l3", "l4"])
    assert set(store._lines) == {"l2", "l3", "l4"}


def test_dictionary_corrupt_file_loads_empty(tmp_path):
    path = tmp_path / "d.json"
    path.write_text("### not json ###", encoding="utf-8")
    store = comp.DictionaryStore(path=path)
    assert not store.known("anything")


def test_dictionary_save_failure_never_raises(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not dir", encoding="utf-8")
    store = comp.DictionaryStore(path=blocker / "d.json")
    store.record(filename="a.py", seen_lines=["x"])
    store.save()
    assert not (blocker / "d.json").exists()


def test_all_filler_source_keeps_first_line():
    report = comp.compress_context("// filler line one\n// filler line two\n", filename="a.js")
    assert report.compressed_text == "// filler line one\n"
    assert report.tokens_saved > 0


def test_budget_head_skip_drops_filler_keeps_sink():
    critical = "const queryExpression = eval(rawUserId);"
    filler = "".join(f"const filler_{i:04d} = {i};\n" for i in range(300))
    report = comp.compress_context(filler + critical + "\n", filename="a.js", max_tokens=12)
    assert report.compressed_tokens <= 12
    assert critical in report.compressed_text
    assert "filler_" not in report.compressed_text


def test_budget_path_records_dictionary(tmp_path):
    store = comp.DictionaryStore(path=tmp_path / "d.json")
    big = "".join(f"const line_{i:04d} = {i};\n" for i in range(2000))
    big += "const queryExpression = eval(rawUserId);\n"
    report = comp.compress_context(big, filename="a.js", max_tokens=200, dictionary=store)
    assert report.compressed_tokens <= 200
    assert "const queryExpression = eval(rawUserId);" in report.compressed_text
    assert store.known("const line_0000 = 0;")


# --- sms_async gaps: blocking result/error/cancel-join (23-31),
# --- make_log passthrough/swallow (37-43).


async def test_blocking_returns_thread_result():
    assert await sms_async.blocking(lambda x, y=0: x + y, 2, y=3) == 5


async def test_blocking_propagates_worker_error():
    def boom():
        raise RuntimeError("worker blew up")

    with pytest.raises(RuntimeError, match="worker blew up"):
        await sms_async.blocking(boom)


async def test_blocking_joins_inflight_work_on_cancel():
    started = threading.Event()
    finished = []

    def slow():
        started.set()
        time.sleep(0.2)
        finished.append(True)
        return 7

    outer = asyncio.create_task(sms_async.blocking(slow))
    while not started.is_set():
        await asyncio.sleep(0.01)
    outer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await outer
    assert finished == [True]


async def test_make_log_passes_through():
    calls = []

    async def emit(team, message):
        calls.append((team, message))

    log = sms_async.make_log(emit)
    assert await log("red", "hello") is None
    assert calls == [("red", "hello")]


async def test_make_log_swallows_emit_failures():
    async def broken(team, message):
        raise RuntimeError("socket closed")

    assert await sms_async.make_log(broken)("x", "y") is None


# --- sms_observability gaps: bad env (56), shutdown no-init (77),
# --- sk- redact (99/112), append no-init (120), bad aspect (136).


def test_resolve_mode_rejects_bad_env(monkeypatch):
    monkeypatch.setenv(obs.ENV_VAR, "verbose")
    with pytest.raises(ValueError):
        obs.resolve_mode(None)
    monkeypatch.delenv(obs.ENV_VAR, raising=False)
    assert obs.resolve_mode(None) == "prod"


def test_shutdown_without_init_is_noop():
    saved = {
        "root": obs._state["root"],
        "mode": obs._state["mode"],
        "metrics": list(obs._state["metrics"]),
    }
    obs._state["root"] = None
    try:
        assert obs.shutdown() is None
    finally:
        obs._state.update(saved)


def test_redact_withholds_sk_prefixed_strings():
    assert obs._redact("sk-ant-secret-value-123") == "REDACTED"
    assert obs._redact({"api_key": "whatever", "nested": ["sk-live-abcdef1234"]}) == {
        "api_key": "REDACTED",
        "nested": ["REDACTED"],
    }
    assert obs._redact({"ok": 1, "note": "short"}) == {"ok": 1, "note": "short"}
    assert obs._redact("sk-x") == "sk-x"


def test_append_without_init_writes_nothing():
    saved = {
        "root": obs._state["root"],
        "mode": obs._state["mode"],
        "metrics": list(obs._state["metrics"]),
    }
    obs._state["root"] = None
    try:
        assert obs._append("logs", "gap.probe", {"event": "x"}) is None
    finally:
        obs._state.update(saved)


def test_get_aspect_rejects_non_identifiers():
    with pytest.raises(ValueError):
        obs.get_aspect("")
    with pytest.raises(ValueError):
        obs.get_aspect("has space")


async def test_blocking_swallows_worker_error_on_cancel():
    """sms_async:30 — cancelled outer + failing worker: `except Exception: pass` runs."""
    started = threading.Event()

    def failing():
        started.set()
        time.sleep(0.2)
        raise RuntimeError("late worker failure")

    outer = asyncio.create_task(sms_async.blocking(failing))
    while not started.is_set():
        await asyncio.sleep(0.01)
    outer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await outer


def test_retry_after_of_swallows_broken_headers():
    """sms_http:83 — headers.get raising degrades to None, never raises."""

    class BadHeaders:
        def get(self, key, default=None):
            raise RuntimeError("headers broken")

    err = HTTPError("http://h/x", 429, "Too Many", BadHeaders(), None)
    assert http._retry_after_of(err) is None


def test_dictionary_save_chmod_failure_still_persists(monkeypatch, tmp_path):
    """sms_compress:186 — chmod OSError is swallowed, data still written."""
    path = tmp_path / "sub" / "d.json"
    store = comp.DictionaryStore(path=path)
    store.record(filename="a.py", seen_lines=["kept"])
    real_chmod = type(path).chmod

    def bad_chmod(self, *args, **kwargs):
        raise OSError("perms locked")

    monkeypatch.setattr(type(path), "chmod", bad_chmod)
    try:
        store.save()
    finally:
        monkeypatch.setattr(type(path), "chmod", real_chmod)
    assert json.loads(path.read_text(encoding="utf-8")) == {"kept": 1}
