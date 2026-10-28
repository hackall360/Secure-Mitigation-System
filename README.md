# Secure Mitigation System

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

An autonomous **red/blue input-boundary verification harness**: a red-team AI
finds an input-handling weakness, an isolated Docker sandbox proves it, a
blue-team AI writes a minimal sanitization patch, and trusted regression checks
confirm the boundary holds — then every container is removed. A FastAPI
dashboard and a CLI share one evidence-gated workflow.

Built for Meta's **Muse** models — and that choice is load-bearing, not branding
(see [Why Muse](#why-muse-models-are-required)).

## How it works

```text
fixture source
  │  baseline: trusted normal-input checks (must pass)
  ▼
RED agent (Muse) ──► finding + verification probe (Python, stdlib only)
  │  sandbox probe: exit 0 = boundary reached · 1 = blocked · 2 = inconclusive
  ▼
BLUE agent (Muse) ──► minimal sanitization patch (guarded diff)
  │  fresh clone of the patched snapshot → regression checks → probe re-run
  ▼
verified / not_confirmed / rejected / failed  →  full Docker cleanup
```

Only `verified` means the probe reached the sink before the patch, normal
behavior held throughout, and the probe is blocked after. Anything
inconclusive fails closed. Original fixture files are never overwritten.

## Why it matters

- **Evidence, not opinion.** Every claim about a boundary is a container exit
  code, not a model assertion. The model proposes; Docker disposes.
- **Minimal, reviewable fixes.** Conservative patch guards (small-diff
  budget, protected-line preservation, exact allowlists) keep candidates
  auditable. Review every candidate before applying it.
- **Safe by construction.** Air-gapped sandboxes, non-root users, dropped
  capabilities, CPU/RAM/PID caps, read-only roots, redacted artifacts with
  owner-only permissions, no secrets in Docker/reports/UI.
- **Research-grounded, optionally.** Opt-in research sidecars (red + blue
  Muse agents) ground reasoning in live CVE intel from keyless public
  sources (OSV, CIRCL, GitHub Advisory, EPSS) plus local scanners (Trivy,
  Grype, OSV-Scanner, Dependency-Check, Dependency-Track). Intel is always
  untrusted data — Docker evidence still decides.

## Why Muse models are required

Most mainstream frontier models ship with guardrails that refuse red-team
work outright: they will not analyze an injection sink, will not write a
boundary probe, and will not discuss exploit mechanics even in a sandboxed,
defensive context. That makes a system like this nearly impossible to build
on them — roughly 90% of this project's development loop (red analysis,
probe authoring, patch reasoning about live sink behavior) is the exact
category those guardrails block.

Muse takes a different and, for security engineering, better approach. The
safety restrictions are deliberately lighter: instead of refusing security
work, Muse trusts the developer to scope it. The safety perspective shifts
from the provider hand-holding the developer to the developer owning the
environment — which is precisely correct here, because this system already
owns the environment: probes run in disposable, network-disabled containers
as non-root with capped resources, and every artifact is redacted. The model
is allowed to do genuine offensive reasoning *because the harness around it
is genuinely contained*.

In practice, that means Muse Spark can dissect a dynamic-expression sink
and author a working boundary probe, and Muse Wonder can reason about the
minimal sanitization that blocks it — in one session, without refusal
dance, jailbreaks, or euphemism. Spark runs analysis at roughly a fifth of
Wonder's output-token cost, so the red/blue split is economical as well as
effective.

None of this is an excuse to be careless: lighter provider guardrails mean
*our* guardrails must be stronger, and they are (see [Isolation](#isolation)
below). But for security-intensive applications built in the open, Muse's
posture — capable models, developer-owned safety, containment over refusal —
is what makes this project possible at all.

## Quick start

Requires Python 3.12+, Docker Engine/Desktop with Linux containers, and a
Meta Model API account with access to the configured Muse models. Image
initialization downloads Alpine packages; scan containers never install
dependencies or publish host ports.

```bash
python3 .jcode/tools/dev.py setup   # reproducible venv, hash-locked deps
source .venv/bin/activate           # Windows: .venv\Scripts\Activate.ps1

# No API key needed for these:
python main.py --list-targets
python main.py --init-images
python main.py --serve --port 8000
```

Open **http://127.0.0.1:8000**. The dashboard loads without Docker or a key
and explains missing setup. Stop the server before changing its environment.

To enable inference, copy `example.env` to `.env`, add your key, and export it:

```bash
cp example.env .env   # edit: META_MUSE_API_KEY=...
set -a; source .env; set +a
python main.py --serve --port 8000
```

`.env` is git-ignored, created owner-only (0600), and **never loaded
automatically**. No keys are sent to Docker, written to reports, returned by
health checks, or displayed in the UI. A real scan sends the selected fixture
source to the configured Muse endpoint.

```bash
python main.py --scan node_query_sink --output-dir reports
python main.py --scan php_command_sink --profile economy
python main.py --scan node_query_sink --research --research-scanners trivy,grype
```

CLI exit status is `0` only for a verified candidate with successful cleanup,
`1` for all other outcomes, `130` for interruption. `--output-dir` creates a
fresh run folder with `report.json` and, when available, `candidate.patch`.
Reports can contain source code, model output, and candidate patches.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `META_MUSE_API_KEY` | unset | Meta Model API key from dev.meta.ai. Required for scans |
| `META_MUSE_BASE_URL` | `https://api.meta.ai/v1` | Meta Model API. Baseten/Modal allowed for the open model |
| `META_MUSE_RED_MODEL` | `muse-spark-1.3` | Boundary analysis |
| `META_MUSE_BLUE_MODEL` | `muse-wonder-1.0` | Sanitization patch generation |
| `META_MUSE_TIMEOUT_SECONDS` | `180` | Per-request API timeout, 1–300 s (a real blue call took 60+ s) |
| `META_MUSE_MAX_TOKENS` | `32768` | Output budget, 1024–131072. **Reasoning tokens count toward it** |
| `META_MUSE_REASONING_EFFORT` | unset | `minimal`/`low`/`medium`/`high`/`xhigh`/`max`. Unset = model default |
| `PURPLEBOX_RESEARCH` | `off` | `on` enables research sidecars (extra model calls, host network only) |
| `PURPLEBOX_RESEARCH_SCANNERS` | unset | Comma list: `trivy,grype,osv-scanner,dependency-check,dependency-track` |
| `PURPLEBOX_DTRACK_URL` / `PURPLEBOX_DTRACK_API_KEY` | unset | Dependency-Track server (both required to enable) |
| `NVD_API_KEY` | unset | Optional; raises NVD/Dependency-Check rate limits |
| `PURPLEBOX_VERIFIER_TIMEOUT_SECONDS` | `20` | Per-verifier execution limit, 1–120 s |

All inference goes through `agents.MetaMuseClient`: HTTPX against Meta's
compatible `/chat/completions` endpoint, strict Pydantic response validation,
bounded response size, no redirects, no fallback provider. Only Muse
Spark/Wonder IDs and `meta-models/muse-spark-open[-suffix]` are accepted.

**Verified default:** red `muse-spark-1.3`, blue `muse-wonder-1.0`. Spark is
~5x cheaper per output token, so it analyzes and Wonder patches; Spark for
both roles also verified. **Hackathon open model:** `meta-models/muse-spark-open-1026`
is not served by `api.meta.ai` (404) — it needs a hosted provider, e.g.
Baseten (`META_MUSE_BASE_URL=https://inference.baseten.co/v1`).

The original spec used `muse-code` as a model ID — **Muse Code is Meta's
coding agent, not a model**. This implementation uses the documented Muse
Spark/Wonder IDs. See Meta's [quickstart](https://dev.meta.ai/docs/quickstart).

## What is implemented

| Component | Behavior |
| --- | --- |
| CLI + FastAPI | Shared async workflow, localhost binding, one active UI scan per process |
| Dashboard | Local-only assets, split red/blue traces, arena comms, cancel, report download |
| Three fixtures | Node dynamic-expression sink, PHP local command argument, MySQL config audit |
| Docker lifecycle | Two pre-built images; isolated target/verifier; immutable per-session snapshots |
| Resource controls | Non-root, dropped caps, no-new-privs, CPU/RAM/PID caps, read-only roots, bounded `/tmp` |
| Patch guard | Required notices, small-diff budget, protected lines, exact MySQL allowlist |
| Verification | Trusted normal-input checks before/after; explicit 0/1/2 verifier semantics |
| Research sidecars | Opt-in red/blue Muse researchers over OSV/CIRCL/GHSA/EPSS + 5 local scanners |
| Testability | Mocked unit tests, live Docker/API self-tests, headless-browser E2E (Chrome/FF) |

The PHP fixture uses `printf` for a deterministic local diagnostic (no
external requests). The MySQL fixture is a served config file — no database
server is started.

## Isolation

Source is injected via Docker tar archives into **stopped, never-executed
staging containers** with networking disabled, then committed; runtimes start
from those snapshots with read-only roots. No host mounts, socket mounts,
exposed ports, or inherited proxies. Base images persist; per-session
snapshots, containers, and networks are removed after every scan.

Docker `internal=True` blocks normal routing but **does not guarantee host
gateway services are unreachable**, and containers share the host kernel. Use
a disposable VM or stronger sandbox before pointing this at hostile
repositories. No claim of complete air-gapping or measured performance.

The model verifier must explicitly exit `0` (boundary observed), `1`
(blocked), or `2`/other (inconclusive → error, never a fix). Python
exceptions and implicit completion convert to `2`. Regression checks re-run
after the final probe to catch a broken target. This is finite evidence, not
proof of security — the verifier can be wrong. Review every candidate.

Cancellation waits for in-flight Docker calls, then cleans up. Daemon
outages, host termination, and SIGKILL can leave resources behind; failures
identify the session label `purplebox.session=<id>` (the app never prunes
unrelated Docker resources).

## Tests

```bash
python3 .jcode/tools/dev.py check   # the full gate: lint, format, tests, fixtures
python test_harness.py --docker     # live Docker (needs base images, no key)
python test_harness.py --api        # two real Muse calls (normal usage cost)
.venv/bin/python .jcode/tools/ui_scan.py node_query_sink --offline --browser firefox
```

Default tests are mocked (no Meta/Docker contact). See `VALIDATION.md` for
scaffolding runs and `docs/DEVELOPMENT.md` for the environment, traps, and
the browser matrix (Chrome/Chromium/Edge/Brave via CDP, Firefox via
WebDriver).

## Project map

```text
agents.py            Muse transport, strict schemas, red/blue + research methods
prompts.py           Red/blue/research task contracts
config.py            Env validation, model lock, PURPLEBOX_RESEARCH* gates
workflow.py          Baseline → probe → patch → regression → cleanup
research.py          Keyless intel transport (OSV/CIRCL/GHSA/EPSS)
scanner_binaries.py  Trivy / Grype / OSV-Scanner / Dependency-Check wrappers
scanner_dtrack.py    Dependency-Track BOM upload client
main.py              CLI, FastAPI, WebSocket entry points
registry.py          Fixture registry + normal-behavior contracts
patches.py           Patch guards, unified diffs
docker_manager.py    Images, isolated runtimes, deadlines, cleanup
checks.py            Normal-input + egress checks
static/              Dashboard (app.js, index.html, app.css)
targets/             Three intentionally vulnerable fixtures
tests/               Unit + API tests
.jcode/tools/        dev.py, offline_scan.py, ui_scan.py, scans
docs/                DEVELOPMENT.md, PROJECTS.md, SCAN_PROFILES.md, ...
AGENTS.md            Contributor working agreement (branch law, invariants)
TODO.md              The work queue
```

See `AGENTS.md` for the contributor contract — feature branches only, never
work in `main` or `develop` — and `TODO.md` for what is next.

## Acceptable use, warnings, and disclaimer

This is a **defensive cybersecurity research project**. Its purpose is to
verify that a specific input boundary is enforced and to propose a minimal
sanitization that preserves normal behavior — nothing more.

**Intended use only:**

- Verifying input-handling boundaries in code you own or are authorized to test.
- Studying red/blue remediation workflows in isolated, disposable sandboxes.
- Evaluating AI-assisted patch review under evidence-gated, human-supervised conditions.

**Not intended, not permitted:**

- This system is **not a pure red-team tool**. It is not built, licensed, or
  supported for discovering or exploiting vulnerabilities in systems you do
  not own or lack explicit authorization to test.
- This system is **not a pure blue-team shield**. A `verified` result is
  finite evidence from a fixed set of probes, not proof of security,
  correctness, or behavioral equivalence. It must never be treated as a
  guarantee that a system is safe.
- **No guarantee of safety or security is provided.** Sandboxes can be
  escaped, verifiers can be wrong, patches can introduce new faults, and
  model output can be mistaken. The isolation measures here are
  defense-in-depth for a research scaffold, not a production security boundary.
- **Do not repurpose this software for misuse.** Adapting, extending, or
  reconfiguring any part of this system — red-team prompts, probe execution,
  sandbox controls, intel fetching — to attack, intrude upon, surveil, or
  degrade systems without authorization is prohibited, regardless of license
  terms that might otherwise permit modification.
- **Do not remove or weaken the safety controls.** The sandbox restrictions,
  patch guards, artifact redaction, permission controls, and fail-closed
  semantics are load-bearing. Running scans with weakened containment, or
  pointing the harness at code or infrastructure outside your authority,
  voids any expectation of safe operation.

**Provided as is.** This software is supplied without warranty of any kind,
express or implied, including fitness for a particular purpose. The authors
and contributors accept no liability for loss, damage, or unauthorized
activity arising from its use or modification. Operating this system —
including any outbound network activity from research sidecars or local
scanners — is done at your own risk and under your own authority and
responsibility. Comply with all applicable laws and authorization
requirements in your jurisdiction; if you are unsure whether a use is
authorized, do not proceed.

**Human supervision is required.** Every candidate patch must be reviewed by
a qualified person before application. Automated outputs of this system must
never trigger unattended changes to production systems.

Licensed under [PolyForm Noncommercial 1.0.0](LICENSE.md).
