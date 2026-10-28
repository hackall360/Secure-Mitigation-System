# PurpleBox

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

Local input-boundary verification and sanitization scaffolding for the supplied
**PurpleBox specification**. A FastAPI dashboard and CLI share one workflow:
baseline checks → Muse analysis → isolated boundary probe → guarded candidate patch
→ normal-input regression checks → repeat the same boundary probe → cleanup.

This is an initial, runnable implementation for **three bundled fixtures**. It is not
an arbitrary-repository scanner or a production security boundary.

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

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `META_MUSE_API_KEY` | unset | Provider key (Baseten key for the hackathon default). Required for scans and live API tests |
| `META_MUSE_BASE_URL` | `https://inference.baseten.co/v1` | Baseten (hackathon default), Modal, or `https://api.meta.ai/v1` |
| `META_MUSE_RED_MODEL` | `meta-models/muse-spark-open-1026` | Boundary analysis |
| `META_MUSE_BLUE_MODEL` | `meta-models/muse-spark-open-1026` | Sanitization patch generation |
| `META_MUSE_TIMEOUT_SECONDS` | `90` | Per-request API timeout, 1–300 seconds. Use 180+ for real scans (one blue request took over 60 s) |
| `META_MUSE_MAX_TOKENS` | `32768` | Output budget, 1024–131072. **Reasoning tokens count toward it.** 8192 truncated real responses |
| `META_MUSE_REASONING_EFFORT` | unset | Optional `minimal`/`low`/`medium`/`high`/`xhigh`/`max`. Unset uses the model's default. `none` is rejected by Muse |
| `PURPLEBOX_VERIFIER_TIMEOUT_SECONDS` | `20` | Per-verifier execution limit, 1–120 seconds |

All inference goes through `agents.MetaMuseClient`. The transport is HTTPX against
Meta's compatible `/chat/completions` endpoint, with strict Pydantic response validation,
bounded response size, no redirect following, and no fallback provider. Only Muse
Spark/Wonder IDs and `meta-models/muse-spark-open[-suffix]` are accepted. For a custom Baseten/Modal deployment, supply a
compatible base URL and ensure that the endpoint actually serves the specified Muse model;
a hostname/model-name check cannot attest what a remote server runs.

**Hackathon model:** Meta's docs list `meta-models/muse-spark-open` for hosted providers. For the hackathon, use `meta-models/muse-spark-open-1026` (the default). Muse Spark Open is open-weight and is not served by `api.meta.ai`, so the default endpoint is Baseten (`https://inference.baseten.co/v1`, a hackathon credit partner). To use the Meta Model API instead, set `META_MUSE_BASE_URL=https://api.meta.ai/v1` with `muse-spark-1.3` / `muse-wonder-1.0`.

**Key type matters.** A Meta Model API key works only against `api.meta.ai` (verified 2026-10-28: a full real scan passed). On `api.meta.ai` the `-1026` ID returns `404 model_not_found`, and Baseten rejects Meta keys with `403`. Running `-1026` needs a key from the hosting provider.

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
Use a disposable VM or stronger sandbox before extending this scaffold to hostile
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

Next development steps: language-aware patch validation; explicit supported project
manifests and dependency preparation for real repositories; stronger host isolation;
and a measured live demo with your Muse account. Distributed queues, webhook/CI
automation, automatic host-source patching, and cross-scan snapshot caches are outside
this initial scaffold.

Licensed under [PolyForm Noncommercial 1.0.0](LICENSE.md).
