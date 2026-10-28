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

## Environment template and ignore policy

`example.env` is the tracked, sanitized configuration template. Setup copies it to
`.env` only if absent. `.env` and `.env.*` local variants are ignored, with an
explicit exception for the conventional `.env.example` template name.
`example.env` is explicitly allowed. Never put real credentials in templates.
To use the configuration, edit `.env` privately and export it as described above.

## Web UI (dark, interactive dashboard)

Files: `static/index.html`, `static/app.css`, `static/app.js`. No build step, no
external fonts/CDNs (the CSP is `default-src 'self'`). Features: clickable target
cards (keys `1`-`3`, arrows, `Enter` runs, `Esc` stops), a 7-stage pipeline driven
by matching workflow log text in `advanceStage()` in `app.js`, per-team traces
with copy buttons, filterable activity timeline, result facts, and a colored
candidate diff. All model output is inserted with `textContent` only; a test in
`tests/test_web.py` forbids `innerHTML`.

Trap: pipeline stages are inferred from message strings emitted in `workflow.py`.
If you reword those `log(...)` messages, update `advanceStage()` too, or the
pipeline will stop advancing (the scan itself still works).

Visual check without an API key or Docker: run a server whose
`main.execute_purple_workflow` is monkeypatched to emit the real message
sequence, then load it in headless Chrome (`google-chrome --headless=new
--screenshot`). Verified 2026-10-27 at 1440px and 390px: full pipeline, facts,
diff, filters, keyboard selection, and no horizontal overflow on mobile.

## Docker operations (added 2026-10-27)

| Command | What it does |
| --- | --- |
| `python3 .jcode/tools/dev.py docker-status` | `main.py --docker-status`: pings the daemon, checks both base images, counts leftover session containers. Exit 0 only when `state` is `ready`. |
| `python3 .jcode/tools/dev.py images` | Builds base images only if missing (`ensure_base_images`). |
| `python3 .jcode/tools/dev.py rebuild-images` | `main.py --rebuild-images`: unconditional rebuild with `pull=True`, label `purplebox.base=true`. Use after editing `docker/`. |
| `python3 .jcode/tools/dev.py docker-cleanup` | `main.py --cleanup`: removes only `purplebox.session`-labeled containers/networks and `purplebox-clone-cache` snapshots. Base images kept. |
| `python3 .jcode/tools/dev.py docker-test` | Live harness: all three fixtures end to end in real containers. |
| `python3 .jcode/tools/dev.py offline-scan` | `.jcode/tools/offline_scan.py`: runs the production `execute_purple_workflow` through real Docker for every fixture with only Muse replaced by known outputs. Exit 0 only if all three are `verified` with cleanup. About 110 s. |

Code: `docker_status()`, `build_base_images()`, `remove_stale_resources()` in
`docker_manager.py`. `/api/health` now returns a `docker` object
(`state`: `ready` / `images_missing` / `unavailable`). The dashboard shows a Docker
chip and keeps **Run verification** disabled unless both the API key and Docker are ready.

Host state verified: Docker Engine 29.9.2, service enabled at boot, user `sponge`
in the `docker` group (no sudo needed). Forced rebuild produced target
`9f303a259eaf` (Node 22.23.4, PHP 8.4.27, Python 3.12.13, uid 10001) and verifier
`9a351c08f942`. The live harness then passed for all three fixtures with zero leftovers.
A bare `docker run` of the target image takes about 2.4 s, so a full scan's many
short containers dominate wall-clock time.

Traps:
- A rebuild leaves the previous image untagged. Docker refused to delete the two old
  IDs (`9930d74618e3`, `47fb182d1cea`) because of dependent child images. They are harmless.
  Never run a global `docker image prune -a` or `docker system prune` on a shared host.
- Port 8766 on this machine is held by an unrelated `firefox-agent` process. If
  `--serve` exits with errno 98, pick another port. `curl` then gets an empty reply
  from the *other* process, which looks like a server crash but is not.

Why `offline-scan` exists: `test_harness.py --docker` calls `DockerSandboxManager`
directly and never runs `workflow.execute_purple_workflow`, so a harness pass did
not prove the scan path the UI/CLI use. Verified 2026-10-27: all three fixtures
returned `status=verified pre=0 post=1 baseline=True regression=True cleanup=True`
with 12 events each and zero leftover containers.

Trap seen while writing it: `BlueTeamPatch` requires a `diff_summary` field. A stub
without it made every fixture end in `status=error` right after the patch request,
which looked like a workflow/Docker failure but was a schema error in the stub.

