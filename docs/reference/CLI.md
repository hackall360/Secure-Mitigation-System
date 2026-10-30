# CLI reference

Generated from `main.py` argparse (`main()`), 2026-10-30. Run
`python3 main.py --help` for the live text.

## Commands (mutually exclusive, one required)

| Flag | Help |
|---|---|
| `--init-images` | Build the two base images (requires Docker) |
| `--rebuild-images` | Force a fresh rebuild of both base images |
| `--docker-status` | Report Docker daemon and image readiness |
| `--cleanup` | Remove leftover session resources |
| `--serve` | Serve the local dashboard |
| `--tui` | Live terminal UI: panes, pipeline, result card (curses; degrades to plain text without a TTY); `h` shows Wave 2/5/8 receipt/guard/mutation tokens |
| `--scan {fixture}` | Scan one bundled fixture |
| `--project PATH` | Scan a local source directory without modifying it |
| `--list-targets` | List bundled fixtures without Docker or a key |
| `--health` | Report readiness (models, profiles, Docker) without Docker or a key |
| `--ai-demo` | AI-built demo mode: Muse designs a novel vulnerable demo, then red/blue exercise it in Docker |
| `--mcp-snippet PATH` | Verify one source snippet file through the red/blue Docker loop; prints the VerdictReceipt JSON (MCP submit_code_snippet over CLI) |
| `--mcp` | MCP STDIO transport: JSON-RPC on stdin/stdout (tools: submit_code_snippet, sms_scan_source, sms_scan_binary, sms_query_vault_stats, sms_verify_receipt) |
| `--snippet-language {javascript,python,php}` | Snippet language for `--mcp-snippet` (default: inferred from file extension) |
| `--sweep-passes N` | Multi-pass sweep depth for `--scan`: 1=standard only, 2=+deep, 3=+threat-actor (default: single finding loop) |
| `--binary-target PATH` | Sweep one compiled binary (ELF/Mach-O/PE) through the trusted harness 3-pass loop; prints per-pass exits + mitigation rules (`binary_argv_echo` resolves to the bundled fixture) |
| `--ingest-repo URL` | Clone a git repo at a pinned commit into an isolated Docker staging container, then run the project scan (requires `--commit-hash`; Phase 1, Wave 4) |

> Engine leaves (`sms_compress`, `sms_vault`, `sms_api`) are library modules, not CLI flags.

## TUI parity (`tui.py` plain mode; tri-surface with CLI/dashboard)

Verified via `python3 tui.py --help` 2026-10-30: the TUI exposes every CLI
scan surface. Curses keys: `1/2/3` fixture, `m` mcp, `b` binary, `p`
project, `g` sweep, `v` demo, `c` cve, `+/-` depth (1-3), `Enter/s` start,
`x/Esc` stop, `f` filter, `h` help, `q` quit. Plain-mode flags mirror the
curses modes:

| Flag | Help |
|---|---|
| `--mode {fixture,sweep,mcp,binary,project,demo,cve}` | Scan mode (default: fixture single finding loop); unknown mode exits 2 |
| `--snippet PATH` (`--snippet-language`, `--contract`) | MCP snippet file through the red/blue Docker loop (mcp mode) |
| `--binary-path PATH` (alias: `--binary-target`) | Binary sweep in binary mode |
| `--project-path/--project-command/--project-test-command/--project-contract/--project-cycles/...` | Project two-cycle workout (project/cve modes) |
| `--demo-theme/--demo-vulns` | Themed demo replay (demo mode) |

`--sweep-passes N` / `--binary-target PATH` without `--mode` keep the legacy
single-surface behavior via `_run_plain_legacy`; any dispatch flag routes
through `_run_state_scan` + `dispatch_scan`.

## Modifiers

| Flag | Default | Help |
|---|---|---|
| `--port` | 8000 | Dashboard port |
| `--image` | — | Already-loaded runtime image with offline dependencies |
| `--command` | — | Target argv as JSON, e.g. `["python3", "app.py"]` |
| `--test-command` | — | Trusted regression argv as JSON |
| `--contract` | "" | Expected behavior and sanitization-only patch constraints |
| `--scan-profile {profile,c custom}` | custom | Project scan intensity, independent of `--profile` models |
| `--cycles N` | — | Explicit custom red/blue cycles, 1 to 20 (legacy default: 1) |
| `--red-agents N` | 5 | Red agent team size, 1 to 12 |
| `--blue-agents N` | 5 | Blue agent team size, 1 to 12 |
| `--context-budget N` | 32768 | Bounded per-call source context budget |
| `--allow-remote-inference` | off | Consent to send source/evidence to hosted Muse endpoint |
| `--profile {economy,balanced,quality,custom}` | — | Model profile for `--scan` (default: configured models) |
| `--config PATH` | — | TOML or JSON file with an `[sms]` table of CLI defaults |
| `--format {table,json}` | table | Non-interactive output shape (tables show guard rationales + mutation probes) |
| `--show-usage` | off | Always print token/cost table even when no model calls were made |
| `--output-dir PATH` | — | Save scan JSON + candidate diff to a new run dir (includes `receipt.json`) |
| `--research` | off | Opt-in research sidecars for `--scan` (keyless OSV/CIRCL/GHSA/EPSS) |
| `--research-scanners LIST` | — | Comma-separated local scanners for `--research` grounding (requires `--research`) |
| `--commit-hash HEX` | — | Pinned 40-hex commit for `--ingest-repo` (required with `--ingest-repo`) |
| `--cve-scan` | off | Deep static+CVE scan (OSV lookup) instead of probe/patch verification |
| `--deep-assessment` | off | Muse triage of static signals and CVE context |
| `--offline-cve` | off | Skip OSV network lookup; static signals only |
| `--fast-lane` | off | CVE disclosure fast lane: static + OSV only, deterministic order, no Muse/NVD (requires `--project` with `--cve-scan`) |
| `--build-brief TEXT` | "" | What the AI demo should build (bounded to 500 chars) |
| `--vulns TEXT` | "" | Requested demo flaws: CVE IDs, named types, or free text |
| `--intel-theme TEXT` | input validation SQL injection XSS deserialization | Threat-intel themes for AI demo generation |
| `--intel-offline` | off | Generate AI demo without live NVD lookup |
| `--demo-size {small,standard}` | standard | Greenhouse demo size: small (fewer routes) or standard (full set) |
| `--flaw-count N` | — | Bound the requested demo flaws to 1..8 (default: keep them all; clamps; ai-demo only) |
| `--demo-seed N` | — | Variation nonce for AI demo generation (ai-demo only) |

