# Repository import and development map

## Initial scaffold import

- Date: 2026-10-27.
- Source: `purplebox-scaffold.zip`, originally in `/home/sponge/Downloads/`.
- Archive SHA-256: `d4a3abbb0efb486c7b8040b4344541804afabc731eda9abb375c07b5dc5e0629`.
- Branch: `feature/initial-scaffolding`, based on `develop` at `8bb2dc6`.
- Import commit: `2594b90` (`feat: import initial PurpleBox scaffold`).
- Removed the archive's enclosing `purplebox/` directory so the application lives
  at the repository root. All 34 non-ignore files were verified byte-identical
  to the archive after import. The existing `.gitignore` was preserved and the
  scaffold's rules appended. The source archive was not modified or committed.
- `VALIDATION.md` contains the scaffold author's original validation report,
  not a record of checks performed in this repository.

## Local validation of the import

Created an ignored `.venv/` with Python 3.12.13 and installed the exact direct
versions from `requirements-dev.txt`:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m compileall -q -x '/(\.git|\.venv)/' .
node --check static/app.js
node --check targets/node_query_sink/app.js
.venv/bin/python test_harness.py
.venv/bin/python main.py --list-targets
```

Results: 63 tests passed, lint passed, all 21 Python files passed formatting,
Python compilation and both JavaScript syntax checks passed. The local harness
passed schema, fixture-patch, and generated-check syntax checks. The CLI listed
all three bundled targets. Node version was 22.22.1.

One upstream Starlette warning reports deprecated HTTPX TestClient usage. It did
not fail the suite. No application code or dependency versions were changed.
Live Docker builds, container checks, Muse API requests, and browser visual
checks were not run as part of the import. The local harness explicitly skips
live checks unless requested. Unit tests are not proof of live integration.

## Entry points and local state

- `main.py`: CLI, FastAPI application, static asset and WebSocket endpoints.
- `config.py`: environment-driven Muse endpoint, model, and timeout configuration.
- `agents.py`: `MetaMuseClient` and model response schemas.
- `workflow.py`: scan orchestration.
- `docker_manager.py`: `DockerSandboxManager` and sandbox lifecycle.
- `registry.py` and `targets/`: bundled target definitions and source fixtures.
- `tests/`: isolated unit tests, configured by `pyproject.toml`.
- `test_harness.py`: local checks and explicit `--docker` / `--api` live checks.
- `.env.example`: configuration template only. Python does not automatically
  load `.env`, so export the configured values before starting the application.
- `.venv/`, `.env`, caches, and `reports/` are ignored local state.

See `README.md` for running the application, `SPEC.md` for design requirements,
and `AGENT.md` for maintenance constraints.
