# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
# Open-weight verification payload: Muse Spark Open (Bonus 1 / rubric P1-2, 2B +1.0)

## Exact env

```bash
META_MUSE_RED_MODEL=meta-models/muse-spark-open-1026
META_MUSE_BLUE_MODEL=meta-models/muse-spark-open-1026
META_MUSE_BASE_URL=<partner endpoint, Baseten or Modal>
# Baseten example: https://inference.baseten.co/v1
# Modal example:   https://<workspace>--<deployment>.modal.run/v1
```

Partner swap-in only; `api.meta.ai` returns 404 `model_not_found` for
`meta-models/*` IDs. See `docs/guides/DEVELOPMENT.md` ("Open model, optional").

## Expected validation path

`library/core/config.py` `PurpleBoxConfig.validate()`:

1. Base URL: hostname must be `api.meta.ai` or end with `.baseten.co`,
   `.api.baseten.co`, or `.modal.run`; HTTPS, no credentials/query/port.
2. Model IDs: `meta-models/muse-spark-open(?:-[a-z0-9]+)*` fullmatch. This
   accepts both `meta-models/muse-spark-open` and
   `meta-models/muse-spark-open-1026`; anything else under `meta-models/`
   (e.g. `meta-models/llama-4`) is rejected.
3. `library/core/config.py` was READ-ONLY for this change; validation already
   accepted both IDs + Baseten/Modal hostnames.

## Pricing assumption table (USD per 1M tokens)

| model | cached input | input | output | status |
|---|---|---|---|---|
| `meta-models/muse-spark-open` | 0.006 | 0.30 | 0.60 | PROVISIONAL estimate |
| `meta-models/muse-spark-open-1026` | 0.006 | 0.30 | 0.60 | PROVISIONAL estimate |

Assumption: ~3x the `muse-spark-*-contributor` tier (same cheap
hosted-inference order of magnitude). Marked PROVISIONAL in code
(`library/core/pricing.py` comment) pending the partner rate card. Re-baseline
before quoting real runs.

## Mocked-smoke procedure

No credentials needed; the wire is canned with `httpx.MockTransport` (same
pattern as `tests/test_config_agents.py`):

```bash
python3 -m pytest tests/test_config_agents.py -k "spark_open" -q
```

Covers: (a) config validates on a Baseten URL, (b) cost lookup for both model
IDs returns finite USD, (c) `run_red_team_analysis` with the spark-open model
id sends `body["model"] == "meta-models/muse-spark-open-1026"` and parses back
a `RedTeamFinding`.

## Partner verification (live)

1. Set the three env vars above with the real endpoint + partner key.
2. Send one `POST {base_url}/chat/completions` with `"model":
   "meta-models/muse-spark-open-1026"`; keep the receipt fields: HTTP status,
   `usage.prompt_tokens`, `usage.completion_tokens`, `finish_reason`.
3. Run the scan; confirm the red-team round trip parses and
   `ScanUsage.cost_usd` is finite (provisional rates apply).

**Live-partner run: PENDING** (needs partner credentials; static + mocked proof
only as of this doc).

## Conflicting test note

`tests/test_pricing.py:29` asserted `estimate_cost("meta-models/muse-spark-open-1026",
...) is None`. That assertion encodes the pre-fix unpriced state and FAILS after
this change adds the provisional entry. It belongs to the read-only checkout
scope of the pricing test file (out of scope here: this task owns only
`pricing.py`, `test_config_agents.py`, `docs/OPEN_WEIGHT.md`). Flag for the
pricing-file owner: update line 29 to assert the provisional finite value.
