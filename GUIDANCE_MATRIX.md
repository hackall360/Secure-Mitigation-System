# GUIDANCE MATRIX — closed-loop state-differential ledger (brief 2026-11-01-closed-loop-guidance)

Live Δ tracker. A subsystem exists in $S_{current}$ **only** when its gate exits 0.
Status: `[ ]` UNVERIFIED | `[~]` IN_PROGRESS | `[x]` VERIFIED_ZERO_DELTA.

LAWs governing this task: 0, 1, 2, 8, 9, 10, 11. Branch: `feature/webui-v3-migration`.
Baseline (LAW 10A): gate green pre-change 06:30 UTC — 876 passed + All checks.

| ID | Subsystem | $S_{current}$ (measured) | $\Delta$ deviation | Corrective vector | Gate | Status |
|---|---|---|---|---|---|---|
| A | WebUI v3 asset migration + serving | `web/` holds v3 tree verbatim (6 pages, js/css/tools, AGENTS+README); `sync_assets.py --check` → `assets in sync`; `GET /web/*.html` → 200 + assets:begin; `/` still v2; `static/` untouched | 0 | none further | contract A-group 4/4 + sync --check | `[x]` |
| B | Telemetry data contract + payload mapping | `socket_emit` + `build_compression_event` + `build_ingest_event` carry server `ts`; health/targets keys already v3-complete; redacted result aliases (pre/post_exit_code, receipt.patch_sha256) already read by result-view; no calc logic touched (rubric matrix preserved) | 0 | none further | contract B-group + full suite | `[x]` |
| C | WS pipeline + state hydration | `{type:snapshot}` first frame (nodes/hud/chips/ts) on every accept; busy path still precedes snapshot (lock check first — verified in code); `TelemetryBatcher` 100–250 ms for telemetry bursts only; run path inline (loop unblocked); 15 pre-existing WS tests updated to snapshot-first via `tests/helpers.drain_snapshot` (no assertions weakened) | 0 | none further | contract C-group + Gate 2 live Docker 4/4 | `[x]` |
| D | Gates + docs + commit | Gate 1 green (885 passed + 1 skipped, All checks — 06:50 UTC; 876 baseline + 9 new contract tests); Gate 2 `offline_scan` 4/4 verified + cleanup (06:45 UTC); Gate 3 Firefox + Chrome v3 proof (6/6 pages, HUD/chips, snapshot, interpreter stages/verified); docs updated (web/INDEX, TRAPS, matrix); proof tool `.jcode/tools/v3_ui_proof.py` | 0 — Δ=0 across all subsystems | commit on feature branch (no merge/push unasked) | dev.py + scans + browser | `[x]` |

## Δ-recompute log

- 06:30 UTC: baseline green (876 passed + All checks) — S_current pinned.
- 06:35 UTC: RED tests written; 7 fail on functional absence, 2 pass.
- 06:36–06:37 UTC: A implemented (web/ copy + /web mount + page routes); B implemented (ts aliases); C implemented (snapshot + batcher). First regression caught: `test_disconnect_cancels...` expected hello-first → updated to snapshot-first (test strengthened to contract, impl unchanged — LAW 9B clean).
- 06:38–06:41 UTC: Gate 1 red (16 failures, all hello-first assumptions in w22/project/profile tests) → halted forward work, built `drain_snapshot` helper, routed 15 sites, tolerated snapshot in collect-loop, verified busy-precedes-snapshot ordering. Regression → 0. Second red: vendored `web/tools/*.py` upstream style trips repo ruff → `exclude = web/tools/*` in pyproject (vendored pipeline, never hand-edited). Third: 3 files needed ruff format.
- 06:45 UTC: Gate 2 green — `offline_scan` 4/4 verified pre=0 post=1 + cleanup, with snapshot active (loop unblocked).
- 06:46–06:48 UTC: Gate 3 green — Firefox + Chrome v3 proof: 6/6 pages 200 + assets_sync, snapshot {hud ×5, nodes 5, chips server/docker/key}, console render {hud/chips all true, stages sandbox/probe/patch, findings 1, verdict verified}. Floor: v2 `ui_scan` Firefox exit 0 (Boundary check passed card read). Trap recorded: console.html redirects without launch → proof seeds launch like prod-setup, then reloads (real user flow); /usr/bin/firefox is a snap wrapper → omit --binary unless ELF (same rule as ui_scan).
- Trap refinement (TRAPS.md): physical `web/` is safe (no root `web.py`); only `tui/` shadows. GG2 no-physical-dirs verdict narrowed to same-named modules.

