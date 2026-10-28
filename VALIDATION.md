# Final acceptance: October 28, 2026

- `.venv/bin/python .jcode/tools/dev.py check`: **176 tests passed**, Ruff lint
  and format checks, Python compilation, JavaScript syntax, fixture/schema
  harness, and CLI target listing passed. One upstream Starlette warning remains.
- **Real Muse plus real Docker:**
  `.jcode/tools/project_scan.py --live --cycles 1 --output-dir reports/project-live-structured`
  passed against the configured Meta API, using Spark for red and Wonder for blue.
  Only the generated acceptance fixture was sent. Six real model calls consumed
  27,091 reported tokens, estimated $0.21268 for the successful run. Earlier failed
  attempts also incurred usage and are retained separately as diagnostic evidence.
  Red demonstrated `7*7` expression evaluation returning HTTP 200 / `49`. Blue
  generated a replacement. The unchanged probe then received HTTP 400 / `blocked`,
  original regressions passed, independent Red returned no finding in the bounded
  context, final Blue produced a retained-patch report, and cleanup succeeded.
  This is evidence for that tested boundary, not a general security guarantee.
- **Real Firefox dashboard, WebSocket, loopback inference HTTP, and Docker:**
  `.jcode/tools/project_ui_scan.py` served the generated local project. Two cycles
  completed with retained cumulative SQL parameterization and input-allowlisting
  patches. The browser showed baseline Passed, pre-probe 2/2 reachable, regression
  Passed, post-probe 2/2 blocked, Resources removed, both retained cycle reports,
  all seven pipeline stages done, correctly attributed Red/Blue calls, and +4/-2
  diff lines. Remote-source consent stayed hidden and no API key was needed.
  No desktop horizontal overflow was observed. JSON report and candidate.patch
  downloads were read back from the browser download directory and matched the
  server's complete cycle evidence and cumulative diff byte-for-byte.
  This local test endpoint returned deterministic JSON, not real model inference.
- **Pure-Python project-import probes in real Docker:**
  `.jcode/tools/project_scan.py --source-import-probes --cycles 1 --output-dir reports/project-import-acceptance`
  passed, including pre/post probes, original regression checks, original source
  preservation, and cleanup. Project containers now use explicit /workspace CWD.
- Live diagnostics exposed a missing source-import path and prompt-only schema
  fragility. They are fixed and regression-covered. See PROJECT_WORKFLOW.md for
  the exact runtime flags, schema request shape, provider documentation, and
  browser evidence-summary traps. No permissive JSON repair or provider fallback
  was added. Local schema validation still rejects malformed responses.
- Private generated evidence lives under ignored `reports/`. Test-only dashboard
  and inference servers were stopped after acceptance. No PurpleBox containers,
  session networks, or snapshot images remained in the final inspection.

## Operator prerequisites, not bundled services

A compatible runtime image, dependencies, meaningful regression command, and
behavior contract remain required for each project. Full offline inference needs
an operator-provided local Muse-compatible model server with schema-constrained
Chat Completions support. The loopback HTTP integration is verified, but no real
local Muse model deployment is bundled or attested. Containers share the host
kernel. VM-grade hostile-code containment, exhaustive language/framework coverage,
mobile-browser acceptance, and universal patch correctness are not claimed.

The earlier validation sections below are historical records, superseded by the
final acceptance above where their environment or validation status differs.

---

# Arbitrary-project validation: October 28, 2026

- `.venv/bin/python .jcode/tools/dev.py check` passed: pytest, Ruff lint and
  formatting, Python compilation, JavaScript syntax, schema/fixture harness, and
  CLI target listing. Current suite: **173 passed**, one upstream Starlette
  test-client deprecation warning.
- `.venv/bin/python .jcode/tools/project_scan.py` passed with real Docker target
  and verifier containers. Two cycles retained cumulative SQL parameterization
  and decimal-input allowlisting replacements. Original probes confirmed the
  vulnerabilities before each change and were blocked afterward. The unchanged
  original regression command passed, fresh independent red calls ran, final
  blue reports were produced, original source was unchanged, and cleanup passed.
- Muse HTTP replies in that acceptance run were deterministic `MockTransport`
  responses. This verifies the orchestration and runtime, not autonomous finding
  quality or a real local Muse deployment. The private full report is at ignored
  `reports/project-acceptance/project-acceptance.json` and can be regenerated.
- Dashboard JavaScript executes under Node for hosted consent, local keyless
  readiness, local non-consent, and context-bound checks. FastAPI tests exercise
  project WebSockets, disconnect cleanup, shared scan locking, input rejection,
  and private CLI report exports. These are not visual browser acceptance tests.
- Post-run Docker inspection found no PurpleBox containers or session networks.
- Arbitrary projects require a compatible preloaded image, dependencies, startup
  command, regression command, and behavior contract. No clone, package download,
  automatic patch application, universal-language support, VM-grade containment,
  or general security certification is claimed. Local inference is an explicit
  operator-provided loopback Muse-compatible service, never a hosted fallback.

The older scaffold validation below is retained as historical evidence only.
Its Docker/browser availability statements describe that earlier environment,
not the current Docker acceptance result.

---

# Scaffold validation — October 27, 2026

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

## Completed

- Python 3.12.14; the pinned direct dependencies installed successfully in a clean virtual environment.
- `python -m pytest -q`: **63 passed**. One upstream Starlette warning advises migrating
  its test client from HTTPX to HTTPX2; this does not affect the Muse HTTPX transport.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: all 20 Python files formatted.
- `python -m compileall -q .`: passed.
- `node --check static/app.js` and `node --check targets/node_query_sink/app.js`: passed.
- `python test_harness.py`: all local schemas, three known candidate patches, and
  generated trusted-check script syntax passed; live checks correctly reported skipped.
- `python main.py --list-targets`: lists all three bundled fixtures.
- A real Uvicorn process served `/`, `/api/health`, `/api/targets`, and all static assets
  with HTTP 200. A real WebSocket connection returned a clean missing-key error result.
- A CLI scan without a key exited 1 before opening Docker.
- `python test_harness.py --docker` reported a failed Docker preflight and exited 1,
  as expected in this environment without a Docker daemon.

The unit suite covers API schema errors, endpoint/model restrictions, no redirects or
fallbacks, path-safe archive generation, container resource configuration, staging
injection failures, verifier timeouts, cleanup after failures, cancellation during a
blocking Docker operation, normal-behavior regression failures, post-probe health,
patch scope, notice preservation, cross-origin/DNS-rebinding rejection, concurrent
scan rejection, and WebSocket disconnection cleanup.

## Not validated here

- No live image builds or container executions: Docker CLI/daemon are unavailable.
  Resource options, creation/commit operations, and cleanup are tested with mocks.
  Actual Docker `put_archive`/commit compatibility, DNS reachability, read-only runtime
  behavior, PHP execution, and egress restrictions require `python test_harness.py --docker`.
- No real Muse calls: no API key was configured. The API transport and schemas were
  tested with HTTPX MockTransport. Run `python test_harness.py --api`, then a real scan
  to validate endpoint access, model response quality, and the combined workflow.
- No visual browser verification: the environment had no Chromium executable and
  its attempted browser download was not a valid archive. HTML/CSS/JS asset delivery,
  JavaScript syntax, and server/WebSocket behavior were tested; responsive layout and
  browser event rendering still need visual review.
- No performance benchmarks, hostile-repository containment proof, or proof that
  generated patches preserve all possible application behaviors.

`README.md` records the implementation's scope and deliberate corrections to the
provided starter, including Muse model IDs and Docker internal-network limitations.
