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
| `build_verdict_receipt` / `export_receipt_json` | `modules/workflows/workflow.py:245,262` | Build on verified cycles only (sha256 of patch); `model_dump_json` export alongside the candidate patch. `ScanResult.receipt` carries it. |
| `CycleReceipt` | `modules/workflows/project_workflow.py:214` | Project-cycle receipt: `fixture`, `pre_probe_exit`, `post_probe_exit`, `baseline_regression_exit`, `patched_regression_exit`, `differential_passed`, `property_exit`/`property_passed`, `patch_sha256`, `retained`. On `ProjectCycleReport.receipt`. |
| `build_cycle_receipt` / `export_cycle_receipt_json` | `modules/workflows/project_workflow.py:242,265` | Build on retained cycles only; JSON export alongside the candidate diff. |
| `GuardRationale` | `modules/workflows/project_workflow.py:177` | `guard_id` (which guard fired, 1-128 chars), `reason`, `trigger` (protected path/line/setting, max 500 chars, no probe bytes per LAW 4). Lives on `ReplacementValidation.guard_rationale` and cycle evidence root. |
| `guard_rationale(exc)` / `PatchRejected` | `modules/core/patches.py:29` | `PatchRejected` carries `guard_id` + `trigger`; `guard_rationale()` exports `{guard_id, reason, trigger}` for review. |
| Mutation scripts | `modules/core/checks.py:387,506` | `project_mutation_script(fixture_id)` (exit 0 = all held, 1 = mishandled, 2 = unknown fixture); `project_property_mutation_script(fixture_id)` combined property+mutation run. Seeded (`MUTATION_SEED = 20261029`, `MUTATION_COUNT = 4`); `mutation_fixture_supported()` gates; per-fixture builders `_mutation_node_ids` / `_mutation_php_hosts` / `_mutation_mysql_paths`. |
| Mutation/property gates | `modules/workflows/project_workflow.py:101,131` | `mutation_gate_passed()` / `property_gate_passed()`: fail-closed, `None` evidence passes (no contract) and defers to regression; any non-zero exit fails the retain decision. Evidence on `SnapshotVerification.mutations` / `.properties`. |
| Fast-lane topping fields | `modules/workflows/cve_workflow.py:33,317` | Ranked summaries carry `reach_score`, `reach_evidence`, `queue_evidence` (via `_queue_evidence`), `fixed_versions`, `kev_listed`, `epss_percentile`. Sort tier: `-reach_score`, fix availability, KEV, then id. |

Related: [CLI.md](CLI.md) (flags), [DASHBOARD.md](DASHBOARD.md) (panels/hooks map).