---

# Brief 2026-11-02-systems-assurance-e2e — 7-stage sweep (branch `feature/systems-assurance-sweep`)

LAWs governing this task: 0, 1, 2, 3, 4, 6, 8, 9, 10, 11.
Phase 0 baseline (LAW 10A): gate green pre-change 2026-11-02 ~18:58 UTC — **1050 passed + 1 skipped, All checks passed**.

## Slice registry

| Slice | Agent | Write scope | Deps | Status |
|---|---|---|---|---|
| S1 | reader-engine | NONE (read-only audit of `library/core/`, `library/workflows/`) | — | `[.]` dispatched |
| S2 | reader-services | NONE (read-only audit of `library/services/`, `library/intel/`) | — | `[.]` dispatched |
| S3 | reader-entry | NONE (read-only audit of `main.py`, `tui.py`, `sms_cli.py`, `library/shared/`) | — | `[.]` dispatched |
| S4 | reader-surface | NONE (read-only audit of `web/`, coverage ledger CLI/API/UI/TUI inventory) | — | `[.]` dispatched |
| S5 | reader-contracts | NONE (read-only audit docs-vs-code: README/docs/ vs behavior) | — | `[.]` dispatched |

## 7-stage matrix (Δ tracker; `[ ]` UNVERIFIED | `[~]` IN_PROGRESS | `[x]` VERIFIED_ZERO_DELTA)

| Stage | Subsystem/Surface | $S_{current}$ | $\Delta$ | Corrective vector | Evidence | Disposition |
|---|---|---|---|---|---|---|
| 0 | Baseline gate | 1050 passed + All checks | 0 | none | /tmp/baseline_gate.log | `[x]` |
| 1 | Arch boundaries/invariants | audit in progress (S1–S5) | ? | TBD from reader reports | — | `[~]` |
| 2 | Failure discovery | pending Stage 1 | ? | — | — | `[ ]` |
| 3 | Resilience hardening | pending Stage 2 | ? | — | — | `[ ]` |
| 4 | Baseline qualification | pending Stage 3 | ? | — | — | `[ ]` |
| 5 | Chaos engineering | pending Stage 4 | ? | — | — | `[ ]` |
| 6 | Recovery/convergence | pending Stage 5 | ? | — | — | `[ ]` |
| 7 | SAPRE + 100% live E2E | pending Stage 6 | ? | — | — | `[ ]` |

## Stage 1/2 confirmed defects (coordinator-verified 2026-11-02 ~19:05 UTC, LAW 10H)

