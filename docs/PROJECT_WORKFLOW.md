# Arbitrary-project workflow

Secure Mitigation System reviews an immutable snapshot of a local project without writing model output back to the source tree. The implementation is split between `project_agents.py` (stateless Muse roles and context batching) and `project_workflow.py` (Docker evidence gates, cycles, rollback, accounting, and reports).

## Public entry point

```python
result = await execute_project_workflow(spec, emit, config=settings)
```

`spec` is `projects.ProjectSpec`. Its `cycles` value defaults to 1 and is validated in the range 1 through 20. `allow_remote_inference=True` is required in hosted mode before any project source is sent to Muse. Local mode uses only the explicitly configured loopback endpoint and does not require or grant remote-source consent. Only `spec.path.name` is used as the hosted project name. The absolute local path is never placed in a model payload.

The result is `ProjectWorkflowResult`. It provides both the project-native fields and compatibility aliases used by the CLI and UI:

- `status`: `verified`, `no_findings`, `partial`, or `error`
- `cycle_reports`, also serialized as `cycles`
- `cumulative_diff`, also serialized as `diff`
- `total_cost_usd`, also serialized as `cost_usd`
- `cleanup.succeeded`, also serialized as `cleanup_ok`
- `usage`, `total_tokens`, `success`, and per-cycle evidence

`verified` means only that retained candidate replacements passed the recorded evidence gates. It never means the project is generally secure. `no_findings` means the bounded review produced no testable finding, not that no vulnerability exists. Rollback-only, unconfirmed, or inconclusive runs are `partial` and are not successful.

## Snapshot and context boundaries

`projects.snapshot_project()` reads a deterministic bounded snapshot. Binary files and text outside the inference limits remain in the sandbox snapshot but are not sent to Muse. The default inference caps are 512 UTF-8 files and 2 MiB. Omitted paths, counts, covered bytes, covered paths, batches, and limitation notes are returned in `ContextCoverage`.

`project_agents.build_source_batches()` covers every selected UTF-8 byte. A large file is split only at an explicit UTF-8 byte boundary. No source suffix is silently discarded. The full serialized payload, including contract, history, evidence, coverage, and `schema.model_json_schema()`, is checked against the effective payload budget. `ProjectSpec.context_budget` is converted to an approximate four-bytes-per-token ceiling and is also capped by `ProjectWorkflowLimits.max_payload_bytes`.

Large red evidence sets are hierarchically compressed with fresh `RedEvidenceDigest` calls before the independent red report call. Blue affected files are grouped into bounded calls. A single artifact that cannot fit causes an explicit fail-closed error rather than truncation.

All source, contract, history, runtime output, and prior model output is identified in system prompts as untrusted data, never instructions.

## Cycle and evidence gates

The preserved original regression command is run before the first red inference. Each cycle then performs:

1. Fresh red evidence calls for every source batch.
2. A separate fresh red report call selecting one testable finding or `no_finding`.
3. Pre-change execution of the report's exact Python probe. Exit 0 means vulnerable, exit 1 means blocked, and every other result is inconclusive.
4. One or more fresh blue proposal calls limited to complete existing snapshot files.
5. Path, source-hash, duplicate, no-op, file-count, byte-count, and protected-test validation.
6. A fresh patched target, the exact same original probe, and the unchanged original regression command.
7. A separate independent red assessment. If it reports the same vulnerability class, its new probe is also run on another fresh target and must be blocked.
8. A separate fresh final-blue report call based on bounded immutable evidence.

A candidate is carried into the next cycle only after the original probe is blocked and the preserved regression command passes. A confirmed or inconclusive same-vulnerability independent probe causes rollback. An unrelated independent finding is recorded for subsequent cycles rather than misrepresented as failure of the current repair.

The cumulative diff is recomputed in `finally`, so a later model, Docker, or reporting failure cannot hide previously retained verified replacements. No candidate diff is automatically applied to the source project.

## Protected regression corpus

Blue may assess tests but cannot replace common regression paths:

- directories named `test`, `tests`, or `__tests__`
- `test_*`, `*_test.py`, `*.test.*`, and `*.spec.*`
- existing snapshot paths named explicitly in `test_command` argv

This prevents common test-deletion and always-pass proposals. It is not a semantic proof that every ecosystem's regression corpus is protected, so final reports disclose that remaining limitation.

## Docker interface

`DockerProjectSandbox` adapts the project primitives in `docker_manager.DockerSandboxManager`:

- `require_base_images()` and `create_isolated_network()`
- `start_project(network, spec, snapshot)` for a fresh target aliased as `target-service`
- `run_project_check(..., command=spec.test_command)` for regression evidence
- `run_project_check(..., script=probe)` for a read-only Python verifier
- `stop_project()` after each evidence snapshot
- `close()` during normal completion, errors, and cancellation

