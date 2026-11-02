# Technical breakdown — how the Secure Mitigation System works

Companion to the [`README.md`](../README.md). The README explains the loop
like you are five. This page explains it like you build software: the exact
passes, the isolation, the memory, the receipts, and where each part lives.

## The loop in one paragraph

A scan takes a fixture (source or compiled binary), runs it through up to
four sweep passes, and for each pass asks Red to find a weak input rule,
proves the finding with a probe inside an air-gapped Docker box, asks Blue
for a minimal patch, then re-runs the probe plus trusted normal-input
regression checks against the patched target. Only a probe that flips from
exit `0` (rule broke) to exit `1` (rule held) with regression green counts
as `verified`. A `VerdictReceipt` (fix hash + exact exit codes) is committed
to the encrypted vault. Anything else fails closed: `not_confirmed`,
`failed`, or `error` — never `verified`.

## The four sweep passes

Defined in `library/workflows/sweep.py` (`SWEEP_PASSES`, l.38):

| pass | what Red looks for |
|---|---|
| `standard` | common CVE sink patterns |
| `deep` | edge cases and input-mutation handling (encoding, coercion, truncation) |
| `threat_actor` | logic abuse + technical exploitation, combined into novel behavior |
| `chain` | linked fixtures where step A's output feeds step B's sink (e.g. `node_chain_link`: a role-grant gate in Link A guards a dynamic query in Link B) |

`--sweep-passes N` (1–4) selects a prefix of that tuple (l.317). Chain
fixtures prove what single-step misses: each link alone looks safe, the
chain is not.

## Context compression (token saver)

`library/shared/sms_compress.py`: deterministic middleware that dedups,
prunes boilerplate, and enforces a token budget before context reaches Muse.
Critical lines are never dropped — budget overflow drops filler first
(ll.29–30). Every run emits a `CompressionReport` (`compressed_tokens_sent`,
`compression_ratio`) serialized into the `ScanResult`, so the dashboard can
show exactly what was saved.

## The vault (memory)

`library/intel/sms_vault.py`: an encrypted on-disk vault (override via the
`PURPLEBOX_VAULT_DIR` env var, l.75). Before Red analyzes, the workflow
fingerprints the target and checks for a `KNOWN_ARCHETYPE` hit: a repeat of
a solved shape recalls the prior finding + patch instead of spending fresh
Muse calls. Novel shapes are tagged `NOVEL_SURFACE` and run the full loop;
their receipts are committed back so the next identical shape recalls them.
The dashboard surfaces this as the Vault recall badge.

## Isolation (the locked room)

`library/core/docker_manager.py`: every probe runs in its own container with
`network_mode="none"` (ll.369, 569, 618, 681, 775) on an `internal=True`
network (l.344), read-only root filesystem (`read_only: True`, l.418),
capped RAM (`mem_limit`, l.243) and PIDs (`pids_limit`, ll.246), non-root
user, and no host mounts. Per-session containers, snapshots, and networks
are removed afterward (LAW 4 cleanup). Exit codes are the whole verdict
language: `0` = boundary reached, `1` = blocked, `2` = inconclusive.

## 429s and retries (rate limits)

Two layers, both never-raise. The Muse transport (`library/core/agents.py`,
ll.147–163) retries transient statuses `(429, 502, 503, 504)` with capped
exponential backoff + jitter, honoring a server `Retry-After` on 429 up to a
cap. The intel sidecars (`library/intel/research.py`, l.20) use the same
discipline (backoff with jitter, small pages). A scan degraded by rate
limits reports what it could not fetch — it never invents grounding.

## Receipts (cryptographic proof)

`library/workflows/workflow.py` defines `ScanResult` + `VerdictReceipt`;
`library/services/sms_api.py:verify_receipt` (ll.97–137) validates a receipt
digest without Docker: schema-check, then chain-check that a follow-up
receipt re-attests the SAME patch (`prev_receipt_sha`). The README code
sample calls exactly these two functions:

```python
from library.services.sms_api import scan_source, verify_receipt
```

Reports are redacted (`redact_report_for_user`) and stored `0600`; only
lengths and exit codes leave the loop (LAW 4).

## Live telemetry (WebSocket → dashboard/TUI/CLI)

`main.py` WS executors (`run_socket` l.735, `combat` l.1080,
`project_combat` l.1084, `demo_build` l.1088, `binary_combat` l.1093) stream
granular team events. `web/js/ui/comms-feed.js` renders them: `CommsFeed.append(team, text)`
(l.291) appends chatter, `advanceStage(team, text)` (l.345) moves the phase
graph, `buildRoster` (l.230) seats the red/blue/green crews, `renderDiff`
(l.623) + `showResult` (l.1081) present the patch and verdict. The same
events feed the TUI (`tui.py`) and CLI (`sms_cli.py` tables) — LAW 8
tri-surface parity. Transport hiccups stay log-only; the scan keeps running
server-side (`app.js:1298`).

## Scan profiles (intensity vs model)

`library/core/scan_profiles.py`: `scan_profile` controls how many
remediation cycles run and how review focus expands (`extra_light` = 1 cycle
through exhaustive 12-cycle profiles); the model `profile` (Spark vs Wonder)
is independent. Changing one never changes the other.

## Where everything lives

- Core loop + guards: `library/core/` (agents, prompts, patches, checks,
  docker_manager, pricing, profiles, registry, scan_profiles)
- Reused logic: `library/shared/` (compression, HTTP, records, redact,
  vault helpers, text, budget, async)
- Keyless intel: `library/intel/` (OSV/CIRCL/GHSA/EPSS research + Trivy,
  Grype, OSV-Scanner, Dependency-Check, Dependency-Track transports)
- Product surfaces: `library/services/` (API, projects, chatter, intake,
  demo, MCP bridge)
- Verification loops: `library/workflows/` (fixture, sweep, binary,
  project, CVE, deep)
- Category maps: `docs/web/INDEX.md`, `docs/tui/INDEX.md`,
  `docs/mcp/INDEX.md` (members stay at gate-pinned paths — see each map)
