# Arbitrary-project workflow

PurpleBox reviews an immutable snapshot of a local project without writing model output back to the source tree. The implementation is split between `project_agents.py` (stateless Muse roles and context batching) and `project_workflow.py` (Docker evidence gates, cycles, rollback, accounting, and reports).

## Public entry point

```python
result = await execute_project_workflow(spec, emit, config=settings)
```

`spec` is `projects.ProjectSpec`. Its `cycles` value defaults to 1 and is validated in the range 1 through 20. `allow_remote_inference=True` is required before any project source is sent to Muse. Only `spec.path.name` is used as the hosted project name. The absolute local path is never placed in a model payload.

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
