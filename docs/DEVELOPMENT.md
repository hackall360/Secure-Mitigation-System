# Development environment

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

## Prerequisites and bootstrap

Run from the repository root. Use Python 3.12 (selected by `.python-version`),
[uv](https://docs.astral.sh/uv/getting-started/installation/), Node.js for syntax
checks, and a running Linux Docker Engine accessible to your user. Docker socket
access is effectively host administrator access. Do not chmod the socket or
run this application as root to bypass permissions.

```sh
python3 .jcode/tools/dev.py setup
python3 .jcode/tools/dev.py check
python3 .jcode/tools/dev.py images
python3 .jcode/tools/dev.py docker-test
python3 .jcode/tools/dev.py smoke
python3 .jcode/tools/dev.py serve --port 8000
```

`setup` creates `.venv` only if missing, installs exactly the transitive versions
and hashes in `requirements-dev.lock`, checks compatibility, and creates a private
ignored `.env` template only if absent. Existing `.env` files are not overwritten.
No activation is needed: the helper always uses this repository's interpreter.
It never installs into system Python. Dependency synchronization removes packages
not in the lock, so keep unrelated tooling in a different environment.

`serve` runs in the foreground at http://127.0.0.1:8000. Stop with Ctrl+C.
`smoke` starts a temporary real server on an available localhost port, checks
key-free health, dashboard/API/static assets, and shuts the process down.
`check` runs unit tests, Ruff, Python compilation, JavaScript syntax checks, the
local harness, and the target-list CLI. It does not call Docker or Muse.
`images` creates missing reusable base images. `docker-test` uses those images
for real sandbox checks, then removes its own containers, networks, and snapshots.
No target or verifier service should remain running between scans. Do not add
Compose or keep intentionally vulnerable fixtures exposed on host ports.

## Keys and inference

Setup and all commands above work without an API key. `.env` is a template,
not automatically loaded by the application or helper. To enable inference,
edit `.env` privately, then in a trusted shell:

```sh
set -a
source .env
set +a
.venv/bin/python test_harness.py --api
.venv/bin/python main.py --scan node_query_sink --output-dir reports
```

These two commands send source to Muse and incur API usage. They are deliberately
not part of bootstrap or routine validation. Never commit `.env` or reports.

## Dependencies and images

Direct versions remain in `requirements.txt` and `requirements-dev.txt`. After an
intentional dependency edit, regenerate and review the lock, synchronize, and test:

```sh
python3 .jcode/tools/dev.py lock
python3 .jcode/tools/dev.py setup
python3 .jcode/tools/dev.py check
```

The lock was resolved for Python 3.12 on Linux x86_64. Other platforms must be
validated independently. It does not lock operating-system packages in images.
The Dockerfiles currently use `python:3.12-alpine3.22` and Alpine package names,
so a future uncached rebuild can resolve different image/package versions.
`ensure_base_images()` in `docker_manager.py` builds only missing tags. After
editing a Dockerfile or `docker/runner.py`, rebuild explicitly:

```sh
docker build -f docker/Dockerfile.target -t purplebox-target-base:latest docker
docker build -f docker/Dockerfile.verifier -t purplebox-verifier-base:latest docker
python3 .jcode/tools/dev.py docker-test
```

Do not run global Docker prune commands. Inspect only project resources:

```sh
docker image ls --filter 'reference=purplebox*'
docker ps -a --filter label=purplebox.session
docker network ls --filter label=purplebox.session
```

Inspect a resource's exact `purplebox.session` label before considering manual
cleanup. Do not delete another development session's containers or networks.

## Observed setup facts and traps (2026-10-27)

- Branch: `feature/setup-and-refinement` from merged `develop` at `2dc95e9`.
- System Python is 3.14.4, so using bare `python` can silently select the wrong
  runtime. The project environment is CPython 3.12.13 with uv 0.11.7.
- `uv venv` does not seed pip by default. `python -m pip` failed in the original
  environment, while `uv pip` worked. The helper consistently uses `uv pip`.
- Docker Engine 29.9.2 / API 1.56 works with the project's Docker SDK 7.1.0 for
  image builds. Both base images built successfully through `main.py --init-images`.
- The Docker harness can be quiet while snapshots/containers are created. Inspect
  project-scoped `docker ps` or events before interpreting silence as a hang.
- Cross-filesystem uv cache hardlink warnings mean it fell back to copies, not
  a failed install. Set `UV_LINK_MODE=copy` to suppress this optional optimization.
- Starlette emits a TestClient HTTPX deprecation warning. The current unit tests
  pass. This is not a reason to silently change the pinned transport dependencies.
- A real Uvicorn smoke test returned HTTP 200 for health, targets, dashboard,
  JavaScript, CSS, and favicon, and shut down cleanly.

Research references: [uv environments](https://docs.astral.sh/uv/pip/environments/)
and [Docker SDK image API](https://docker-py.readthedocs.io/en/stable/images.html).
The installed SDK source and actual Docker execution, not only current online
SDK documentation, determine compatibility with this pinned environment.

## Acceptance results on this machine

The completed setup was exercised on 2026-10-27, not only inspected:

| Requirement | Observed result |
| --- | --- |
| Isolated dependencies | All 29 packages installed with required hashes into a second, newly created Python 3.12.13 virtual environment; compatibility check passed |
| Unit and setup regression tests | 68 passed in both the project environment and the fresh environment |
| Repeatable bootstrap | Re-running `setup` succeeded without replacing the existing `.env` |
| Tooling quality | Ruff lint/format, Python compilation, both Node syntax checks, local harness, and target-list CLI passed |
| Real application startup | Real localhost health/dashboard/API/assets checks passed, including helper invocation from outside the repository |
| Docker target image | `purplebox-target-base:latest`, image ID `sha256:9930d74618e30885fd7dd5d83d9ca44cbc9dd578bead9e39a2128929c97f41b5` |
| Docker verifier image | `purplebox-verifier-base:latest`, image ID `sha256:47fb182d1cea493bf4228d91b15c4e84227988f301fac6cd8f464906b6547907` |
| Image ownership | Both images configure `10001:10001`, verified using Docker inspect through the SDK |
| All three real fixture flows | Node, PHP, and MySQL-config fixtures each passed baseline, unsanitized probe, patched probe, normal-input regression, and target/verifier egress checks |
| Cleanup | Subsequent SDK queries found zero session-labeled containers/networks and zero `purplebox-clone-cache` snapshot images; reusable base images remain |
| Private local configuration | `.env` exists with mode 0600 and remains Git-ignored |

The initial image-build plus live-harness command completed successfully in about
156 seconds. Harness progress messages now flush per fixture/stage to distinguish
ongoing work from a stall. Five new unit tests cover local-interpreter selection,
missing prerequisites, template permissions, and preservation of existing config.

### Remaining limits

No real Muse API request or model-generated end-to-end scan has been run. Configure
a valid account key to test those separately. No visual browser review or
performance benchmark was performed. Docker's internal bridge blocks the tested
public TCP paths but is not proof of host isolation. Fixtures remain a development
scaffold, not a safe execution boundary for arbitrary hostile repositories.
The original `VALIDATION.md` remains a historical scaffold report; this section
supersedes its Docker-unavailable statement for this machine only.
