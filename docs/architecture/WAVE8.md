# Wave 8 additions

Follow-on to [WAVE5.md](WAVE5.md): the KEV/EPSS reach-signal enrichment,
the per-process KEV catalog cache, the property normal-contract gate, the
LOW consistency bundle, and the property response-shape trap.

## Q1 enrichment (`cve_workflow.py:54`, wired in `cve_workflow.py:263`)

`_enrich_reach_signals(summary)` attaches KEV/EPSS likelihood signals to
one OSV summary before `reachability_score` runs (`cve_workflow.py:263-267`):

- Uses the summary's first CVE alias only: at most 1 KEV + 1 EPSS lookup
  per summary. Both lookups are keyless and never-raise; each call is
  additionally wrapped in `try/except` so any failure leaves the fields
  unset (fail-closed: no KEV flag, no EPSS percentile).
- `kev_listed=True` set only when `kev_lookup(first).extra["kev_listed"]`
  is truthy (`cve_workflow.py:71-74`).
- `epss_percentile` set only when the EPSS percentile parses to a float in
  `0.0..1.0` (`cve_workflow.py:81-87`); out-of-range or unparsable values
  leave the field unset.
- No CVE alias returns the summary unchanged. Mutates and returns
  `summary` for call-site convenience.

## Q2 KEV cache (`research.py:357-421`)

`kev_lookup(cve_id)` (`research.py:393`) keeps its Wave 5 record shape
(`source="kev"`, `extra.kev_listed/due_date/ransomware`) and adds a
per-process catalog cache so one fetch serves many ids:

- `_KEV_CACHE: dict[str, dict] | None = None` (`research.py:357`); only a
  successfully parsed catalog populates it.
- `_kev_catalog()` (`research.py:366`) returns the cached index on hit,
  else fetches `KEV_CATALOG_URL` with `max_bytes=MAX_MAX_BYTES`
  (`research.py:374`), indexes by upper-cased `cveID`, stores, and
  returns it. Transport `RuntimeError` and malformed payloads return
  `None` without caching, so the next call retries.
- `_kev_cache_clear()` (`research.py:360`) resets the cache; test helper
  only, production never calls it.
- Never-raises contract unchanged: bad CVE shape, missing catalog, and
  catalog miss all degrade to `None`.

## R1 property checks (`checks.py:109`, gate in `project_workflow.py:95`)

`project_property_script(fixture_id)` (`checks.py:109-143`) builds a
bounded deterministic property script per fixture contract. Exit
contract: 0 = every property held, 1 = a property failed (evidence in
the message), 2 = inconclusive or unknown fixture. Output is bounded:
compact summaries only, never response bodies.

Supported ids (`checks.py:85-95`):

- `node_query_sink` (`checks.py:157`): JSON envelope of
  `targets/node_query_sink/app.js`. Known ids 101/102 stay 200 with one
  result row (`status == ok`); seeded random ids return an empty result
  set (`count == 0`, `results == []`), never the 404 route.
- `project_lookup_text` (`checks.py:176`): plain-text contract of
  project-workflow demo apps. Known ids return exact names
  (`101 -> Alice`, `102 -> Bob`); seeded random ids return an empty 200
  body, never rows or an error page.
- `php_command_sink` (`checks.py:195`): benign hosts `localhost` and
  `127.0.0.1` stay 200 `ok` with a stable diagnostic echo across
  repetition.
- `mysql_config_audit` / `mysql_insecure_conf` (`checks.py:217`):
  audited config keys (`[mysqld] port`, `[mysqld] max_connections`)
  survive idempotent re-read; both registry aliases map to the
  `mysql_config_audit` branch (`checks.py:131-132`).

Gate: `property_gate_passed(verification)` (`project_workflow.py:95-122`)
is fail-closed with a `None`-skips rule: `None` properties (fixture has
no contract, or the check did not run) returns `True` so the existing
regression requirement decides; any recorded properties exit other than
0 returns `False`. Conjoined into the retain verdict
(`project_workflow.py:1289`) and the independent-verification retain
(`project_workflow.py:1299`), so a recorded properties failure vetoes
the retain even when the probe is blocked and regression is green.
Wired in `verify_project_snapshot` (`project_workflow.py:495-509`):
runs the script only when `property_fixture_supported(fixture_id)`
(`checks.py:96`), records it as `properties` on `SnapshotVerification`
(`project_workflow.py:563`).

## R2 LOW bundle

Three small consistency fixes, each fail-first tested:

- `research.py:118-120` (`osv_lookup`) and `research.py:144-146`
  (`circl_lookup`): direct CVE fetches use `max_bytes=MAX_MAX_BYTES`
  like the KEV path, instead of the 1 MiB default cap that large OSV
  records could silently exceed.
- `research.py:323` (`epss_score`): normalizes through
  `sanitize_cve_id` instead of ad-hoc `strip().upper()[:32]`.
- `intel_search.py:130-138` (`osv_lookup_by_cve`): validates CVE shape
  (`sanitize_cve_id` + `fullmatch(CVE-\d{4}-\d{4,7})`) before fetching;
  malformed ids return `None` without touching the network. Companion
  hardening in `cve_workflow.py:234`: `(record or {}).get("affected")`
  so a `None` OSV record degrades to no ranges instead of raising.

## TRAP: property script must match the target's real response shape

A JSON property script run against a plain-text service exits 2 via
`JSONDecodeError`, and the fail-closed gate rolls the cycle back even
though the service is healthy. Live case: `project_scan.py` generated a
plain-text demo app but passed the `node_query_sink` contract id, so the
JSON script (`json.loads` on `"Alice"`) raised inside the script harness
as exit 2, `property_gate_passed` returned `False`, and the live
project_scan rolled back. Fix `09b9635`: split the scripts by real
response shape — `node_query_sink` keeps the JSON envelope branch
(`checks.py:157`), `project_lookup_text` gets its own plain-text branch
(`checks.py:176`), and the contract first line names the fixture id so
the opt-in wiring (`project_workflow.py:497-509`) picks the matching
script. Live proof after the fix: 2/2 retained, properties exit 0.
