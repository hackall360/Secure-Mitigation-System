# Module index

One-line roles for every `sms_*` leaf plus the TUI, CLI presenter, dashboard
layers, and test helpers. See [architecture/REPOSITORY.md](../architecture/REPOSITORY.md)
for the repo map and [guides/DEVELOPMENT.md](../guides/DEVELOPMENT.md) for setup.

## Shared leaves (`sms_*`)

| Module | Role |
|---|---|
| `sms_async.py` | Shared async + emit plumbing: joins in-flight Docker/thread work before propagating results. |
| `sms_budget.py` | Shared payload budgeting: JSON size checks against explicit context budgets. |
| `sms_http.py` | Shared paced HTTP+JSON leaf: one backoff/cap discipline for every keyless intel call. |
| `sms_records.py` | Shared record shaping: CVE-id normalization, summary caps, dict export. |
| `sms_redact.py` | Shared redaction for user-facing reports: dict-level, no model imports (LAW 4). |
| `sms_scan_parse.py` | Shared scanner-field shaping: CVSS picks, CWE lists, reference lists. |
| `sms_text.py` | Shared text bounding: char-limit cuts with omission notes, UTF-8 prefixes. |

## Presentation

| Module | Role |
|---|---|
| `sms_cli.py` | Non-interactive CLI presentation: ANSI colors, stderr spinner, fact/usage tables. |
| `tui.py` | Terminal UI (80x24, stdlib + curses only): read-only view over `main`/`workflow`. |

## Dashboard layers

| File | Role |
|---|---|
| `static/fx.js` | Motion layer: cursor glow + parallax vars, stage data-flow pulses (WAAPI only, CSP-safe). |
| `static/panels.js` | Scan-timeline markers fed by `writeLine(team, msg)` in `static/app.js` (max 100). |

## Test support

| Module | Role |
|---|---|
| `tests/helpers.py` | Consolidated unit-test doubles for fixture and project workflow tests. |

## Wave 2 (SPEC 14.8) surfaces

| Symbol | Location | Fields / role |
|---|---|---|
| `VerdictReceipt` | `modules/workflows/workflow.py:218` | Fixture-loop receipt: `fixture`, `pre_exit_code`, `post_exit_code`, `regression_passed`, `differential_passed`, `property_exit_code`/`property_passed` (None: fixture loop has no properties), `patch_sha256`, `verified`. Records only, never upgrades a verdict. |
| `build_verdict_receipt` / `export_receipt_json` | `modules/workflows/workflow.py:238,262` | Build on verified cycles only (sha256 of patch); `model_dump_json` export alongside the candidate patch. `ScanResult.receipt` carries it. |
| `CycleReceipt` | `modules/workflows/project_workflow.py:263` | Project-cycle receipt: `fixture`, `pre_probe_exit`, `post_probe_exit`, `baseline_regression_exit`, `patched_regression_exit`, `differential_passed`, `property_exit`/`property_passed`, `patch_sha256`, `retained`. On `ProjectCycleReport.receipt`. |
| `build_cycle_receipt` / `export_cycle_receipt_json` | `modules/workflows/project_workflow.py:285,320` | Build on retained cycles only; JSON export alongside the candidate diff. |
| `GuardRationale` | `modules/workflows/project_workflow.py:207` | `guard_id` (which guard fired, 1-128 chars), `reason`, `trigger` (protected path/line/setting, max 500 chars, no probe bytes per LAW 4). Lives on `ReplacementValidation.guard_rationale` and cycle evidence root. |
| `guard_rationale(exc)` / `PatchRejected` | `modules/core/patches.py:57` | `PatchRejected` carries `guard_id` + `trigger`; `guard_rationale()` exports `{guard_id, reason, trigger}` for review. |
| Mutation scripts | `modules/core/checks.py:423,543` | `project_mutation_script(fixture_id)` (exit 0 = all held, 1 = mishandled, 2 = unknown fixture); `project_property_mutation_script(fixture_id)` combined property+mutation run. Seeded (`MUTATION_SEED = 20261029`, `MUTATION_COUNT = 4`); `mutation_fixture_supported()` gates; per-fixture builders `_mutation_node_ids` / `_mutation_php_hosts` / `_mutation_mysql_paths`. |
| Mutation/property gates | `modules/workflows/project_workflow.py:102,131` | `mutation_gate_passed()` / `property_gate_passed()`: fail-closed, `None` evidence passes (no contract) and defers to regression; any non-zero exit fails the retain decision. Evidence on `SnapshotVerification.mutations` / `.properties`. |
| Fast-lane topping fields | `modules/workflows/cve_workflow.py:31,135,417` | Ranked summaries carry `reach_score`, `reach_evidence`, `queue_evidence` (via `_queue_evidence`), `fixed_versions`, `kev_listed`, `epss_percentile`. Sort tier: `-reach_score`, fix availability, KEV, then id. |

## Wave 5 (SPEC 14.9) surfaces

| Symbol | Location | Fields / role |
|---|---|---|
| `_source_fresh` | `modules/workflows/cve_workflow.py:66` | Freshness gate for `queue_evidence`: true unless a stamped ISO date proves the signal older than `_SOURCE_FRESH_DAYS = 1`; missing/unparseable/future dates count as fresh (fetched live inline). Applied to `kev_date` / `epss_date` in `_queue_evidence` (`cve_workflow.py:118,126`); stamps set in `_enrich_reach_signals` (`cve_workflow.py:204,220`). |
| `FAST_LANE_EXCLUDED_SOURCES` / `assert_fast_lane_source_allowed` | `modules/workflows/cve_workflow.py:39,42` | `frozenset({"euvd"})`; fail-closed assert at each fast-lane consultation site (`kev`/`epss` calls) — raises `AssertionError` on excluded sources, returns `True` otherwise so allowed sources never block the scan. |
| `FROZEN_MUTATION_POOL_SHA256` / `mutation_pool_snapshot` / `_assert_frozen_pool` | `modules/core/checks.py:267,286,295` | Frozen digest of the canonical per-contract mutation-id pools; snapshot keyed by fixture; asserted byte-identical at both mutation-script entry points (`modules/core/checks.py:438,560`). Drift raises `ValueError` fail-closed. |
| `EDIT_BUDGET_LINES` / `is_solver_synthesized_shape` | `modules/core/patches.py:10,27` | 60-line surgical edit budget (unchanged); solver-shape detector over `_SOLVER_SHAPE_MARKERS` rejects SemFix/DirectFix-style patches (`guard_id="solver_synthesized_shape"`, `modules/core/patches.py:89`) while template-shaped sanitization flows through the existing guards (`edit_budget_exceeded` at `modules/core/patches.py:111`). |

Related: [CLI.md](CLI.md) (flags), [DASHBOARD.md](DASHBOARD.md) (panels/hooks map).
