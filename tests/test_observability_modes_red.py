# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): dev/prod observability modes — logs, metrics, traces.

Contract (brief 2026-11-02-observability-lmt):
- `library/shared/sms_observability.py` owns mode + per-aspect JSONL sinks.
- Mode from `PURPLEBOX_OBSERVABILITY_MODE` (dev|prod, default prod) with a
  `mode` override at init; dev emits ~10x the records of prod on the same
  scripted sequence.
- Layout: `logs/<signal>/<aspect>.jsonl` (signals: logs, metrics, traces;
  aspect like `workflows.fixture`), one JSON object per line with fixed keys
  (ts, aspect, event, mode + signal payload). Plus a per-run
  `logs/metrics/_summary.json`.
- Traces carry trace_id/span_id/duration_ms/status on success AND error paths.
- LAW 4: secrets never land in files (a passed api-key-looking value is
  redacted, never verbatim).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _load():
    from library.shared import sms_observability as O

    return O


def test_module_contract_shapes():
    O = _load()
    assert O.SIGNALS == ("logs", "metrics", "traces")
    assert O.DEFAULT_MODE == "prod"
    for name in ("init", "get_aspect", "shutdown", "record_metric", "trace", "log"):
        assert callable(getattr(O, name)), name


def test_mode_from_env_with_prod_default(monkeypatch):
    O = _load()
    monkeypatch.delenv("PURPLEBOX_OBSERVABILITY_MODE", raising=False)
    assert O.resolve_mode(None) == "prod"
    monkeypatch.setenv("PURPLEBOX_OBSERVABILITY_MODE", "dev")
    assert O.resolve_mode(None) == "dev"
    assert O.resolve_mode("prod") == "prod"
    with pytest.raises(ValueError):
        O.resolve_mode("verbose")


def test_dev_is_ten_times_prod_on_same_sequence(tmp_path):
    O = _load()
    scripted = [
        ("scan_start", {"target": "node_query_sink"}),
        ("baseline", {"exit_code": 1}),
        ("probe_built", {"bytes": 512}),
        ("probe_exit", {"exit_code": 0}),
        ("patch_written", {"lines": 4}),
        ("reprobe_exit", {"exit_code": 1}),
        ("verdict", {"status": "verified"}),
    ]
    for mode in ("prod", "dev"):
        root = tmp_path / mode
        O.init(root=root, mode=mode)
        try:
            aspect = O.get_aspect("workflows.fixture")
            with O.trace(aspect, "scan") as span:
                for event, fields in scripted:
                    O.log(aspect, event, message=f"{event} happened", **fields)
                    O.record_metric(aspect, f"{event}.count", 1, unit="count")
            assert span.trace_id and span.span_id and span.status == "ok"
        finally:
            O.shutdown()
        logs = list((root / "logs" / "workflows.fixture.jsonl").read_text().splitlines())
        assert logs, f"no log lines in {mode}"
        for line in logs:
            record = json.loads(line)
            assert {"ts", "aspect", "event", "mode", "message"} <= set(record), record
            assert record["mode"] == mode
        metrics = list((root / "metrics" / "workflows.fixture.jsonl").read_text().splitlines())
        assert metrics, f"no metric lines in {mode}"
        traces = list((root / "traces" / "workflows.fixture.jsonl").read_text().splitlines())
        assert traces, f"no trace lines in {mode}"
        trace = json.loads(traces[0])
        assert trace["trace_id"] and trace["span_id"]
        assert trace["duration_ms"] >= 0 and trace["status"] == "ok"
    summary = json.loads((tmp_path / "dev" / "metrics" / "_summary.json").read_text())
    assert summary["mode"] == "dev" and summary["metrics"]
    # Verbosity lives in logs: dev emits the milestone + ~10 detail records.
    # Metrics/traces keep identical cardinality across modes (comparable
    # measurements; richness, not count, differs).
    dev_logs = list((tmp_path / "dev" / "logs" / "workflows.fixture.jsonl").read_text().splitlines())
    prod_logs = list((tmp_path / "prod" / "logs" / "workflows.fixture.jsonl").read_text().splitlines())
    assert len(dev_logs) >= 10 * len(prod_logs), f"dev {len(dev_logs)} vs prod {len(prod_logs)}"
    for signal in ("metrics", "traces"):
        dev_n = len(list((tmp_path / "dev" / signal / "workflows.fixture.jsonl").read_text().splitlines()))
        prod_n = len(list((tmp_path / "prod" / signal / "workflows.fixture.jsonl").read_text().splitlines()))
        assert dev_n == prod_n == len(scripted) if signal == "metrics" else dev_n == prod_n == 1


def test_error_trace_marks_fail_with_type(tmp_path):
    O = _load()
    O.init(root=tmp_path, mode="dev")
    try:
        aspect = O.get_aspect("core.docker")
        with pytest.raises(RuntimeError):
            with O.trace(aspect, "container_run"):
                raise RuntimeError("boom")
        trace = json.loads((tmp_path / "traces" / "core.docker.jsonl").read_text().splitlines()[-1])
        assert trace["status"] in ("error", "fail")
        assert trace.get("error", {}).get("type") == "RuntimeError"
    finally:
        O.shutdown()


def test_secrets_redacted_never_verbatim(tmp_path):
    O = _load()
    O.init(root=tmp_path, mode="dev")
    try:
        aspect = O.get_aspect("core.agents")
        secret = "sk-live-abcdefghijklmnopqrstuvwx"
        O.log(aspect, "call", message="model call", api_key=secret, model="muse-spark-1.3")
        line = (tmp_path / "logs" / "core.agents.jsonl").read_text()
        assert secret not in line
        assert "REDACTED" in line
    finally:
        O.shutdown()


def test_per_aspect_files_not_giant_blobs(tmp_path):
    O = _load()
    O.init(root=tmp_path, mode="dev")
    try:
        for aspect_name in ("workflows.fixture", "core.docker", "intel.osv"):
            aspect = O.get_aspect(aspect_name)
            O.log(aspect, "ping", message="ping")
        for aspect_name in ("workflows.fixture", "core.docker", "intel.osv"):
            assert (tmp_path / "logs" / f"{aspect_name}.jsonl").exists(), aspect_name
        assert not (tmp_path / "logs" / "all.jsonl").exists()
        assert not (tmp_path / "logs.jsonl").exists()
    finally:
        O.shutdown()
