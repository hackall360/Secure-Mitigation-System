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