CVE JSON output now carries `reach_score` + `reach_evidence` per vulnerability (KEV-listed +5, EPSS percentile >=0.9 +5 tie-breaks).

## Wave 2 (SPEC 14.8) output — no new flags

Verified via `.venv/bin/python main.py --help` 2026-10-29: Wave 2 adds no
CLI flags. It adds output rows/sections/files, all sourced from live result
fields (never synthesized):

| Surface | Location | Rows / behavior |
|---|---|---|
| `fact_table` rows | `sms_cli.py:631` via `format_wave2_facts` (`sms_cli.py:310`) | `Receipt`, `Guard rationales`, `Fast-lane top`, `Mutations` (each `Not reported` when the result carries no such evidence). |
| `--output-dir` extra file | `main.py:870` via `_extract_wave2_receipt` | `receipt.json`: top-level `receipt` (VerdictReceipt) or first cycle `receipt` (CycleReceipt); legacy `verdict_receipt` fallback; mode 0600. |
| Markdown report sections | `main.py:1093-1107` | `## Verdict receipt`, `## Guard rationales`, `## Mutation probes` — emitted only when the fact is reported. |
| TUI suffix | `tui.py:280` `describe_wave2` | Appends `[receipt ...] [guards ...] [mutations ...]` tokens to the result line, probing the same fields as `format_wave2_facts`. |

`format_wave2_facts` read order per item: Receipt = `result.receipt` (or any
`cycle.receipt`), legacy `verdict_receipt`; Guards = top-level
`guard_rationale` then each cycle `evidence.replacement_validation.guard_rationale`,
legacy `guard_rationales`; Fast-lane top = `fast_lane_top` string else first
`vulnerabilities[]` entry `queue_evidence` (else `reach_score`/`fixed_versions`/KEV/EPSS
composite); Mutations = cycle `evidence.{patched,pre}_verification.mutations`
`ExecutionEvidence` (`N/M held|failed (exit N)`), legacy `mutation_evidence`.

## Wave 5 (SPEC 14.9) output — no new flags

Verified via `.venv/bin/python main.py --help` 2026-10-29: SPEC 14.9 adds no
CLI flags (`--fast-lane`, `--context-budget` text unchanged; `--context-budget`
is the per-call source context budget, unrelated to the 60-line edit budget).
Behavior surfaces through existing rows only:

| Behavior | Existing surface | How it shows |
|---|---|---|
| Queue freshness (`_source_fresh`, `cve_workflow.py:66`) | `fact_table` fast-lane row / `queue_evidence` string | Stale-dated (>1 day) KEV/EPSS signals read as `stale:<date>` inside the same `reach:N fix:X kev:Y epss:Z` string; numeric `reach_score`/`epss_percentile` fields untouched. |
| EUVD exclusion (`FAST_LANE_EXCLUDED_SOURCES`, `assert_fast_lane_source_allowed`) | None (fail-closed only) | Raises `AssertionError` if a future wiring consults `euvd`; no CLI row, never blocks allowed sources. |
| Template/solver-shape guard (`is_solver_synthesized_shape`, `patches.py:27`) | `Guard rationales` row (`guard_id="solver_synthesized_shape"`) | Same `guard_rationale` `{guard_id, reason, trigger}` shape; 60-line `EDIT_BUDGET_LINES` unchanged. |
| Frozen mutation pool (`FROZEN_MUTATION_POOL_SHA256`, `mutation_pool_snapshot`) | None (internal) | `_assert_frozen_pool` runs at both mutation-script entry points (`modules/core/checks.py:438,560`); drift raises `ValueError`, no dedicated CLI row. |

## CVE scan notes

- `--fast-lane` orders findings by reach tier: `reach_score` desc, patched (`fixed_versions`) first, then id.
- KEV (CISA catalog) is a 5th keyless `cve_records` signal: exploited flag + due date, never raises.
- GHSA CVE lookup by exact CVE id is fixed (returns matching records only).

Related: [MODULES.md](MODULES.md) (`sms_cli.py` presenter), [guides/PROJECTS.md](../guides/PROJECTS.md) (project intake).
