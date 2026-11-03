# MCP Surface Notes — live test 2026-11-02 (worktree /tmp/wt-surface3)

Probes: `/tmp/mcp_surface/off_probe.py` (direct `handle_mcp_request`), `/tmp/mcp_surface/stdio_probe.py` (`--mcp` STDIO subprocess). Tmp vault only (`/tmp/mcp_surface/vault`, 1 seeded red record). NEVER touched live :8795. NO commits.

## Result: OFFLINE 25/25 PASS, STDIO 17/17 PASS. No critical findings.

### Per-tool matrix (offline / STDIO)

| Tool | Offline | STDIO | Notes |
|---|---|---|---|
| initialize / tools-list | PASS | PASS | 10 tools, protocol 2025-06-18 |
| submit_code_snippet | PASS (-32602 offline) | NOT CALLED (runs live Docker; out of scope) | Offline branch absent by design; live only via STDIO/HTTP |
| sms_scan_source | PASS (-32001 offline) | NOT CALLED (runs live Docker; asserted offline only) | |
| sms_scan_binary | PASS (-32001 offline) | NOT CALLED (runs live Docker; asserted offline only) | |
| sms_query_vault_stats | PASS (red.records>=1) | PASS | |
| sms_list_vault_namespaces | PASS (red listed) | PASS | No payload leak (`probe-shape` absent) |
| sms_replay_vault_record | PASS (roundtrip; bad id/ns -> -32603) | PASS (roundtrip; bad id -> -32603) | Summary only: id/fingerprint_prefix/status/created |
| sms_verify_receipt | PASS (canned valid; garbage -> valid False) | PASS (same) | |
| sms_scan_status | PASS (idle none/done; unknown id done) | PASS (done/verify) | Registry read only |
| sms_ops_status | PASS (daemon `ready` here -> full shape) | PASS (full shape) | Fail-closed path (-32603 when daemon unreachable) covered by existing unit test `test_ops_status_daemon_unreachable_fails_closed`, not re-proven here since daemon is up |
| sms_showcase_status | PASS (tts/capture/music/render keys) | PASS (same keys) | Static file checks only |

### Schema rejection (extra keys -> error)

- `sms_verify_receipt` + extra key (`evil_extra_key`/`bogus`): rejected both transports — offline returns `valid False` (VerdictReceipt `extra=forbid`), no error envelope, no raise. PASS.
- Input schemas all carry `additionalProperties: False` (verified by reading `mcp_bridge.py` tool definitions for all 10 tools). Runtime extra-key enforcement at the `verify_receipt` layer confirmed; other tools' extra args are ignored by design (e.g. `scan_status` reads only `scan_id`).

### Fail-closed codes

- Unknown tool -> -32602 (both transports). PASS.
- `sms_scan_source` / `sms_scan_binary` offline -> -32001 (both asserted; NEVER invoked live). PASS.
- Bad vault id / bad namespace -> -32603 (both transports). PASS.
- 6 garbage frames (bad version, unknown method, null name, string params, string arguments) -> valid envelopes, zero raises, zero tracebacks. PASS. STDIO stderr: no traceback. PASS.

### Observations (non-blocking)

1. `submit_code_snippet` has NO offline branch in `handle_mcp_request` (falls through to `Unknown tool -32602`), while `sms_scan_source`/`sms_scan_binary` have an explicit `-32001` offline refusal. Consistent with design (snippet never had an offline meaning) but asymmetric: a client cannot distinguish "unknown tool" from "snippet needs live transport" offline. Consider a `-32001` branch for parity.
2. This sandbox HAS a live Docker daemon (`docker_health` -> `ready`), so `sms_ops_status` returned success, not the fail-closed `-32603`. The unreachable-daemon path is unit-tested but was not live-proven here.