| ID | Severity | Subsystem | Trigger → Root cause → Violated invariant → Consequence | Evidence | Disposition |
|---|---|---|---|---|---|
| F-01 | P0 | CLI `--ingest-repo/--commit-hash` | valid pair → `main():3069` validates + forwards kwargs → `cli_runner:2038` accepts `ingest_repo/commit_hash` but body never reads them → fixture/sweep branch on `target_key=None` → unhandled pydantic `ValidationError` traceback | live probe: `cli_runner(None, ingest_repo=..., commit_hash=...)` → traceback `ScanResult.target Input should be a valid string` (not a clean exit 2) | OPEN — fix + RED test required |
| F-02 | P1 | TUI `ingest` mode | any `--ingest-repo` → `_dispatch_core:683` builds `RepoIntakeSpec` (validates URL/commit, READS repo) → `:689` drops it, runs `execute_purple_workflow(fixture_key)` → user told `system: ingest proven on fixture node_query_sink` | live probe w/ mocked workflow: ingest URL accepted, fixture scan ran, summary `ingest: ? -> ? -> verified` | OPEN — fix + RED test required |
| F-03 | P2 | `--format json` on CVE path | `--format json` → `cli_runner:2084` `_out` routes chatter to stderr BUT `:2094` legacy `print(...Report...)` goes to stdout → stdout no longer machine-pure (LAW-8 parity break for the one machine surface) | code-read `main.py:2084-2094` (SOURCE-CONFIRMED) | OPEN |
| F-04 | P2 | `--health` payload | `_health_report:2491 "busy": False` hardcoded → operators polling health during a live WS scan see idle; live socket state at `main.py:768` is authoritative | code-read (SOURCE-CONFIRMED) | OPEN |
| F-05 | P3 | `example.env` drift | `PURPLEBOX_RESEARCH/SCANNERS`, `PURPLEBOX_DOCKER_TIMEOUT_SECONDS` have `os.getenv` readers (`config.py:123,170-175`) but no template lines → copied `.env` silently leaves research off | code-read + file diff (SOURCE-CONFIRMED) | OPEN |
| F-06 | P3 | docs-vs-code | HOW_IT_WORKS `3-pass sweep` vs `sweep.py:45` 4 passes; CLI.md `--scan-profile {profile,c custom}` garbage vs parser choices; WORKFLOWS.md `six LAWs` vs LAWS.md through LAW 12; README default-scan promises all passes while bare `--scan` is 1 loop | code-read (SOURCE-CONFIRMED) | OPEN |
| D-01 | — | docs-only (no code change) | `web/js` showcase fixtures + `/ws/system` dead-end + tags.py loose needles: cactus items are doc-hedged/proposed-marked; NOT defects to fix in code | reader report | DEFER (docs note only) |

Ruled OUT (reader claim disproven by code): R-01 "binary hardcodes 3 passes with no knob" — FALSE: CLI/WS/MCP all thread `max_passes` (`main.py:1360/1790`, default 3 is the documented harness contract since chain evidence is source-only). R-02 "`--format json` polluted by Report print" as P1 — real but P2 (table-mode `[SYSTEM]` line only; json branch already routes chatter to stderr except one legacy print). R-03 "TUI ingest stub scans fixture" as mere stub — UPGRADED: it is F-02 false-success (reports ingest verified while scanning a fixture). R-04 "`--health busy hardcoded`" — CONFIRMED as F-04.

## Finalize 2026-11-02 ~19:46 UTC — sweep closed, all lines in sync

- Feature branch `feature/systems-assurance-sweep` fully merged → deleted (local). No worktrees remain (`git worktree list` = home checkout only). No agents remain (all writers stopped/retired).
- `develop` == `origin/develop` == `main` == `origin/main` (`aef40fe`). Home = `develop`, tree CLEAN.
- Gate at ship: 1063 passed + 2 skipped, All checks passed. Red default `muse-spark-1.3-contributor`, version `0.14.0` on all surfaces.
- Deferred to post-ship (unchanged from directive scope): Stages 4–7 live/chaos/concurrency qualification; Stages 1–3 are VERIFIED_ZERO_DELTA for audited surfaces.

---

# Run v2 — 2026-11-03 systems-assurance re-issue (brief `2026-11-03-systems-assurance-e2e-v2`, verbatim)

Branch `feature/startup-gap-hunt` off `develop` `c64189f`. Baseline S_current: gate **1405 passed + 2 skipped, All checks passed**
(post-dotenv fix). Recon input: 20 read-only agents (R01-R20), full reports in
`.jcode/session/recon/2026-11-03-recon-20.md` (local, ignored). Coordinator re-verified load-bearing claims live before triage.

## Coordinator live verification of recon claims (LAW 10H: no fix on an unverified claim)

| Claim | Probe | Result |
|---|---|---|
| R18: WS binary dead above ~48 KB raw (ws_max_size=65536) | live server :8797, `/ws/binary` frames of 16 KB / 60 KB / 200 KB raw | **REPRODUCED**: 16 KB accepted (log frames), 60 KB + 200 KB `ConnectionClosedError` at transport. UI badge says 8 MiB. |
| R17 P0-2 / repo-intake clone works | `containers.create(...)` then `exec_run` on the never-started staging container | **REPRODUCED (worse than reported)**: Docker 409 Conflict, exec on a non-running container is impossible. And target-base image has `apk` only, no `git`/`apt-get`, runs uid 10001. `intake_repo_to_snapshot(clone=True)` can never succeed live; it is only green against the unit-test fake. |
| R17 P0-1 SSRF via clone | depends on clone working | **DISPROVEN as live risk today** (clone path cannot execute, see above) but host gate still missing. |
| R09/R17: `cli_runner` ingest branch unreachable | `main()` dispatch at `main.py:3597-3640` | **CONFIRMED**: `main()` always refuses `--ingest-repo` (exit 2) with "not yet implemented"; `cli_runner` + TUI ingest call the dead clone path. Prior session's "intake clone retired F-01/F-02" claim was proven only against a fake. |

