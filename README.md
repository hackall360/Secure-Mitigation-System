# PurpleBox

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

Pre-production security mitigation for the **Meta Global AI Developer Hackathon**.
Scan a local source repository through the CLI or dashboard, not just the three
bundled demonstrations. Each cycle separates **red discovery and proof → blue
sanitization proposal → red re-verification → blue final report**. Repeated cycles
carry forward verified candidate changes inside the sandbox, never into your source tree.

This is a defensive review tool, not a proof of security or a VM-grade boundary
for actively hostile code. Review every candidate patch before applying it.

## Development setup

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the reproducible virtual
environment, hash-locked dependencies, Docker builds, live fixture tests, and
localhost smoke checks. Start with `python3 .jcode/tools/dev.py setup`.

## Quick start

Requires Python 3.12+, Docker Engine/Desktop using Linux containers, and a Meta Model
API account with access to the configured Muse models. Image initialization downloads
Alpine packages; scan containers do not install dependencies or publish host ports.

```bash
cd Secure-Mitigation-System
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# No API key needed for these commands:
python main.py --list-targets
python main.py --init-images
python main.py --serve --port 8000
```

Open **http://127.0.0.1:8000**. The dashboard loads without Docker or a key and explains
missing setup. Stop the server before changing its environment. On Windows PowerShell,
activate with `.venv\Scripts\Activate.ps1`; use `$env:NAME="value"` for environment variables.

To enable inference, copy `example.env` to `.env`, fill in your key, and export its values:

```bash
cp example.env .env
# Edit .env with your own Meta Model API key, then:
set -a
source .env
set +a
python main.py --serve --port 8000
```

`.env` is ignored by Git and is **not loaded automatically**. PurpleBox reads
`META_MUSE_API_KEY`, even though Meta's examples call the variable `MODEL_API_KEY`.
No keys are sent to Docker, written to reports, returned by health checks, or displayed
in the UI. A real scan sends the selected fixture source to the configured Muse endpoint.

```bash
python main.py --scan node_query_sink --output-dir reports
python main.py --scan php_command_sink
python main.py --scan mysql_insecure_conf
```

CLI exit status is `0` only for a verified candidate with successful cleanup, `1` for
all other scan outcomes, and `130` for interruption. `--output-dir` creates a new run
folder with `report.json` and, when available, `candidate.patch`. The UI also exports
a JSON report. Reports can contain source code, model output, and candidate patches.
Original fixture files are never overwritten by a scan.

## Scan your own repository

Use an existing local checkout. PurpleBox deliberately does not clone URLs, execute
Git hooks, run repository Dockerfiles, or download dependencies during a scan.
Prepare a trusted runtime image with the required tools and dependencies beforehand.
The bundled target image provides Python, Node.js, and PHP, not every framework.
Commands are JSON argv arrays executed **only inside containers**, from `/workspace`.
Your start command must keep the target running. Supply meaningful regression tests
and an expected-behavior contract so a blocked probe cannot earn credit by breaking the app.

```bash
python main.py --project /absolute/path/to/checkout \
  --image my-prepared-runtime:latest \
  --command '["python3", "app.py"]' \
  --test-command '["python3", "-m", "unittest", "discover"]' \
  --contract 'Preserve routes, successful responses, and business logic. Only harden untrusted inputs.' \
  --cycles 3 --context-budget 32768 \
  --allow-remote-inference --output-dir reports
```

The default is **one cycle**, with a maximum of 20. The dashboard's **Local project**
mode accepts the same settings. Paths refer to the server's local filesystem.
Each CLI project run creates a private report directory with evidence and a
cumulative candidate diff. UI reports and patches can be downloaded separately.
The original checkout is read-only to PurpleBox and is never mounted into containers.
To continue on a later run, review/apply the exported patch yourself and scan that
checkout again. No hidden conversation or cross-run state is reused.

See [project intake and runtime requirements](docs/PROJECTS.md) and
[workflow, evidence, and context limits](docs/PROJECT_WORKFLOW.md).

### Private and offline operation

**Hosted mode sends selected source and evidence to the configured Muse endpoint.**
It requires the explicit `--allow-remote-inference` flag or dashboard consent.
Filename-based secret exclusions are a precaution, not a secret scanner. Audit your
source before authorizing hosted inference. Reports can contain sensitive code.

For offline inference, run an operator-provided **Muse-compatible local server**
before starting PurpleBox, with models, runtime images, and dependencies already
available. PurpleBox does not install or download a model server:

```bash
export PURPLEBOX_INFERENCE_MODE=local
export META_MUSE_BASE_URL=http://127.0.0.1:8081/v1
export META_MUSE_RED_MODEL=meta-models/muse-spark-open-1026
export META_MUSE_BLUE_MODEL=meta-models/muse-spark-open-1026
python main.py --serve
```

Local mode permits only literal `127.0.0.1` or `[::1]` endpoints, does not require
an API key or remote-source consent, and never falls back to hosted inference.
The dashboard automatically hides hosted consent and enables local scans without a key. It still uses `MetaMuseClient`
and the Muse model allowlist. The local server must support Chat Completions
`response_format` with `type: "json_schema"`. The operator must ensure the local server actually
serves Muse and does not forward requests externally. No real local Muse serving
deployment is bundled or attested by the endpoint check.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `META_MUSE_API_KEY` | unset | Meta Model API key from dev.meta.ai. Required for scans and live API tests |
| `META_MUSE_BASE_URL` | `https://api.meta.ai/v1` | Meta Model API. Baseten/Modal allowed for the open model |
| `META_MUSE_RED_MODEL` | `muse-spark-1.3` | Boundary analysis |
| `META_MUSE_BLUE_MODEL` | `muse-wonder-1.0` | Sanitization patch generation |
| `META_MUSE_TIMEOUT_SECONDS` | `180` | Per-request API timeout, 1–300 seconds (one real blue request took over 60 s) |
| `META_MUSE_MAX_TOKENS` | `32768` | Output budget, 1024–131072. **Reasoning tokens count toward it.** 8192 truncated real responses |
| `META_MUSE_REASONING_EFFORT` | unset | Optional `minimal`/`low`/`medium`/`high`/`xhigh`/`max`. Unset uses the model's default. `none` is rejected by Muse |
| `PURPLEBOX_VERIFIER_TIMEOUT_SECONDS` | `20` | Per-verifier execution limit, 1–120 seconds |
| `PURPLEBOX_INFERENCE_MODE` | `hosted` | `hosted` requires a key and consent for project source. `local` restricts inference to a literal loopback endpoint |

All inference goes through `agents.MetaMuseClient`. The transport is HTTPX against
Meta's compatible `/chat/completions` endpoint, with strict Pydantic response validation,
bounded response size, no redirect following, and no fallback provider. Only Muse
Spark/Wonder IDs and `meta-models/muse-spark-open[-suffix]` are accepted. For a custom Baseten/Modal deployment, supply a
compatible base URL and ensure that the endpoint actually serves the specified Muse model;
a hostname/model-name check cannot attest what a remote server runs.

**Default models (verified):** red `muse-spark-1.3`, blue `muse-wonder-1.0` on `https://api.meta.ai/v1`. On 2026-10-28 real scans of all three fixtures with a Meta key returned `verified`. Muse Spark is about 5x cheaper per output token than Wonder ($4.25 vs $20 per 1M), so it does the analysis and Wonder writes the patch. Spark for both roles also verified a real PHP scan; set `META_MUSE_BLUE_MODEL=muse-spark-1.3` to cut cost.

**Hackathon open model (optional):** the hackathon asks for `meta-models/muse-spark-open-1026` instead of the documented `meta-models/muse-spark-open`. Muse Spark Open is open-weight and is **not served by `api.meta.ai`** (it returns `404 model_not_found`). It needs a hosted provider's key, for example Baseten: `META_MUSE_BASE_URL=https://inference.baseten.co/v1` and both models set to `meta-models/muse-spark-open-1026`. A Meta key is rejected there with `403`. The allowlist already accepts this ID.

