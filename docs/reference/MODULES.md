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

Related: [CLI.md](CLI.md) (flags), [DASHBOARD.md](DASHBOARD.md) (panels/hooks map).
