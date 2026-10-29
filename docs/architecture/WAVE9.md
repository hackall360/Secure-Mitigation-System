# Wave 9 (migration): Wave 2 data flow (SPEC 14.8)

Wave 2 mechanics (SPEC 14.8 items 1-4) wired through the Wave 8 proof
gates. Follow-on to [WAVE8.md](WAVE8.md); SPEC anchor
`docs/SPEC.md` 14.8.

## Receipts: build and export paths

Two receipt types, both record-only (never upgrade a verdict):

- Fixture loop: `VerdictReceipt` (`workflow.py:218-236`) via
  `build_verdict_receipt` (`workflow.py:238-259`), exported by
  `export_receipt_json` (`workflow.py:262-264`), carried on
  `ScanResult.receipt` (`workflow.py:278`). Fixture loop has one
  regression gate, so regression + differential share one outcome;
  properties do not run there (`None`).
- Project loop: `CycleReceipt` (`project_workflow.py:214-231`) via
  `build_cycle_receipt` (`project_workflow.py:234-262`), exported by
  `export_cycle_receipt_json` (`project_workflow.py:265-267`),
  attached to the retained cycle report only
  (`project_workflow.py:1584-1597`).

Both hash the candidate patch/diff with SHA-256 hex.

## Guard rationale binding on rejects

Every rejection path returns a `GuardRationale` (`guard_id`,
`reason`, `trigger`, max 500 chars), never probe bytes (LAW 4):

- Fixture patches: `guard_rationale(exc)` (`patches.py:29-39`)
  exports `guard_id` / `reason` / `trigger` from `PatchRejected`.
- Project replacements: `_reject` (`project_workflow.py:809-821`)
  binds a `GuardRationale` (`project_workflow.py:177-190`) to each
  `ReplacementValidation` (`project_workflow.py:192-198`).
  Accepted validations carry `guard_rationale=None`.

## Fast-lane topping evidence strings

`_queue_evidence` (`cve_workflow.py:33-52`) emits one auditable line
per ranked summary:

```text
reach:<score> fix:<first-fixed-or-none> kev:<listed|absent> epss:<pct|absent>
```

Rank key `_fast_lane_rank` (`cve_workflow.py:55-70`): `-reach`,
then unfixed-last, non-KEV-last, `-epss`, then id. Intake capped at
`FAST_LANE_MAX_INTAKE = 10` (`cve_workflow.py:30`), id-sorted before
the detail cap so the capped set never depends on OSV ordering.

## Mutation gate chain

`verify_project_snapshot` (`project_workflow.py:595-719`):

1. `mutation_fixture_supported(id)` true ->
   `project_property_mutation_script(id)` runs ONCE in the same
   capped container as regression; the single combined
   `ExecutionEvidence` is recorded as BOTH `properties_ev` and
   `mutations_ev` (`project_workflow.py:614-626`).
2. Otherwise, if the id is mutation-supported and not
   `node_query_sink`, `project_mutation_script(id)` runs standalone
   (`project_workflow.py:644-661`).
3. Anything else leaves `mutations=None` (skips; arbitrary
   projects unaffected).
4. Any exception in either branch records exit 2
   ("did not run"), which the fail-closed gate vetoes.

`mutation_gate_passed` (`project_workflow.py:101-127`): `None`
passes; any recorded exit other than 0 fails; unparsable evidence
fails.

## Fail-closed gate order

Retain requires ALL of (`project_workflow.py:1484-1499`):

1. probe blocked, 2. regression exit 0, 3. not inconclusive,
4. `differential_passed`, 5. `property_gate_passed(patched)`,
6. `mutation_gate_passed(patched)`.

Independent same-finding re-check repeats 1/2/5/6 on a fresh target
(`project_workflow.py:1500-1510`).

## TRAP: node-vs-php/mysql response shape

Mutation/property scripts must match each target's REAL shape
(`checks.py:253-255`); a shape mismatch raises inside the harness
and exits 2, which the fail-closed gates turn into a rollback on a
healthy service:

- node (`node_query_sink`): JSON envelope `{status,count,results}`.
- php (`php_command_sink`): status/host/diagnostic text per host
  arg (echo exactly or clean 4xx reject); NOT the node envelope.
- mysql (`mysql_insecure_conf`): `/my.cnf` config re-read,
  byte-identical with audited keys; no JSON at all.

This is the Wave 8 property TRAP generalized: `json.loads` on a
plain-text body, or an envelope assertion on a text/config
service, is exit 2, not exit 1. The contract first line names the
fixture id so the opt-in wiring picks the matching script.
