# Discovery review teams

`ProjectAgentRunner` is configured once before each remediation pass:

```python
runner.configure_review(
    profile_key=profile_key,
    cycle=cycle,
    red_agents=5,
    blue_agents=5,
    pass_number=pass_number,
)
```

`pass_number` is optional for direct callers and defaults to 1. The workflow passes 1 or 2 explicitly. The runner converts `(cycle, pass_number)` to the cumulative logical round `(cycle - 1) * 2 + pass_number` before calling `scan_profiles.focus_for_cycle()`.

Every subsequent red, blue, and final-report request for that pass contains this stable payload field:

```json
{
  "review": {
    "profile_key": "heavy",
    "cycle": 2,
    "pass_number": 1,
    "cumulative_focus": ["..."]
  }
}
```

Calling a stage with a cycle different from the configured cycle fails before inference. Agent counts are bounded from 1 through 12 to match intake validation. `custom` keeps an empty focus list and the pre-profile single-agent behavior.

## Standard profiles

`extra_light`, `light`, `medium`, `heavy`, and `super_heavy` retain the existing one-call-per-stage orchestration. Their cumulative focus is added to every stage payload. Focus breadth is owned by `scan_profiles.py`; it must be distributed over `profile.cycles * 2` logical rounds because every named-profile cycle has two remediation passes.

## Ultra-heavy model team

`ultra_heavy` uses actual Muse calls through `MetaMuseClient._request` for both teams:

1. A leader planning call receives bounded metadata, cumulative focus, and the requested worker count.
2. The returned `ReviewTeamPlan` must contain exactly agents `1..N` with no missing or duplicate index.
3. Each red worker independently reviews each bounded source batch. The existing digest tree compresses oversized evidence without truncation.
4. The red leader synthesis call produces the existing `RedReport` schema.
5. Each blue worker independently proposes changes against only the supplied safe snapshot file group.
6. The blue leader synthesis call receives those bounded worker proposals and returns the existing `BlueProposal` schema.

The default requested team size is five red workers and five blue workers. Role names identify leader planning, each worker, digest calls, and leader synthesis, so every completed HTTP call is included in `MetaMuseClient.usage` by the existing transport accounting.

`RedAnalysisArtifacts.leader_plan` persists the validated red assignments for reporting and is `None` outside ultra-heavy orchestration. Blue keeps the existing model-facing `BlueProposal` schema unchanged; its plan remains observable through the explicitly named planning and synthesis calls and their usage records.

## Safety and bounds

Leader assignments and worker proposals are explicitly treated as untrusted model output. They cannot override the red probe execution contract, invent omitted source, expand blue changes beyond existing supplied paths, or relax the sanitation-only change kinds:

- `input_validation`
- `parameterization`
- `configuration_hardening`

All planning, worker, digest, and synthesis requests use the existing `_call()` serialized-payload byte check. Oversized artifacts fail closed with `AgentError`; no source, plan, evidence, or proposal is silently truncated. Existing workflow validation still enforces path safety, original hashes, duplicate/no-op rejection, protected regression files, changed-file bounds, changed-byte bounds, runtime probe evidence, unchanged regression commands, and rollback.

## Focused validation

Run:

```bash
.venv/bin/python -m pytest -q tests/test_discovery_teams.py
```

The focused tests verify cumulative profile context, pass-aware expansion, five-worker red and blue fan-out, real leader planning and synthesis calls, sanitation-only blue output, role-level usage accounting, and configuration bounds.