`projects.replace_snapshot_files()` creates the candidate snapshot in memory and rejects new paths. The original source tree remains unchanged. Docker operations run through `workflow.blocking()`, which waits for an in-flight thread before cancellation cleanup proceeds.

The execution contract, including the expected `target-service` hostname and port 8080 where applicable, is passed to every Muse stage. The local path is not.

## Research basis

The design treats test-passing patches as candidates rather than correctness proofs because automated repair can overfit its validation suite. The additional independent assessment and unchanged regression corpus follow that risk model. See Le-Cong et al., *Invalidator: Automated Patch Correctness Assessment via Semantic and Syntactic Reasoning*, IEEE TSE 2023: <https://arxiv.org/abs/2301.01113>.

Repository context is batched and explicitly accounted for instead of attempting to place an entire repository into one context window. A practical overview of selective repository context and its context-window tradeoff is: <https://www.tabbyml.com/blog/repository-context-for-code-completion>.

## Offline integration traps and executable checks

`main.py` exposes `inference_mode` and `inference_ready` from `/api/health`.
`static/app.js.initialize()` uses those fields, not just `api_key_configured`:
a local Muse endpoint deliberately works without a hosted API key. In local mode
the remote-consent label is hidden and `projectSpec()` always sends
`allow_remote_inference: false`, including if a stale checkbox is checked.
`project_workflow.execute_project_workflow()` checks consent only for hosted mode.
Configuration validation and `MetaMuseClient` still enforce the literal-loopback
endpoint restriction, no redirects, and no hosted fallback. Health readiness is
configuration readiness, not an assertion that the model server is reachable.

Run `.venv/bin/python -m pytest -q tests/test_dashboard_project.py` to execute
JavaScript intake/readiness checks under Node. These use a minimal DOM substitute,
not a visual browser acceptance check. Context-budget bounds are 1024 through
131072 in both the HTML, JavaScript intake, and `ProjectSpec`.

Run `.venv/bin/python .jcode/tools/project_scan.py` for two real Docker cycles.
Only the Muse HTTP transport is replaced with deterministic structured replies.
The transport recognizes the current red report payload key `evidence_digests`,
not the obsolete `batch_evidence`. A mismatch raises before probe execution and
produces a failed report despite the initial red evidence call succeeding.
The workflow intentionally sanitizes unexpected exception details in public
reports, so inspect the transport contract when a harness reports AssertionError.
This check exercises cumulative SQL parameterization then decimal-input
allowlisting, probe rechecks, unchanged original regressions, original-source
preservation, fresh role contexts, and cleanup. It does not measure model quality
or attest a real local Muse server.

## Finalization findings: real Muse and browser contracts

`agents.MetaMuseClient._request()` now passes the Pydantic schema through
`response_format = {"type": "json_schema", "json_schema": {"name": ..., "schema": ...}}`.
Embedding `response_schema` only in prompt text was not constrained decoding:
a live project run returned schema-invalid output despite prompt-only unit tests
passing. `_request()` removes the duplicate schema from the user payload before
sending it, while `ProjectAgentRunner._call()` still accounts for one schema in
its bounded context calculation. Responses still undergo strict local validation.
No retry, schema repair, or fallback provider is silently introduced. Local
Muse-compatible servers must support this Chat Completions response format.
Official source: <https://dev.meta.ai/docs/structured-output> (October 28, 2026).
Strict mode is intentionally not set because these Pydantic schemas have optional
properties. Meta documents that decoding remains schema-constrained with strict
omitted. The schema is non-recursive and below Meta's documented depth limits.

Live Muse also produced a valid probe importing `src.boundaries`. That originally
failed with `No module named 'src'`, because launching `/verifier/runner.py` added
`/verifier`, not `/workspace`, to the import path. Project probes now launch Python
with `-I -B -u -c`, load `runpy`, append `/workspace` after the standard library,
and run the existing trusted runner. The exact model probe is unchanged before
and after patching. No base-image rebuild is needed for this launch change.
`-I` ignores inherited PYTHONPATH and excludes implicit startup search paths,
while `-B` prevents bytecode writes and `-u` keeps timeout evidence unbuffered.
See <https://docs.python.org/3.12/using/cmdline.html#cmdoption-I>.
All project targets and checks explicitly set Docker `working_dir=/workspace`:
relying on a custom image's WORKDIR violated the documented execution contract.
The verifier still has only its own Python standard library, not target runtime
dependencies. HTTP probes are preferred for services. Missing dependencies remain
inconclusive, not blocked.

Browser result presentation must use project-native evidence, not fixture fields.
`ProjectWorkflowResult.baseline_verification` preserves the actual original
regression evidence. `static/app.js.summaryEvidence()` computes multi-cycle probe
counts and regression summaries from recorded cycle checks, with unknown values
remaining unknown. `renderUsage()` recognizes `project_blue_*` roles. Project
stage log messages now drive `advanceStage()` and reset analysis per cycle.
Otherwise a completed run misleadingly showed all stages skipped, all calls Red,
and probes not run. Project report filenames use `project`, not the fixture-only
`target` field.

