<!-- Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use. -->
<!-- https://polyformproject.org/licenses/noncommercial/1.0.0 -->

# Scan intensity profiles

Secure Mitigation System project scans separate **scan intensity** from **model selection**. The
`scan_profile` field controls how many remediation cycles run and how review focus
expands. The existing model `profile` still selects the Red and Blue Muse models.
Changing one does not change the other.

## Named profiles

| Key | Dashboard label | Cycles |
| --- | --- | ---: |
| `extra_light` | Extra light | 1 |
| `light` | Light | 3 |
| `medium` | Medium | 5 |
| `heavy` | Heavy | 8 |
| `super_heavy` | Super heavy | 12 |
| `ultra_heavy` | Ultra heavy | 12 |

A named cycle contains two remediation passes: **Red, Blue, Red, Blue**. Reports
identify these as `Cycle N · pass 1` and `Cycle N · pass 2`. This means a named
profile has `cycles * 2` logical review rounds.

`ultra_heavy` has the same bounded cycle count as `super_heavy`. It combines
larger team orchestration with bounded automatic discovery from the first pass.
Project intake exposes `red_agents` and `blue_agents`, each bounded from 1
through 12 and defaulting to 5.

## Cumulative focus and discovery bounds

`scan_profiles.focus_for_cycle(profile_key, logical_round)` returns an immutable,
deterministic tuple. Every profile starts with a practical common baseline:
architecture and trust boundaries, sources and sinks, server-side validation,
injection and output encoding, file/path/upload handling, and secure
configuration. Each logical round keeps that baseline and every earlier focus,
then adds one new structured area. Later rounds cover authentication,
authorization, deserialization, cryptography, races/TOCTOU, workflow integrity,
resource controls, regression gaps, and cross-component attack chains.

`ultra_heavy` also includes bounded automatic discovery outside the established
focus areas from logical round 1. Discovery is open-ended in subject matter but
bounded operationally: it cannot create additional rounds beyond the fixed 24
passes, and intake still bounds both agent teams. `super_heavy` uses the same 24
passes for structured review without automatic discovery. Unknown profile keys,
round zero, and rounds beyond `profile.cycles * 2` are rejected.

The focus order follows OWASP's guidance to expand baseline review breadth,
trace untrusted sources through processing to sensitive sinks, and cover
context-dependent areas such as access control, cryptography, business logic,
and race conditions. See the
[OWASP Secure Code Review Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html).

## `ProjectSpec` compatibility

`ProjectSpec.scan_profile` defaults to `custom`. This preserves existing clients:

- A payload that omits `scan_profile` may continue to send any explicit `cycles`
  value from 1 through 20.
- A custom payload that omits `cycles` retains the historical default of 1.
- A named profile derives its fixed cycle count automatically.
- If a named profile includes `cycles`, the value must match the profile. A
  conflicting explicit count is rejected before Docker or inference starts.
- `red_agents` and `blue_agents` default to 5 and must each be in `1..12`.

Custom mode retains the legacy single Red/Blue remediation pass per cycle. It
does not use named-profile cumulative focus orchestration.

## Dashboard

Local-project intake defaults to `extra_light`. The intensity dropdown updates a
read-only derived cycle field for every named profile. Selecting `custom` makes
the cycle field editable. Red and Blue team-size controls both default to 5 and
are enabled only for `ultra_heavy`. Model selection remains in the separate
**Models** control.

## CLI

Use `--scan-profile` for scan intensity and `--profile` for models:

```bash
python main.py --project /absolute/project \
  --command '["python3", "app.py"]' \
  --test-command '["python3", "-m", "pytest"]' \
  --contract 'Preserve the public API' \
  --scan-profile medium \
  --profile balanced \
  --red-agents 5 \
  --blue-agents 5
```

Legacy explicit cycles remain available in custom mode:

```bash
python main.py --project /absolute/project \
  --command '["python3", "app.py"]' \
  --test-command '["python3", "-m", "pytest"]' \
  --contract 'Preserve the public API' \
  --cycles 2
```

The CLI parses `--cycles` with a default of `None`. When neither a named scan
profile nor an explicit count is supplied, project construction normalizes the
legacy custom default to one cycle.