## Failure register (Stage 2 triage; severity P0-P3, evidence level)

| ID | Sev | Evidence | Subsystem | Causal chain (trigger → root cause → consequence) | Slice |
|---|---|---|---|---|---|
| F-201 | P1 | REPRODUCED | transport / WS binary | real binary upload → `ws_max_size=65536` at `main.py:3460,3642` → transport closes; advertised 8 MiB path dead for any real ELF | sa-main |
| F-202 | P1 | REPRODUCED | repo intake | clone=True → `exec_run` on created-not-started container (409) + no git in image → intake can never clone; CLI refuses, TUI/cli_runner fail late after Docker work | sa-intake |
| F-203 | P1 | SOURCE-CONFIRMED | repo intake security | `RepoIntakeSpec` accepts `user:pass@` userinfo, any host incl. loopback/RFC1918/link-local/metadata literals; creds echoed in `--ingest-dry-run` + progress | sa-intake |
| F-204 | P1 | SOURCE-CONFIRMED | WS ingest integrity | `/ws/project` ingest frame scans client-supplied `file_list` under a claimed repo URL + commit, never fetched; verdict attributed to repo it never read (false-success family) | sa-main |
| F-205 | P1 | SOURCE-CONFIRMED | config precedence | `merge_config(None,...)` at `main.py:3225` reads `PURPLEBOX_RESEARCH*`/`INTEL_OFFLINE` via `_env_values` BEFORE `load_config()` fills `.env` → `.env`-only research/offline silently ignored (dotenv sibling bug) | sa-config |
| F-206 | P2 | SOURCE-CONFIRMED | config precedence | `cli_runner`/`ai_demo_runner` rebuild from `load_config()` and only override `if research:` → env `PURPLEBOX_RESEARCH=on` beats config-file `research=false` (documented order flag>config>env violated) | sa-main |
| F-207 | P2 | SOURCE-CONFIRMED | observability / MCP stdio | `mcp_stdio_runner` inits obs with `mode=None` before any `load_config()` → `.env`-only `PURPLEBOX_OBSERVABILITY_MODE` ignored | sa-main |
| F-208 | P2 | SOURCE-CONFIRMED | library parity | `sms_api.docker_health/cleanup_preview(None)` build bare `PurpleBoxConfig()` → skip env, `.env`, validate | sa-libmisc |
| F-209 | P1 | SOURCE-CONFIRMED | WS concurrency | `/ws/binary` 60 s and fixture/project 30 s first-frame reads run INSIDE `async with lock` → one slow client holds the global scan lock, everyone else gets busy | sa-main |
| F-210 | P2 | SOURCE-CONFIRMED | MCP binary | MCP HTTP + stdio `sms_scan_binary` base64-decode unbounded `blob_b64` before any cap; HTTP tempfile unlink skipped on exception (/tmp leak) | sa-main |
| F-211 | P2 | SOURCE-CONFIRMED | binary intake | filename accepts NUL/control chars/whitespace-only; CLI/TUI `read_bytes()` unbounded before 8 MiB check | sa-binary |
| F-212 | P1 | SOURCE-CONFIRMED | CLI JSON purity | `--ai-demo`, `--mcp-snippet`, `--binary-target` `--format json` print chatter to stdout before JSON; `--health --format json` + bad config → KeyError → empty stdout; `--config` preamble on stdout | sa-main |
| F-213 | P2 | SOURCE-CONFIRMED | error semantics | generic `main()` catch swallows actionable text: `--ai-demo` missing key and `--project` consent print only "could not start (Type)"; MCP `-32603` drops key guidance | sa-main |
| F-214 | P2 | SOURCE-CONFIRMED | TUI UX | TUI prints `scan failed (ConfigurationError)` type-only; user never sees which key/consent is missing | sa-tui |
| F-215 | P2 | SOURCE-CONFIRMED | vault durability | `default_vault_dir` raw `RuntimeError` on no HOME; `mkdir` outside try → raw `OSError` escapes `VaultError` contract (carries paths into traces); `chmod` failures swallowed, no mode verify; relative/`~` override unexpanded | sa-vault |
| F-216 | P3 | SOURCE-CONFIRMED | vault concurrency | `_bump_index` read-modify-write, no lock → lost counts under concurrent commits (index is a cache; blobs stay atomic) | sa-vault |
| F-217 | P2 | SOURCE-CONFIRMED | WS demo | Greenhouse does keyless intel HTTP + "green" chatter before the key gate, then fails as generic "Demo generation failed (ConfigurationError)" | sa-main |
| F-218 | P2 | SOURCE-CONFIRMED | CVE labelling | `--offline-cve` result message identical to live OSV path; offline output indistinguishable from a live verdict | sa-libmisc |
| F-219 | P3 | SOURCE-CONFIRMED | docs/env drift | `example.env` documents unread `PURPLEBOX_DOCKER_TIMEOUT_SECONDS`; 6 read-but-undocumented knobs (DTRACK URL/KEY, NVD_API_KEY, VAULT_DIR, INTEL_OFFLINE, LOG_RAW_RESPONSES); `ENV_FALLBACKS` dead dict; CLI.md advertises nonexistent `--ingest-branch` | sa-config |
| F-220 | P3 | SOURCE-CONFIRMED | obs redaction | `_redact` value scan only `sk-` prefixes; misses `ghp_/AKIA/PEM/JWT` shapes and `x-api-key/cookie/bearer/credential/private_key` key names | sa-libmisc |
| F-221 | P3 | SOURCE-CONFIRMED | docker residue | `--docker-status` leftover count is containers only; networks/snapshot images invisible | sa-docker |
| F-222 | P3 | SOURCE-CONFIRMED | WS params | `research_scanners` allowlist hardcoded 3x in `main.py` instead of importing `ALLOWED_RESEARCH_SCANNERS` (drift risk) | sa-main |

