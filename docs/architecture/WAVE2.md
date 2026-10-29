# Wave 2 additions

Follow-on to [PROJECT_WORKFLOW.md](PROJECT_WORKFLOW.md): reachability scoring,
the CVE fast lane, project ghost-probe liveness, the Greenhouse demo flow,
and the honest surface gaps that remain.

## Reachability score (`deep_scan.py:290`, wired in `cve_workflow.py:224`)

`reachability_score(summary, static_findings)` is a deterministic pure
function (no network, no inference) fusing OSV fixed-version ranges with
static sink adjacency into a 0-100 score:

- base +10 when the summary identifies a record (`cves` non-empty or `id`
  present); otherwise `no record identity (+0)` (`deep_scan.py:290-310`).
- +40 when `fixed_versions` is non-empty (a patched range exists to reach);
  otherwise `no fixed version recorded (+0)`.
- +40 when any static finding's CWE matches a CWE implied by the summary.
  Implied CWEs come from `summary.get("cwe")` (str or list) plus `CWE-\d+`
  strings in the `summary`/`details` text (`_CWE_RE`, `deep_scan.py:288`).
  Empty findings or no match record `(+0)` with the reason named.
- capped at 100: `return min(score, 100)` (`deep_scan.py:355`).
  Each evidence entry is bounded to 160 chars.

Fail-closed evidence: every branch appends a presence-or-absence string, so
a low score always explains which signals were missing. `execute_cve_scan`
attaches `reach_score`/`reach_evidence` per summary and never raises on a
scoring failure: `except Exception` falls back to `0` plus
`["scoring unavailable"]` (`cve_workflow.py:224-231`).

## CVE fast lane (`cve_workflow.py:62-81`, CLI `main.py:1136`)

`fast_lane` is an opt-in disclosure fast lane with the same report shape:

- forces `include_deep_assessment=False` and `include_nvd=False`
  (`cve_workflow.py:78-80`); no Muse credit is spent and NVD enrichment
  is skipped even if requested.
- caps `max_osv_details` to `min(given, 10)` (`cve_workflow.py:81`), so
  the OSV detail fan-out stays bounded.
- sorts vulnerabilities by id (`cve_workflow.py:233-234`) for
  deterministic disclosure order.
- prefixes the status message with `Fast lane: ` (`cve_workflow.py:239-240`).

CLI: `--fast-lane` (`main.py:1136-1138`) flows into `execute_cve_scan(
..., fast_lane=args.fast_lane)` on the project CVE path
(`main.py:1464-1467`). It is request-scoped: the flag is per-invocation,
not a persisted config default (`main.py:1240`).

## Ghost-probe liveness (`project_workflow.py:410`, fixture `workflow.py:399`)

Project verification runs post-probe liveness against the same still-running
target. In `DockerProjectSandbox.verify_project_snapshot`
(`project_workflow.py:410-506`):

- baseline regression runs first; a failed baseline returns probe
  `exit_code=2` without running the probe (`project_workflow.py:449-453`).
- when the probe returns exit code 1 (blocked) or 2 (inconclusive), the
  sandbox re-runs the unchanged regression command inside the same
  still-running target via `exec_run`, falling back to a fresh
  `run_project_check` (`project_workflow.py:462-497`). Exit 0 (reachable)
  needs no liveness override.
- a non-zero post-probe result overrides `regression_ev` with a
  `Post-probe regression failed` prefix (`project_workflow.py:498-505`),
  so a crashed or deadlocked service triggers rollback instead of earning
  success for a blocked probe.

The fixture path already had this shape: `workflow.py:399-404` runs
`final_health` (`run_isolated_verifier` with the normal-behavior script)
after a blocked post-patch probe and rejects the patch when its exit is
non-zero. The project addition mirrors that gate for snapshot targets.

## Greenhouse demo flow (dashboard -> WS -> `generate_demo_project`)

Dashboard inputs (`static/index.html:79-81`): `demo-size` select
(standard/small), `demo-flaw-count` number (1-8, empty keeps all),
`demo-seed` number (empty means random). `static/app.js:952-961`
clamps flaw count to 1-8 via `Math.max(1, Math.min(8, ...))` and truncates
the seed to an integer before sending `demo_size`/`flaw_count`/`seed`
over the `/ws/demo` socket (`static/app.js:942`).

Server WS intake (`main.py:449-461`): unknown `demo_size` falls back to
`standard`; `flaw_count` clamps to 1-8 with `None` on garbage; `seed`
parses to int with `None` on garbage. All three ride into
`run_demo_build(..., demo_size=..., flaw_count=..., seed=...)`
(`main.py:484-486`).

`generate_demo_project` (`demo_gen.py:253-296`): `size` outside
small/standard falls back to standard; `flaw_count` bounds requested
flaws to 1-8 (`None` keeps them all); `seed` is a plain variation nonce
passed through as `seed`/`nonce` in the Muse payload alongside
`demo_size`/`flaw_count`. Invalid values never raise: they clamp or fall
back. The system prompt documents the contract (`demo_gen.py:47`).

CLI flags (`main.py:1074-1173`): `--ai-demo` (generates its own project,
cannot combine with `--scan`), `--build-brief`, `--vulns`,
`--demo-size`, `--flaw-count`, `--demo-seed`, `--intel-theme`,
`--intel-offline`. `--demo-seed` (like the other demo flags) requires
`--ai-demo` (`main.py:1284-1285`). Persisted config keys live in
`sms_cli.CONFIG_KEYS` (`sms_cli.py:27-46`): `demo_size`, `flaw_count`,
`demo_seed` (plus `fast_lane`, `offline_cve`, `deep_assessment`).

## Known surface gaps (honest list)

- Dashboard `socketQuery` (`static/app.js:739-749`) sends 4 scanners
  (`trivy,grype,osv-scanner,dependency-check`) when research scanners are
  enabled, while the server allowlist accepts 5 including
  `dependency-track` (`main.py:362`, `main.py:597-599`,
  `main.py:721-722`). Dependency-track is reachable from CLI/WS config
  but omitted from the dashboard toggle string.
- CVE fast lane is CLI-only: `--fast-lane` (`main.py:1136`) plus the
  `execute_cve_scan(..., fast_lane=...)` parameter (`cve_workflow.py:62`).
  No `/ws` socket query flag or TUI surface sets it yet.
- TUI (`tui.py`) has no demo/green mode: it covers CVE scan paths
  (`tui.py:119-208`) but exposes no `ai-demo`/Greenhouse build flow and
  no `demo_size`/`flaw_count`/`seed` inputs. Demo generation stays on the
  dashboard WS (`/ws/demo`) and the CLI `--ai-demo` path.
