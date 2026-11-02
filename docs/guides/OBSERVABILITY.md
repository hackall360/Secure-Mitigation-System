# Observability (dev/prod modes)

Dev/prod observability for the scan loop: per-aspect JSONL logs, metrics,
and traces. Owned by `library/shared/sms_observability.py` (stdlib only).

## Mode switch

| Source | Values | Default |
|---|---|---|
| `--observability-mode {dev,prod}` | dev or prod | prod |
| `PURPLEBOX_OBSERVABILITY_MODE` | dev or prod | prod (when the flag is absent) |

Explicit flag wins over the env var; anything else raises `ValueError`
(fail-closed to prod: less output, less surface).

## Layout

```
logs/<signal>/<aspect>.jsonl
```

- Signals: `logs`, `metrics`, `traces`.
- Aspects (dots separate area from surface): `workflows.fixture`,
  `intel.research`, `intel.cve`, `intel.scanners`, `services.api`,
  `services.mcp`, `services.telemetry`, ...
- One JSON object per line, plus a per-run `logs/metrics/_summary.json`.

## Record schemas

Log line: `ts`, `aspect`, `event`, `mode`, `message`, optional `fields`.
Metric line: `ts`, `aspect`, `event`, `mode`, `value`, `unit`.
Trace line: `ts`, `aspect`, `event`, `mode`, `trace_id`, `span_id`,
`duration_ms`, `status` (`ok` or `error` with an `error` object), on
success AND error paths.

## The 10x rule

`prod` records milestones (scan start/verdict, errors, trace open/close).
`dev` additionally emits ~10 detail records per milestone (phase
transitions, payload sizes, durations, decisions) — roughly 10x the
records on the same run. Metrics and traces keep identical cardinality
across modes (comparable measurements; richness, not count, differs).

## LAW 4 redaction note

Values that look like secrets (`api_key`, `*token*`, `*secret*`,
`*password*`, `sk-`/`sk_`-prefixed strings) are replaced with `REDACTED`
before they touch disk. Intel is untrusted grounding: log COUNTS returned
and source names, never intel text verbatim.

## Ingestion hint

One JSON object per line, fixed keys — ingest with `jq -s` or pandas:

```bash
jq -s 'group_by(.event) | map({event: .[0].event, n: length})' logs/logs/intel.research.jsonl
```

```python
import pandas as pd

logs = pd.read_json("logs/logs/intel.research.jsonl", lines=True)
logs.groupby("event").size()
```