For repeatable real-browser acceptance, start
`.venv/bin/python .jcode/tools/project_ui_scan.py`. It prints a generated repository
specification and serves a keyless local dashboard on port 8798. Its test-only
`/v1/chat/completions` route serves deterministic JSON replies over actual loopback
HTTP. All snapshots, Docker execution, WebSockets, frontend code, and cleanup are
production paths. Fill the printed settings in Local project mode and run two
cycles. A private `browser-report.json` is saved in
`reports/browser-project-acceptance/`. Stop this test server afterward, never use
its deterministic inference route for actual security review.

`.venv/bin/python .jcode/tools/project_scan.py --source-import-probes --cycles 1`
checks the pure-Python import path through real Docker. `--live --cycles 1` instead
uses the configured real Muse endpoint and incurs API usage, sending only the
generated fixture source. Export the trusted `.env` as described in DEVELOPMENT.md
first. Use separate `--output-dir` paths to preserve evidence from each attempt.

## Cycle-based profiles and two-pass evidence (2026-10-28)

Project intensity is not a time limit. See [SCAN_PROFILES.md](SCAN_PROFILES.md)
for the profile catalog and [DISCOVERY_TEAMS.md](DISCOVERY_TEAMS.md) for actual
Muse leader/worker orchestration. `ProjectSpec.scan_profile` is independent of
the existing model-selection profile.

`execute_project_workflow()` runs two complete remediation rounds per named
cycle. `ProjectCycleReport.cycle` identifies the outer cycle and `pass_number`
identifies round 1 or 2. Consequently, `cycle_reports` has two entries per
completed named cycle, while `cycles_completed` increments only after pass 2.
Do not equate the number of report entries with the number of cycles. Each
round retains the existing independent red audit and final blue evidence report
in addition to the discovery and patch stages. These audits are not substitutes
for the second actual patch-capable round.

Every retained replacement updates the immutable cumulative snapshot before the
next remediation round. Each named profile continues through its selected
rounds after a no-finding, blocked, or inconclusive probe, but never asks Blue to
patch an unproven finding. Docker or inference failures still stop safely and
cleanup runs. Legacy custom requests keep their former single-round/early-stop
behavior. Sandbox labels include both cycle and pass for named profiles.

Mechanical acceptance command:

```sh
.venv/bin/python .jcode/tools/project_scan.py --scan-profile extra_light \
  --output-dir reports/cycle-profile-acceptance
```

This uses actual Docker targets and verifier containers and the real Muse HTTP
client with deterministic model replies. It confirms two distinct vulnerability
patches in one cycle, that the second starts from the first retained snapshot,
that original host files stay unchanged, and that cleanup succeeds. It does not
measure live-model discovery quality. Never substitute the final blue report
for the second patch call, or stop a named scan on the first empty finding.

## Deep static + CVE scanning (2026-10-28)

`deep_scan.py` and `cve_workflow.py` add an in-depth scanner alongside the
probe/patch workflow:

- Deterministic local static signals (eval/exec, deserialization, SQL
  concatenation, shell sinks, TLS disabled, hardcoded secrets, cleartext HTTP,
  debug flags) with CWE hints. Signals are triage hypotheses, never confirmed
  vulnerabilities.
- Dependency inventory from `requirements.txt`, `package.json`, and lockfiles,
  queried against OSV.dev (`/v1/querybatch` + `/v1/vulns`) for CVE aliases,
  CVSS severity, and fixed versions. OSV needs no key. Sources: https://osv.dev
  and https://google.github.io/osv.dev/api/.
- Optional Muse deep assessment (`DeepVulnReport`) that prioritizes reachable
  paths and describes isolated verification probes with benign markers. It never
  authorizes destructive payloads, persistence, exfiltration, or escapes, and
  never replaces Docker probe evidence.

CLI:

```sh
python main.py --project /path/to/repo \
  --command '["python3", "app.py"]' \
  --test-command '["python3", "-m", "unittest"]' \
  --contract 'Preserve behavior' \
  --cve-scan --offline-cve

python main.py --project /path/to/repo \
  --command '["python3", "app.py"]' \
  --test-command '["python3", "-m", "unittest"]' \
  --contract 'Preserve behavior' \
  --cve-scan --deep-assessment
```

`--cve-scan` runs the deep scanner instead of probe/patch verification.
`--offline-cve` skips OSV network lookup. `--deep-assessment` adds Muse triage
and spends inference credit. Reports include `report.json` and `SUMMARY.md`
with static signals, dependencies, CVE records, and advisory assessment.