The provided specification used `muse-code` as a model ID. **Muse Code is Meta's coding
agent**, so this implementation uses the documented `muse-spark-1.3` and `muse-wonder-1.0`
model IDs instead. Access still depends on your account. See Meta's
[quickstart](https://dev.meta.ai/docs/quickstart) and
[model configuration guide](https://dev.meta.ai/docs/coding-agents).
The original `SPEC.md` and requested `AGENT.md` template are retained for reference.

## What is implemented

| Component | Behavior |
| --- | --- |
| CLI + FastAPI | Shared asynchronous workflow, localhost binding, one active UI scan per process |
| Dashboard | Offline assets, split red/blue traces, session activity, cancel, report download |
| Three fixtures | Node dynamic-expression sink, PHP local command argument, MySQL config audit |
| Local projects | Bounded immutable snapshots, user-supplied offline runtime and regression commands, multi-file candidate patches |
| Repeated red/blue cycles | Fresh role contexts, structured handoffs, original-probe rechecks, rollback of failed candidates, final patch reports |
| Large-project context | Explicit bounded source batches and coverage records instead of one growing conversation |
| Docker lifecycle | Two pre-built images; separate target/verifier containers; immutable per-session snapshots |
| Resource controls | Non-root user, dropped capabilities, no-new-privileges, CPU/RAM/PID caps, read-only runtime roots, bounded `/tmp` |
| Patch guard | Required notices, small-diff budget, protected-line preservation, exact MySQL edit allowlist |
| Verification | Trusted normal-input checks before and after; explicit 0/1/2 verifier semantics |
| Cleanup | Resource tracking, cancellation-aware worker joins, cleanup independent of UI logging |
| Testability | Mock transport/Docker unit tests and explicit live Docker/API self-tests |

The PHP fixture uses `printf` for a deterministic local diagnostic, rather than making
external ping requests. The MySQL fixture is served as a configuration file; a MySQL
server is **not** installed or started.

## Isolation and result semantics

Source is injected via Docker tar archives into **stopped, never-executed staging
containers** with networking disabled. After commit, runtime containers start from
those snapshots with read-only roots. The patched target is a fresh clone of the
original session snapshot, so a stale process cannot survive the replacement.
There are no host directory mounts, socket mounts, exposed ports, or inherited proxy
settings inside the sandbox. Base images remain for reuse; per-session snapshots,
staging containers, runtimes, and networks are removed after a scan.

Docker `internal=True` blocks normal external routing but **does not guarantee that
host gateway services are unreachable**. Containers also share the host kernel. See
[Docker's internal-network documentation](https://docs.docker.com/reference/cli/docker/network/create/#network-internal-mode---internal).
Project networks additionally require Docker's isolated gateway mode to avoid assigning
a host bridge address. Use a disposable VM or stronger sandbox for hostile
repositories. No claim of complete air-gapping, sub-second startup, or measured
performance is made.

The model's verifier must explicitly exit:

| Exit code | Meaning | Workflow action |
| --- | --- | --- |
| `0` | Specific unsanitized boundary observed | Request a patch, or reject a patch that still exposes it |
| `1` | Boundary cleanly blocked/neutralized | Before patch: no confirmed finding; after patch: candidate may pass |
| `2` or any other code | Crash, timeout, unexpected response, or inconclusive test | Error; never reported as a fix |

The runner converts unhandled Python exceptions and implicit script completion to
code `2`. Trusted normal-input checks are independent of the generated verifier and
run again after the final probe to catch a target that was left broken.
This is still finite evidence, not proof of security or behavioral equivalence:
the verifier can be wrong, and the line-preservation guard is conservative rather
than a language-aware semantic validator. Review every candidate before applying it.

Graceful cancellation waits for an in-flight Docker call to finish, then attempts all
cleanup steps. Daemon outages, host termination, and SIGKILL can leave resources behind.
Failures identify the session label `purplebox.session=<id>` for inspection; the app
does not prune unrelated Docker resources.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python test_harness.py

# Requires Docker and already-built base images; no API key needed:
python test_harness.py --docker

# Makes two real API requests and incurs normal Meta API usage:
python test_harness.py --api

# Both live checks:
python test_harness.py --docker --api
```

The default tests use mocks and do not contact Meta or Docker. The Docker harness
tests all three fixture flows, readies the target, tests public TCP egress in both
container roles, and checks a known small patch with normal-input regression tests.
Its deterministic patches are test inputs, never a runtime inference fallback.
The live API harness checks red/blue response schemas only; a real `--scan` tests
the combined model-and-container path. See `VALIDATION.md` for what was run during scaffolding.

## Project map

```text
purplebox/
  AGENT.md / SPEC.md / LICENSE.md / README.md / VALIDATION.md
  config.py              Environment validation and Muse model lock
  prompts.py             Red/blue task contracts
  agents.py              Muse transport and strict schemas
  registry.py            Bundled fixture registry and normal behavior contracts
  patches.py             Conservative patch guards and unified diffs
  docker_manager.py      Images, isolated runtimes, deadlines, cleanup
  checks.py              Independent normal-input and egress checks
  workflow.py            Shared orchestration and result schema
  main.py                CLI, FastAPI, and WebSocket entry points
  test_harness.py        Opt-in Docker and Muse self-tests
  docker/                Target/verifier Dockerfiles and verifier runner
  static/                Local HTML, CSS, JavaScript
  targets/               Three intentionally vulnerable fixtures
  tests/                 Unit and API tests
```

Next development steps: language-aware semantic patch validation, more runtime
adapters, stronger host isolation, and a measured live demo with your Muse account.
Distributed queues, webhook/CI
automation, automatic host-source patching, and cross-scan snapshot caches are outside
this initial scaffold.

Licensed under [PolyForm Noncommercial 1.0.0](LICENSE.md).