### Acceptance through the real dashboard (2026-10-27)

Real Chrome clicked the PHP target card and **Run verification** on the real
FastAPI server. That opened the real WebSocket, ran `execute_purple_workflow`, and
created real Docker sandboxes. Only `MetaMuseClient` was replaced by `KnownMuse`
from `.jcode/tools/offline_scan.py`. Observed: status "Boundary check passed", all 7
pipeline stages done, facts Baseline passed / Exit 0 reachable / Regression passed /
Exit 1 blocked / Resources removed, diff +5 -0, 37 s. Afterwards `--docker-status`
showed 0 leftover containers. Without a key, `main.py --scan` exits 1 with the
"META_MUSE_API_KEY is required" message before touching Docker.
Not yet exercised: real Muse inference, which is blocked until a key is supplied.

## Hackathon model configuration (2026-10-27)

Defaults (`config.py`, `example.env`): `META_MUSE_BASE_URL=https://inference.baseten.co/v1`,
red and blue model `meta-models/muse-spark-open-1026`. `META_MUSE_API_KEY` is the
**Baseten** key. Source: the hackathon instruction says to use `-1026` instead of the
documented `meta-models/muse-spark-open`. Meta's docs
(https://dev.meta.ai/docs/muse-spark-open/deploy, "Hosted providers") say Muse Spark
Open is open-weight and **not served by api.meta.ai**. Providers and base URLs:
Baseten `https://inference.baseten.co/v1`, Together `https://api.together.xyz/v1`,
Groq `https://api.groq.com/openai/v1`, Nebius `https://api.tokenfactory.us-north1.nebius.com/v1`,
Fireworks (ID `accounts/fireworks/models/muse-spark-open`). Baseten and Modal are the
hackathon credit partners, and only Baseten/Modal/api.meta.ai hosts pass `config.validate()`.

The model allowlist in `PurpleBoxConfig.validate()` accepts `muse-spark-*`, `muse-wonder-*`
and `meta-models/muse-spark-open[-suffix]`. Nothing else under `meta-models/` is accepted.
Verified: a no-key POST to Baseten `.../v1/chat/completions` returns HTTP 403 (endpoint
real, auth required). **A real `-1026` completion is still unverified**: the user's key is
a Meta Model API key (`llm...`). Baseten rejects it ("please check the api-key you
provided"), and `api.meta.ai` returns 404 `model_not_found` for `meta-models/muse-spark-open-1026`.
Its `/v1/models` lists only muse-wonder-1.0, muse-spark-1.1/1.2/1.3 (+contributor),
muse-image-1.0, sam-3.1 and muse-voice-transcribe-1.0. Running `-1026` needs a
Baseten (or other provider) key. The user's local `.env` was therefore left on the
working Meta configuration.

Trap: `test_key_only_required_for_inference` read the developer's real environment.
After `source .env`, a non-default `META_MUSE_BASE_URL` would fail it. It now clears all
`META_MUSE_*` variables first.

Trap: an existing local `.env` keeps its old values. Setup never overwrites it, so
update `META_MUSE_BASE_URL` and both model lines by hand (copy from `example.env`).

## First real end-to-end scan (2026-10-28)

With the user's Meta key, `.env` set to `https://api.meta.ai/v1`, red `muse-spark-1.3`, blue `muse-wonder-1.0`:
- `test_harness.py --api`: PASS (live red and blue responses match their schemas).
- `main.py --scan node_query_sink`: exit 0, `verified`. Red found `new Function` injection
  (payload `0 || "a"=="a"` returned 2 rows instead of 0). Blue added one line,
  `if (!/^-?\d+$/.test(rawUserId)) { ...400... }`. Post-patch probe got 400 (exit 1),
  normal-input regression passed, and 0 containers were left. Wall time about 75 s.

Trap (root cause of the first live failure): Muse models **reason before answering, and
reasoning tokens count toward `max_tokens`**. The red request used about 4k reasoning plus
1.1k visible tokens. The scaffold's hard-coded `max_tokens: 8192` produced intermittent
`finish_reason: "length"` with `content: null`, which surfaced as the vague "Muse returned
an incomplete response". Now `META_MUSE_MAX_TOKENS` (default 32768, range 1024-131072) and
optional `META_MUSE_REASONING_EFFORT` (minimal..max, `none` returns HTTP 400 on Muse) are
configurable, and a `length` finish names the fix. Use `META_MUSE_TIMEOUT_SECONDS=180+`,
because a blue request can take over 60 s.