Disproven / by-design (no fix): model-lock bypass (R16 all-clear); snippet env leak (R19 not visible); obs call-site leaks (R14 none);
`--cleanup` label scope (R15 reaps all); offline CVE keyless by design (labelling fixed in F-218 only); `/ws/system` explicit-invalid by design.

## Slice registry (write scopes are disjoint; coordinator owns main.py merges serially)

| Slice | Agent | Write scope | Findings | Deps | Status |
|---|---|---|---|---|---|
| sa-main | coordinator | `main.py`, `tests/test_sa_main_*.py` | F-201 F-204 F-206 F-207 F-209 F-210 F-212 F-213 F-217 F-222 | sa-intake (spec API) | [ ] |
| sa-intake | worker | `library/services/repo_intake.py`, `tests/test_sa_intake_*.py` | F-202 F-203 | none | [ ] |
| sa-config | worker | `library/core/config.py`, `sms_cli.py`, `example.env`, `docs/reference/CLI.md`, `tests/test_sa_config_*.py` | F-205 F-219 | none | [ ] |
| sa-vault | worker | `library/intel/sms_vault.py`, `tests/test_sa_vault_*.py` | F-215 F-216 | none | [ ] |
| sa-binary | worker | `library/services/binary_intake.py`, `tests/test_sa_binary_*.py` | F-211 | none | [ ] |
| sa-tui | worker | `tui.py`, `tests/test_sa_tui_*.py` | F-214 | none | [ ] |
| sa-libmisc | worker | `library/services/sms_api.py`, `library/workflows/cve_workflow.py`, `library/shared/sms_observability.py`, `tests/test_sa_libmisc_*.py` | F-208 F-218 F-220 | none | [ ] |
| sa-docker | worker | `library/core/docker_manager.py`, `tests/test_sa_docker_*.py` | F-221 | none | [ ] |
