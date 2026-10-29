# ARCHITECTURE — Secure Mitigation System (production deep dive)

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

This is the dense production-level companion to the executive pitch in
[`README.md`](../README.md). Anything here is load-bearing engineering detail:
wave specs, receipts, guards, isolation mechanics, and the module map.

## Contents

- [The evidence-gated loop](#the-evidence-gated-loop)
- [Wave 2 (0.3.0, shipped 0.4.0)](#wave-2-030-shipped-040)
- [Wave 5: trust signals (shipped)](#wave-5-trust-signals-shipped)
- [Wave 7-8: live signals + property contracts (shipped)](#wave-7-8-live-signals--property-contracts-shipped)
- [Wave 2 (SPEC 14.8)](#wave-2-spec-148)
- [Wave 5 (SPEC 14.9)](#wave-5-spec-149)
- [What is implemented](#what-is-implemented)
- [Configuration](#configuration)
- [Isolation](#isolation)
- [Tests and acceptance](#tests-and-acceptance)
- [Project map](#project-map)

## The evidence-gated loop

One loop, evidence-gated (`modules/workflows/workflow.py:build_verdict_receipt`, `modules/workflows/project_workflow.py:build_cycle_receipt`):

- **Red proves it.** A probe runs in an air-gapped container; exit `0` = boundary reached, `1` = blocked, `2` = inconclusive, fail-closed.
- **Blue fixes only the boundary.** Sanitization-only patch under a 60-line budget (`modules/core/patches.py:EDIT_BUDGET_LINES`); rejected patches carry the firing guard (`project_workflow.py:GuardRationale`).
- **Regression re-proves it.** Trusted normal-input checks re-run on original and patched targets; equal pass/fail class required (`project_workflow.py:differential_passed`), plus opt-in property gate (`property_gate_passed`) and 4-seed mutation gate (`modules/core/checks.py:MUTATION_SEED=20261029`, `mutation_gate_passed`).
- Only all-green is `verified`/`retained`; every verdict ships a machine-readable receipt (`workflow.py:export_receipt_json`, `project_workflow.py:export_cycle_receipt_json`) pinning the exits and `patch_sha256`.

Zero-day triage edge (`modules/workflows/cve_workflow.py`, flags `main.py --cve-scan/--fast-lane/--deep-assessment/--offline-cve`):

- **Reachable+fixable first.** `_fast_lane_rank` orders `(-reach_score, fix availability, kev_listed, epss_percentile, id)`; `_queue_evidence` prints the auditable tie-break `reach:{n} fix:{v} kev:{...} epss:{...}`.
- **Freshness stamps.** KEV/EPSS signals carry `kev_date`/`epss_date`; older than `_SOURCE_FRESH_DAYS=1` read as absent, fail-closed. `FAST_LANE_EXCLUDED_SOURCES={euvd}` keeps unverified feeds out of the fast lane.
- **Frozen inputs.** Mutation pools assert `FROZEN_MUTATION_POOL_SHA256` (`modules/core/checks.py`), so a re-run reproduces byte-identical inputs.

Hardening posture (`ZERO_DAY_BLUEPRINT.md:77-81`): SHIP = probe loop, guards, differential, topping, freshness, fast lane. LABEL = property (opt-in), mutation (shape check), templates (small diffs). CUT = frozen-pool digest hygiene, receipt JSON, rationale text, demo/greenhouse, scanners/sidecars, dashboard chrome — documentation labels, not deletions.

## Wave 2 (0.3.0, shipped 0.4.0)

- **Reachability-ranked CVE output.** CVE scans attach `reach_score` (deterministic 0-100) plus `reach_evidence`, fusing OSV fixed-version ranges with static sink adjacency — keyless, no inference.
- **CVE disclosure fast lane.** `--fast-lane` runs static + OSV only, in deterministic order, with no Muse or NVD calls.
- **Tunable AI demos.** Greenhouse takes `--demo-size small|standard`, `--flaw-count 1..8`, and `--demo-seed`; the dashboard exposes the same as Demo size / Flaw count / Demo seed controls.
- **Ghost-probe liveness for inconclusive probes.** The post-probe liveness check against the still-running target now covers inconclusive (`exit 2`) probes as well as blocked (`exit 1`) ones, so a crashed service cannot earn success.

## Wave 5: trust signals (shipped)

- **GHSA CVE-id lookup fix.** `ghsa_lookup_by_cve` queries `?cve_id=` (the old path sent CVE ids as `?package=`, silently degrading results); records now consume embedded `epss`, `cvss_severities` (v4 preferred), and `first_patched_version`. Never-raises preserved.
- **KEV as fifth signal.** CISA KEV keyless JSON joins `cve_records` (exploited flag + due date); KEV/EPSS-percentile likelihood is tie-breaking evidence in `reachability_score` and never lowers the fail-closed sink/fixed-version floor.
- **Differential normal-contract gate.** After patch + probe-block, trusted normal-input checks re-run against original and patched targets; equal pass/fail class required, recorded as explicit `CycleEvidence.differential_passed`, mismatch = not verified.
- **Fast-lane tiering.** Output orders by actionability `(-reach_score, fix availability, id)` instead of id-sort alone. Gate: `dev.py check` 367 passed.

## Wave 7-8: live signals + property contracts (shipped)

- **KEV/EPSS via the real producer path.** `kev_listed`/`epss_percentile` are now wired through `cve_workflow` enrichment into `reachability_score` (previously Wave 5 tests stubbed the summary dict, so the dead `summarize_osv_vuln` path was invisible). Tie-break only; never lowers the fail-closed sink/fixed-version floor.
- **Per-process KEV catalog cache.** `research.kev_lookup` fetches the CISA catalog once per process instead of per CVE id; fail-first cache test in `tests/test_scanners.py`.
- **Property/metamorphic normal-contract checks.** Seeded deterministic scripts (`checks.project_property_script`, seed `20261029`) run after regression green and veto a retain on any non-zero exit (`property_gate_passed`); exceptions resolve to exit 2, fail-closed. Opt-in by contract first line naming the check id; anything else skips, so arbitrary projects are unaffected.
- **Split scripts by real response shape.** `node_query_sink` asserts the JSON envelope; `project_lookup_text` asserts the plain-text contract (exact names for known ids, empty 200 body for seeded random ids); PHP hosts assert byte-stability under repetition; config keys assert idempotent re-read.
- **LOW bundle.** Research fetch caps, EPSS sanitizer reuse, `intel_search` CVE shape. Gate: `dev.py check` 392 passed; live `project_scan` 2/2 retained with properties exit 0.

## Wave 2 (SPEC 14.8)

- **Verdict receipts.** Every verified fixture cycle records a `VerdictReceipt` (`modules/workflows/workflow.py`: `fixture`, `pre_exit_code`, `post_exit_code`, `regression_passed`, `differential_passed`, `property_exit_code`, `property_passed`, `patch_sha256`, `verified`; built by `build_verdict_receipt`, serialized by `export_receipt_json`); every retained project cycle records a `CycleReceipt` (`modules/workflows/project_workflow.py`: `fixture`, `pre_probe_exit`, `post_probe_exit`, `baseline_regression_exit`, `patched_regression_exit`, `differential_passed`, `property_exit`, `property_passed`, `patch_sha256`, `retained`; built by `build_cycle_receipt`, serialized by `export_cycle_receipt_json`, carried on `ProjectCycleReport.receipt`) exported alongside the candidate patch. Novelty: Dependabot/Snyk emit version-bump PRs with notes, we emit machine-readable exit-0/exit-1 execution receipts, advancing evidence-over-opinion verdicts. Same-day: a reviewer accepts the patch today because the receipt pins exactly which Docker exits the claim rests on.
- **Guard rationale.** Rejected patches carry a structured `GuardRationale` (`guard_id`, `reason`, `trigger`) on `ReplacementValidation.guard_rationale` (`modules/workflows/project_workflow.py`). Novelty: Semgrep/Snyk Code emit AI draft fixes for human/rescan validation, we bind the fired guard and its trigger to each rejected patch, advancing reviewer-legible safe-patch shapes. Same-day: the reviewer sees why the safe patch is the shape it is, with no guard-guessing round trip.
- **Fast-lane topping.** `_fast_lane_rank` (`modules/workflows/cve_workflow.py`) orders reachable+fixable first — `(-reach_score, fix availability, kev_listed, epss_percentile, id)` — and `_queue_evidence` surfaces the auditable tie-break string `reach:{n} fix:{v} kev:{listed|absent} epss:{pct|absent}` read from `reach_score` / `fixed_versions` / `kev_listed` / `epss_percentile`. Novelty: NVD/OSV/EUVD rank by CVSS, we top reachable+fixable with KEV/EPSS evidence strings, advancing day-zero queue auditability. Same-day: the team patches reachable+fixable CVEs first, in an order anyone can re-derive.
- **Mutation probes.** `modules/core/checks.py` runs N=4 (`MUTATION_COUNT = 4`) deterministic seeded (`MUTATION_SEED = 20261029`) per-contract mutations, fail-closed through `mutation_gate_passed` (exit 0 = held, 1 = mishandled, 2 = inconclusive): node shares one capped run via `project_property_mutation_script`, php/mysql run standalone via `project_mutation_script`, dispatched by `mutation_fixture_supported`. Novelty: open-ended fuzzers chase coverage with unbounded runs, we run four seeded contract mutations inside the existing capped check, advancing bounded boundary-shape confidence. Same-day: shape regressions in the patched target fail the cycle the day the patch lands, not after merge.

## Wave 5 (SPEC 14.9)

- **queue_evidence freshness.** `_queue_evidence` (`modules/workflows/cve_workflow.py`) gates KEV/EPSS signals through `_source_fresh` (`_SOURCE_FRESH_DAYS = 1`): per-source date stamps (`kev_date`, `epss_date`) older than 1 day read as absent — fail-closed, never blocks the scan — and `FAST_LANE_EXCLUDED_SOURCES` keeps EUVD out of the fast lane (no keyless JSON endpoint verified 2026-10-29). Novelty: CVSS-ranked feeds reuse stale exploit-probability vintages, we stamp each source date and drop day-old signals from the queue string, advancing triage-time freshness. Same-day: the team queues reachable+fixable CVEs today on signals stamped today, not last month's EPSS.
- **Frozen-pool mutation inputs.** `modules/core/checks.py` pins every mutation id behind `FROZEN_MUTATION_POOL_SHA256`: pools are byte-identical across runs, with no live generative loop in-container (any offline pool proposal must freeze+seed before use). Novelty: generative red loops invent new cases per run and cannot re-derive a verdict, we freeze the seeded pool and assert its digest, advancing re-derivable boundary evidence. Same-day: a re-run today reproduces byte-identical mutation inputs, so a green gate means the same thing it meant yesterday.
- **Guard-discipline template inputs.** Template-shaped inputs are allowed only inside the existing 60-line sanitization guards (`EDIT_BUDGET_LINES = 60`, `modules/core/patches.py`); the budget never widens and `is_solver_synthesized_shape` rejects solver-synthesized edits with a bound `GuardRationale`. Novelty: AI-fix tools accept solver-shaped rewrites and grow the diff to fit, we hold template inputs inside the fixed 60-line budget and name the rejecting guard, advancing reviewer-legible safe-patch shapes. Same-day: the reviewer sees a small template-shaped diff today with the fired guard attached, not a re-architected file.

## What is implemented

| Component | Behavior |
| --- | --- |
| CLI + FastAPI | Shared async workflow, localhost binding, one active UI scan per process |
| Dashboard | Local-only assets, split red/blue traces, arena comms, cancel, report download |
| Three fixtures | Node dynamic-expression sink, PHP local command argument, MySQL config audit |
| Local projects | Bounded immutable snapshots, user-supplied offline runtime and regression commands |
| Repeated red/blue cycles | Fresh role contexts, structured handoffs, original-probe rechecks, rollback of failed candidates |
| Large-project context | Explicit bounded source batches and coverage records, never one growing conversation |
| Docker lifecycle | Two pre-built images; isolated target/verifier; immutable per-session snapshots |
| Resource controls | Non-root, dropped caps, no-new-privs, CPU/RAM/PID caps, read-only roots, bounded `/tmp` |
| Patch guard | Required notices, small-diff budget, protected lines, exact MySQL allowlist |
| Verification | Trusted normal-input checks before/after; explicit 0/1/2 verifier semantics |
| Research sidecars | Opt-in red/blue Muse researchers over OSV/CIRCL/GHSA/EPSS + 5 local scanners |
| Testability | Mocked unit tests, live Docker/API self-tests, headless-browser E2E (Chrome/Firefox) |
| Cleanup | Resource tracking, cancellation-aware worker joins, cleanup independent of UI logging |

The PHP fixture uses `printf` for a deterministic local diagnostic (no external requests). The MySQL fixture is a served config file — no database server is started.

## Configuration

All inference goes through `agents.MetaMuseClient`: HTTPX against Meta's compatible `/chat/completions` endpoint, strict Pydantic response validation, bounded response size, no redirects, no fallback provider. Only Muse Spark/Wonder IDs and `meta-models/muse-spark-open[-suffix]` validate. **Verified default:** red `muse-spark-1.3`, blue `muse-wonder-1.0`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `META_MUSE_API_KEY` | unset | Meta Model API key (`dev.meta.ai`). Required for scans |
| `META_MUSE_BASE_URL` | `https://api.meta.ai/v1` | Meta Model API. Baseten/Modal allowed for the open model |
| `META_MUSE_RED_MODEL` | `muse-spark-1.3` | Boundary analysis |
| `META_MUSE_BLUE_MODEL` | `muse-wonder-1.0` | Sanitization patch generation |
| `META_MUSE_TIMEOUT_SECONDS` | `180` | Per-request API timeout, 1–300 s |
| `META_MUSE_MAX_TOKENS` | `32768` | Output budget, 1024–131072. **Reasoning tokens count toward it** |
| `META_MUSE_REASONING_EFFORT` | unset | `minimal` / `low` / `medium` / `high` / `xhigh` / `max`. Unset = model default |
| `PURPLEBOX_RESEARCH` | `off` | `on` enables research sidecars (extra model calls, host network only) |
| `PURPLEBOX_RESEARCH_SCANNERS` | unset | Comma list: `trivy,grype,osv-scanner,dependency-check,dependency-track` |
| `PURPLEBOX_DTRACK_URL` / `PURPLEBOX_DTRACK_API_KEY` | unset | Dependency-Track server (both required to enable) |
| `NVD_API_KEY` | unset | Optional; raises NVD / Dependency-Check rate limits |
| `PURPLEBOX_VERIFIER_TIMEOUT_SECONDS` | `20` | Per-verifier execution limit, 1–120 s |
| `PURPLEBOX_INFERENCE_MODE` | `hosted` | `hosted` needs a key + project-source consent; `local` pins inference to loopback |

> The hackathon open model `meta-models/muse-spark-open-1026` is not served by `api.meta.ai` (404) — it needs a hosted provider, e.g. Baseten (`META_MUSE_BASE_URL=https://inference.baseten.co/v1`). The original spec's `muse-code` ID is **Meta's coding agent, not a model** — this implementation uses the documented Muse Spark/Wonder IDs ([quickstart](https://dev.meta.ai/docs/quickstart)).

## Isolation

Source is injected via Docker tar archives into **stopped, never-executed staging containers** with networking disabled, then committed; runtimes start from those snapshots with read-only roots. No host mounts, socket mounts, exposed ports, or inherited proxies. Base images persist; per-session snapshots, containers, and networks are removed after every scan.

> Docker `internal=True` blocks normal external routing but **does not guarantee that host gateway services are unreachable**. Containers also share the host kernel ([Docker docs](https://docs.docker.com/reference/cli/docker/network/create/#network-internal-mode---internal)). Project networks additionally require Docker's isolated gateway mode to avoid assigning a host bridge address. Use a disposable VM or stronger sandbox before pointing this at hostile repositories.

The model verifier must explicitly exit `0` (boundary observed), `1` (blocked), or `2`/other (inconclusive → error, never a fix). Python exceptions and implicit completion convert to `2`. Regression checks re-run after the final probe to catch a broken target. Cancellation waits for in-flight Docker calls, then cleans up; daemon outages, host termination, and SIGKILL can leave resources behind (session label `purplebox.session=<id>`; the app never prunes unrelated Docker resources). This is finite evidence, not proof of security — review every candidate.

## Tests and acceptance

```bash
python3 .jcode/tools/dev.py check   # the full gate: lint, format, tests, fixtures
python test_harness.py --docker     # live Docker (needs base images, no key)
python test_harness.py --api        # two real Muse calls (normal usage cost)
.venv/bin/python .jcode/tools/ui_scan.py node_query_sink --offline --browser firefox
```

Default tests are mocked (no Meta/Docker contact). See [`archive/VALIDATION.md`](archive/VALIDATION.md) for the acceptance runs and [`guides/DEVELOPMENT.md`](guides/DEVELOPMENT.md) for the environment, traps, and the browser matrix (Chrome/Chromium/Edge/Brave via CDP, Firefox via WebDriver).

<details>
<summary><strong>Latest acceptance evidence (2026-10-28)</strong></summary>

- Full gate green on `develop` (lint, format, unit tests, fixture/schema harness, `--list-targets`).
- Real Muse plus real Docker: a generated acceptance fixture scanned end to end with Spark red / Wonder blue — probe demonstrated expression evaluation over HTTP, the patched snapshot blocked it, regressions passed, cleanup succeeded.
- Real Firefox dashboard over WebSocket loopback: both cycles completed with retained patches, all seven pipeline stages done, report and `candidate.patch` downloads matched server evidence byte-for-byte.
</details>

## Project map

```text
modules/core/agents.py      Muse transport, strict schemas, red/blue + research methods
modules/core/prompts.py     Red/blue/research task contracts
modules/core/config.py      Env validation, model lock, PURPLEBOX_RESEARCH* gates
modules/workflows/workflow.py          Baseline → probe → patch → regression → cleanup
modules/intel/research.py   Keyless intel transport (OSV/CIRCL/GHSA/EPSS)
modules/intel/scanner_binaries.py      Trivy / Grype / OSV-Scanner / Dependency-Check wrappers
modules/intel/scanner_dtrack.py        Dependency-Track BOM upload client
modules/services/personas.py          Agent personas (tone only, safety rules override)
modules/services/chatter.py Safe server-built team chatter summaries
main.py                     CLI (--scan/--project/--research/--ai-demo), FastAPI, WebSocket
modules/core/registry.py    Fixture registry + normal-behavior contracts
modules/services/projects.py           Arbitrary project intake, validation, sandbox execution
modules/workflows/project_workflow.py  Red/blue cycles, handoffs, regression, final reports
modules/services/project_agents.py     Project-scoped Muse roles + bounded source batches
modules/core/scan_profiles.py          Cycle profiles (economy/balanced/quality/custom)
modules/intel/intel_search.py          NVD CVE lookup for deep scans + demo intel
modules/workflows/cve_workflow.py     CVE scan workflow; deep_scan.py deep static CVE scan
modules/services/demo_gen.py           AI-built demo project generation
modules/core/patches.py     Patch guards, unified diffs
modules/core/docker_manager.py         Images, isolated runtimes, deadlines, cleanup
modules/core/checks.py      Normal-input + egress checks
static/                     Dashboard (app.js, index.html, app.css)
targets/                    Three intentionally vulnerable fixtures
tests/                      Unit + API tests
.jcode/tools/               dev.py, offline_scan.py, ui_scan.py, scans
docs/                       guides/, architecture/, reference/, decisions/ (see index.md)
AGENTS.md                   Contributor working agreement (branch law, invariants)
TODO.md                     The work queue
```

See [`AGENTS.md`](../AGENTS.md) for the contributor contract — feature branches only, never work in `main` or `develop` — and [`TODO.md`](../TODO.md) for what is next. Full doc map: [`index.md`](index.md).
