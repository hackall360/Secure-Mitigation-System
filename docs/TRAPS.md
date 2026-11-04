# TRAPS — things that looked correct and were not

One growing map per `docs/guides/WORKFLOWS.md`. Highest value first: the
wrong assumption, then what the evidence actually showed. Link new entries
here, not in scattered notes.

## Stale `.pyc` shadows mutant revert (2026-11-02, branch feature/verification-sweep)

- **Trap: `git checkout -- <file>` after a mutation experiment does NOT invalidate the `.pyc` compiled from the mutant — the stale bytecode keeps executing.**
  Wrong assumption: "source restored = behavior restored; the next pytest run tests the real code." A Layer-2 mutant run (`cached = 0` in `sms_compress.py`) compiled `__pycache__/sms_compress.cpython-312.pyc` at 15:45; `git checkout --` restored the `.py` but left the mutant `.pyc`. Five R2-parse tests then failed in the repo checkout while passing in a pristine worktree with byte-identical sources — the only difference was the poisoned cache. Purging `*.pyc` (`find library tests -name "*.pyc" -delete`) turned 5-failed into 21-passed with zero source changes.
  Evidence: identical `diff` on the `.py`, divergent `compress_context` output, `ls -la` showing the 15:45 `.pyc`; post-purge 236/236 gap tests green.
  Lesson: after ANY in-place mutation experiment, `find <touched-dirs> -name "*.pyc" -delete` before trusting another run. Prefer `git stash` round-trips (which the gate's compileall would also have caught) or copy-the-file-to-/tmp mutants that never touch the tree. The `verify_cov.py` tracer compounds this: it reports line hits from whatever bytecode executed, so a poisoned `.pyc` silently corrupts coverage too.

## Bare-metal setup test in clean container (2026-11-02, branch feature/baremetal-setup-test)

- **Result: fresh-install setup WORKS — `dev.py setup` → imports → targets → tags → smoke all green in a bare `python:3.12-slim` container; project loads without issues.**
  Method (closest bare-metal approximation): `docker run -d python:3.12-slim sleep 3600`, `git archive HEAD | docker exec tar -x` into `/repo`, `dev.py setup` (stdlib venv fallback — no uv in slim), then `import main/tui/sms_cli`, `main.py --version/--list-targets`, `dev.py tags` (128/128), `dev.py smoke` (keyless health + 6 asset routes), 68 unit tests + ruff + `test_harness.py`. No secrets entered the container (keyless paths only). Container removed afterward (`docker rm -f`). No end-to-end scan per scope.
- **Trap: `--network none` breaks setup at pip — and that is correct, not a bug.**
  Wrong assumption: "air-gapped everywhere, including the test container." `dev.py setup` installs from PyPI, so a fully isolated container fails with `No matching distribution found for fastapi`. The air-gap invariant (LAW 4) covers the app's Docker sandbox, not the developer's `pip install` — bare metal has network at install time. Retested with network: setup green in 40 s. Never "fix" setup to work offline; fix the test harness instead.
- **Trap: slim images have no `node`, and README only asked for Python + Docker.**
  Wrong assumption: "`node --check` is a dev nicety; fixtures don't need it." The gate runs `node --check` on `targets/node_query_sink/app.js` + every `web/js/**`, and the Node fixtures need node at scan time — so a bare box without Node.js fails both. `docs/guides/DEVELOPMENT.md` already listed Node.js, but README "Try it" did not. Fix shipped: README now reads "Python 3.12+, Node.js (syntax checks + Node fixtures), and Docker"; pinned by `test_readme_try_it_lists_all_setup_prerequisites`. Lesson: the README prerequisite line and DEVELOPMENT.md must stay in sync — the container test is the check.
  Evidence: container transcript — setup 40 s green, `imports OK` + `0.14.0`, 5 fixtures, tags 128/128, smoke 6/6 PASS, 68 unit green, harness PASS (Docker/Muse correctly skipped). `node: not found` was the only red line, from the image — not the repo.

## Overnight int(inf) OverflowError class (2026-11-01, branch feature/overnight-verify)

- **Trap: `int()` on untrusted numerics raises `OverflowError`, not `ValueError` — and every `(TypeError, ValueError)` guard in the repo missed it.**
  Wrong assumption: "Invalid values never raise: they clamp or fall back" + `except (TypeError, ValueError)` covers all garbage. `int("abc")` and `int(None)` do raise those — but `int(float("inf"))` raises `OverflowError: cannot convert float infinity to integer`, which escapes. `float()` never has this problem (inf is a valid float); only `int()` does.
  Evidence: 5 RED-first fixes, same shape, all proven with OverflowError in-trace on unmodified code: transport clamps (`sms_http._clamp_tries/_clamp_max_bytes`), `_leader_decision_message` + `generate_demo_project` counters, 7 `/ws/demo` parsing guards (hostile browser JSON: `json.loads` decodes literal `Infinity`/`1e999` to inf via allow_nan default; the socket died `ClosedResourceError` instead of fail-closed defaults), 5 fail-closed evidence-gate guards (Mapping-form evidence from deserialized JSON; the gates crashed instead of returning False), 4 MCP `max_passes`/stamp-cycles guards (raw-Infinity POST body; HTTP contract is clean `-32602`, not a scan). Fixed shape: `except (TypeError, ValueError, OverflowError)`. Files: `library/shared/sms_http.py`, `library/services/project_agents.py`, `library/services/demo_gen.py`, `main.py`, `library/workflows/project_workflow.py`; tests `test_transport_bounds_red.py`, `test_int_overflow_red.py`, `test_ws_demo_inf_red.py`, `test_evidence_gates_inf_red.py`, `test_mcp_inf_red.py`.
  Lesson: any `int()` on network/JSON-adjacent input must catch `OverflowError` too. `float()` sites need no fix. Audit with: grep for `except (TypeError, ValueError)` near `int(`, then prove inf-reachability per site (pydantic-validated ints and int-only callers are safe by construction — verify, don't harden).
- **Trap (tooling): the `write` tool can report success on a new file that never lands — verify with `ls`/`read` before editing it.**
  Wrong assumption: `write` replying "Created ..." means the file exists with that content.
  Evidence: two `edit` calls on `tests/test_int_overflow_red.py` failed "old_string not found", then `read` said "File not found" and `ls` confirmed absence — the create never landed despite the success message. Shell heredoc (`cat > file <<EOF`) worked first try; existing-file edits in the same session were fine.
  Lesson: after `write` of a NEW file, verify existence before editing; if edits mysteriously miss, re-check existence rather than retrying.

## Ascendancy Wave 2 RED tests (2026-10-30, branch feature/30-wave-ascendancy)

- **Trap: a module-level `import` of a not-yet-existing module makes pytest report ERROR, not FAIL — and 2 such files abort the whole session.**
  Wrong assumption: `ModuleNotFoundError` at import = RED fail, so the wave's "44 failed / 0 passed" claim holds by counting.
  Evidence: `pytest` on all 10 `test_*_red.py` stopped at `2 errors during collection` and never ran the other 8 files; the true count (44 failed, 0 passed) only appeared after wrapping both imports in `try/except ModuleNotFoundError` + an explicit `test_*_module_exists` gate test. Same assertions, no weakening.
  Lesson: RED tests for missing modules must import defensively and fail as `AssertionError` inside a test body; a collection ERROR is not a LAW 9 red (it proves nothing about behavior and hides sibling results).
  Also: `TypeError: 'NoneType' object is not callable` on follow-on tests is the correct downstream shape — it traces to the same absence, not a second defect.

## Ascendancy Wave 10 wild crucible (2026-10-31, branch feature/30-wave-ascendancy)

- **Trap: `docker cp` cannot see tmpfs-mounted content on this daemon — three "Could not find the file" failures on files `docker exec ls` proves exist.**
  Wrong assumption: clone into a tmpfs staging dir, then `docker cp` the tree out — standard two-step extraction.
  Evidence: `docker exec ls /tmp/wild` listed all 3 wildcard files, but `docker cp` (whole-dir and per-file) failed every time; per-file `docker exec cat` through stdout worked (~100B files). The tmpfs mount that makes the container disposable also hides its contents from the daemon-side copy path.
  Lesson for the intake implementation (`repo_intake.py` staging): extract with `docker exec tar -C <dir> -cf - .` streamed to stdout, or stage into a non-tmpfs container path (still no host mount — a writable container layer dir), never tmpfs + `docker cp`. Recorded in `docs/WILD_INGESTION_LOG.md`.
  Also: README-manifest mismatch — the wildcard README claims a `requirements.txt` the tree does not contain, so `detect_runtime` correctly fails closed. Never trust manifest claims from intel; list the actual tree.

## TUI parity merge (2026-10-30, shipped as 0.6.0)

- **Trap: `TuiState.sweep_depth` vs `sweep_passes` are two different names
  for one knob, and whichever the dataclass declares wins.**
  Wrong assumption: Writer-B's `_state_sweep_passes` checked
  `("sweep_depth", "sweep_passes")` in order, so `setattr(state,
  "sweep_passes", 3)` should resolve to 3.
  Evidence: Writer-A's merged dataclass declares `sweep_depth: int = 1`
  (no `sweep_passes` field), so the merged `_state_sweep_passes` saw
  `depth=1` first and returned 1 — probe `test_dispatch_sweep_passes`
  failed 1/58 post-merge while passing 51/51 on B's branch (where
  `TuiState` had neither field, so `getattr` fell through to the
  `sweep_passes` kwarg = 3).
  Fix shipped in `tui.py`: `_state_sweep_passes` prefers an explicitly-set
  `sweep_passes != 1`, else falls back to `sweep_depth`; B's
  `test_dispatch_sweep_depth_field` (depth-first) still passes.
  Lesson: when two writers share one dataclass, grep both branches for
  every field name before merging — `getattr` fallback chains silently
  change meaning when a real field appears.

- **Trap: `tests/test_tui.py` `run_plain` pair fails only in some
  collection orders — and the real gate collects alphabetically.**
  Wrong assumption (from Writer-A's report): the 2 failures are
  pre-existing/order-dependent noise, reproducible on the clean tree, safe
  to note and move on.
  Evidence: they reproduce because `run_plain`'s lazy
  `from modules.workflows.workflow import execute_purple_workflow` runs
  AFTER the `sys.modules["modules.workflows.workflow"]` fake is seeded,
  but importing `binary_sweep`/`sweep` at the same point pulls
  `modules.workflows.sweep`, whose top-level
  `from modules.workflows.workflow import build_verdict_receipt` hits the
  fake module (which has no such attr) → `ImportError: cannot import name
  'build_verdict_receipt'`. Direct `pytest tests/test_tui.py` (or any
  order with `test_tui.py` first) fails; B's order (dispatch tests first,
  importing the real modules) passes — masking the bug.
  Fix shipped in `tui.py::_run_plain_legacy`: honor `sys.modules` fakes
  and import `sweep`/`binary_sweep` lazily only inside the branch that
  needs them. Now 14/14 in every order.
  Lesson: "order-dependent, fails on clean tree" is not noise — it is a
  latent import coupling. Reproduce it with the single file first
  (`pytest tests/test_tui.py` alone), read the full chain (the real
  culprit was 3 frames below the test line), and fix the import, not the
  test.

- **Trap: LAW 6 says remove worktrees when done — do it after the merge
  ships, and confirm the branch list.**
  `git worktree remove --force /tmp/wt-<role>` + `git branch -D
  feature/<role>` after `develop`+`main` both push green; `git worktree
  prune` to clear the stale entries.

- **Trap: `python3 tui.py` without the venv fails with
  `ModuleNotFoundError: No module named 'docker.errors'`, not a TUI bug.**
  Live TUI proofs must run under `.venv/bin/python` (Docker SDK lives
  there). Without API key + Docker, `_run_plain_*` fails closed with
  `rc=1` and `Muse request failed or timed out; no fallback provider was
  contacted` — that IS the live proof (real Docker phases ran, cleanup
  ran, no fallback contacted).

## UI guidance-matrix pass (2026-10-30, branch feature/ui-guidance-matrix)

- **Trap: `serve-up --port` foreground-hangs the shell — the server is up while the tool never returns.**
  Wrong assumption: `dev.py serve-up --port 18080` failing to return means the server failed to start.
  Evidence: `/api/health` answered `ok` + `api_key_configured=true` and `/` served the new DOM while the `serve-up` wrapper still held the foreground past the 120s timeout (went to background task `312701v1f2`, had to cancel + `pkill -f serve.*18080`). Prefer `serve-up` for LAW 7 drills, but for DOM-proof serving use the `ui_scan.start_server(port, offline)` helper pattern (returns a Popen once `/api/health` answers) or background the command yourself.
- **Trap: run `offline_scan.py` under `.venv/bin/python`, never system python3.**
  Wrong assumption: system python has the Docker SDK because the repo imports it.
  Evidence: `ModuleNotFoundError: No module named 'docker.errors'` on system python; venv run gives 3/3 verified.
- **Trap: `browser_controls_check.py` asserts a stale 1-tool MCP list.**
  Wrong assumption: its `mcp_tools == ["submit_code_snippet"]` failure means the dashboard regressed.
  Evidence: live `/mcp tools/list` correctly returns all 5 library/MCP tools (V1 Subsystem E shipped); the tool's assertion predates it. Fix the tool, not the dashboard.
- **Trap: the edit tool needs byte-exact anchor whitespace; `sed -n | cat -A` first.**
  Evidence: two failed `edit` calls on `static/index.html` (guessed 2-space vs real 4-space/6-space nesting + one long single-line anchor) before switching to a Python replace script with `repr()`-verified anchors.
- **Trap: `graph.js` `isFallback()` semantics — live canvas still reports fallback while the strip is mounted.**
  Wrong assumption (first draft): `isFallback()` should return false once canvas binds.
  Evidence: the strip `#scan-timeline` is ALWAYS mounted (it is the fallback path), so a naive "strip exists => fallback" check reports fallback=true on a healthy live graph. Shipped logic: internal `fallback` flag (canvas bind failure) decides; the strip reference documents the degraded path. CDP proof showed `graph_fallback=false` with the strip mounted.
- **Trap: `sms_compress.py` budget pass used `id(line)` to restore order — shared refs today, value-equal copies tomorrow.**
  Wrong assumption: `position = {id(line): idx for idx, line in enumerate(pruned)}` + `sorted(..., key=lambda line: position.get(id(line), 0))` is stable because `head`/`tail` are slices of `pruned` (same objects) — so identity ordering is correct.
  Evidence: a future refactor that copies strings (e.g., `str(line)` / `.strip()` / buffer rebuild) would produce value-equal lines with different identities; those would miss the `id()` map, fall back to `0`, and lose original order silently while still passing the 10 existing green tests. Fix shipped in `modules/shared/sms_compress.py:285-311`: keep `id()` fast-path for shared refs but add a value+occurrence fallback (`value_positions: dict[str, list[int]]` + `seen_counts` + `_pos(line)`) so any value-equal line still maps to its first pruned occurrence. Red test `tests/test_compression.py:test_compress_budget_preserves_order_under_value_equality` (600 filler + critical sink, `max_tokens=80`, monotonic filler-index check) pins the invariant; `dev.py check` 627 passed.

## Overnight forge traps (2026-10-31, branch feature/overnight-forge)

- **Trap: hand-written docs JSON shipped invalid for 3 commits.**
  Wrong assumption: a small JSON file written by hand is fine because the gate is green.
  Evidence: `docs/vuln_taxonomy.json` contained a raw `"` inside `"taint":"... db.execute("...") ..."`; `json.load` fails at char 345, and `dev.py check` never parses docs JSON so 3 commits stayed green-but-invalid. Fix: generate docs JSON with `json.dump`, never by hand; run `python3 -c "json.load(open(...))"` before commit. Found during Cycle-4 T7 sync; rewritten as v1 with priors linked.
- **Trap: Green contract/test/default-param mismatch burns keyed spend.**
  Wrong assumption: "decimal arithmetic" in the contract covers `calc('40+2')`.
  Evidence: Cycle-2 attempt 2 — Blue's minimal allowlist was guard-accepted but broke the Green's own `calc('40+2')=='42'` regression while the contract said decimal-only and the default route expr was `'1+1'`. Fail-closed rollback, ≈$0.22 spent. Contract, test, and default params must agree BEFORE keyed runs.
- **Trap: Gate-3 replay must assert neutralization, not exceptions, for SQL parameterization.**
  Wrong assumption: a fixed SQLi sink raises on tautology input.
  Evidence: my first Cycle-4 replay script asserted `raises`; sqlite3 parameterization returns EMPTY rows instead (verified directly). The Blue patch was right, my script was wrong. Assert `== ""` per bundled semantics (project_scan PATCH_ONE).
- **Trap: Blue verbosity breaks the 60-line surgical guard.**
  Wrong assumption: a full arithmetic parser is a better eval-sink patch than an allowlist.
  Evidence: Cycle-2 attempt 1 — Blue wrote a 96-line recursive-descent parser, 36 lines over budget, guard rejected despite Red exit 0. A 7-line decimal allowlist verified on retry. Steer Blue with "minimal allowlist suffices; do NOT write a parser".

- **Trap: `timeout 120` on `offline_scan.py` SIGTERMs it mid-teardown, leaving session containers/networks/snapshots.**
  Wrong assumption: 3 printed "verified" cards mean the sweep (including cleanup) finished.
  Evidence: exit 124 with all 3 cards green, but 1 running target + 1 exited verifier + 5 networks + 4 snapshot images lingered; `remove_stale_resources` reaped `{containers: 4, networks: 5, snapshots: 4}`. The `finally: sandbox.close()` never ran because SIGTERM landed during/after the last card. Fix: run offline scans with `timeout ≥ 300` (a full sweep takes ~2min), assert per-card `cleanup=True` AND `docker ps -a --filter label=purplebox.session` empty afterwards. Never manually `rm -f` session containers that a live sweep may still track — prefer `remove_stale_resources` after the sweep exits on its own.

- **Trap: host-port smoke tests (`--network host` + `docker run -d`) leak containers that `remove_stale_resources` may not reap.**
  Wrong assumption: a detached smoke container is covered by the session-label sweeper.
  Evidence: Cycle-10 smoke `vigilant_poincare` (created 09:23 for the T6b curl check, `--network host`, NO `purplebox.session` label — only `purplebox.base:true`) was still `Up` at 09:32, 9min after use. Session sweeps filter on `purplebox.session`, so unlabeled hand-run containers are invisible to them; manual `docker stop/rm` required. Fix: smoke with `timeout N docker run --rm` in the FOREGROUND (auto-reaped on exit, like the Cycle-7/8/11 Gate-3 replays), or `--label purplebox.session=manual-smoke` so the sweeper sees it. Never `-d` without `--rm` + a foreground wait.

- **Trap: host-loopback smoke tests hang when the container binds a loopback while the HOST holds the port (or vice versa) — curl blocks until timeout.**
  Wrong assumption: `curl 127.0.0.1:PORT` reaches a `--network host` container's `php -S 127.0.0.1:PORT`.
  Evidence: Cycle-13 smoke — container bound `127.0.0.1:18085` inside its netns-visible host stack, but host curl got NO response for 2 minutes (empty replies, task `389902l92a` had to be abandoned; verification moved to `docker exec wget` INSIDE the container, which proved both benign listing AND `;touch /tmp/PWNED13` injection). The `tender_lovelace`/`elastic_ellis` containers also lingered past the smoke (manual stop needed). Fix: NEVER smoke network services from the host against `--network host` containers — `docker exec <container> wget -q -O- http://127.0.0.1:PORT/...` is the reliable probe (same netns). Foreground `docker run --rm` still for lifecycle, but probe via exec, not host curl. (Cycle-5/10 smokes worked because host ports were free AND php bound 0.0.0.0; 18085 collided with the earlier task's network state.)

- **Trap: stateful Green fixtures MUST persist under `/tmp`, never `__DIR__`.**
  Wrong assumption: the target runtime filesystem is writable because the snapshot staged files there.
  Evidence: Cycle-16 attempt 1 — `/sign` wrote `notes.json` next to `server.php` with `@file_put_contents` (silent fail); the runtime is `read_only: True` (tmpfs only `/tmp`), so the wall rendered empty and the BASELINE regression failed (`FAIL Ada`) before Red even ran. Fix: `sys_get_temp_dir()` / `/tmp/...` for all fixture state (the Cycle-16b store is `/tmp/forge16-notes.json`). Never `@`-suppress persistence writes in fixtures — fail loudly in smoke tests.

- **Trap: multi-sink fixtures let Red pick the EASIEST link, orphaning the headline sink.**
  Wrong assumption: Green co-presenting two sinks gets two proofs (or the harder one).
  Evidence: Cycle 24 — Gate-0 PROVED the T1d second-order signal locally (hey,yo vs hey), but the keyed Red probe never touched `/nick` (0 mentions); it proved the T4 traversal instead and Blue closed only that. Same shape as C17 (Function sink orphaned). The receipt is per-FINDING, not per-fixture — orphans must be re-queued solo, never assumed covered. Fix: ONE sink per fixture for headline proofs; co-present sinks ONLY when the chain contract demands both links (C4/C7/C11 unified-script pattern). The T1d solo fixture is queued.

- **Trap: source-import (`from src.x import f`) Red probes DODGE gate links — chain contracts must demand HTTP-level proof.**
  Wrong assumption: a verified sink finding on a chained fixture proves the chain.
  Evidence: Cycle 30 — Gate-0 CONFIRMED the T9b+T1e chain shape locally, but the keyed Red probe imported `read_secret` directly (0 mentions of `/claim`/cookie), proved only the T1e label SQLi, and Blue closed only that. The T9b PIN gate was never exercised (neither honored nor bypassed). C4/C7/C11 chains verified because their probes ran the HTTP cookie round-trip. Fix: chain contracts must REQUIRE the HTTP cookie flow in the probe (assert Set-Cookie capture + Cookie reuse), and scribe must check the probe for the gate-link shape before accepting a "chain" verdict. A direct-import sink proof on a chained fixture is a PARTIAL by definition.

- **Trap: Gate-3 replays MUST reproduce the framework decoding stack, not call the sink directly.**
  Wrong assumption: passing the raw attack string to the patched function replays the Docker proof.
  Evidence: Cycle-38 replay #1 fed literal `%252e...` to `fetch_asset()` via CLI and asserted 400 — FAILED, because CLI strings skip PHP's `parse_str` layer (which decodes `%25→%` once before the app runs). The real probe sends `%252e` over HTTP; the app receives `%2e`. Fix: emulate with `parse_str('name='.raw)` inside the replay, then call the function (replay #2 PASS). Same lesson class as the C36 twin-depth fix: the replay must mirror the PRODUCTION PATH (depth + decoding layers), or a correct patch "fails" a wrong test.

## Node HTTP fixture contract host rule (forge Cycle 42, 2026-10-31)

- The sandbox serves the target at DNS name `target-service:8080`, NOT
  127.0.0.1:8080. A `test_contract.js` hardcoding 127.0.0.1 passes locally
  and FAILS baseline in-sandbox. Fixture contracts MUST try
  `target-service` first with 127.0.0.1 fallback (works both places).
  Red probes already know this; GREEN must write it into the contract.
## Global-state vulns break differential gates (forge Cycle 42, 2026-10-31)

- Prototype pollution (and any process-global-state vuln: caches, singletons,
  module-level flags) permanently alters the server after one hostile probe.
  Pre/post differential verification in a single long-lived server process
  then fails benign-after-hostile BY PHYSICS, not by model error. Do not
  burn attempts: park as hotspot unless the harness restarts the server
  between probe and regression. Prefer stateless fixtures (fresh DB per
  request like sqlite :memory:, pure functions of request input).

## Fixture-authorship quoting rule (forge Cycles 46-47, 2026-10-31)

- Sinks the model must reproduce in JSON payloads go in the LEAST-NESTED
  quoting available. `'" + prefix + "%'"` killed Blue 5x (schema faults);
  the identical vuln with `'... LIKE "' + pattern + '"'` cleared
  immediately. Suspected mechanism: nested quotes inside JSON strings
  break model-side escaping. Prefer double-quoted SQL strings and bind
  parameters outside the string literal entirely.

## Schema-fault attribution requires capture (forge Cycle 48, 2026-10-31)

- Never attribute a "Muse returned invalid JSON or an unexpected response
  schema" fault to a side (Red vs Blue) without the payload: the C48
  cluster looked Blue-side for 5 attempts (emit log shows Blue phase)
  but the captured payload proves the faulting role was
  project_red_verification_report. Set PURPLEBOX_LOG_RAW_RESPONSES to a
  directory to capture failing payloads (env-gated, off by default).
- Canonical shapes (login?next=, LIKE-search) risk Red second-pass
  hallucination of the training-dominant secure variant. Prefer
  shape-distinctive fixtures; F14 nested-quote rule demoted to
  coincidence pending its own capture.

## No subprocess execution inside the target service (forge Cycle 53, 2026-10-31)

- The target sandbox unreliably executes child processes (a3 failed
  even with correct exec bits; cause unidentified). Fixtures must NOT
  exec inside the target: keep write primitives in Gate-0 evidence
  (local, root) and assert the SPLIT/mutation over HTTP in the keyed
  loop. Split the proof across the trust boundary. Related: never
  rely on snapshot exec bits (chmod after copy); keep contract
  asserts total (no indexing).

## Reviewer-grounding quote (forge Cycle 55, 2026-10-31, UNPROVEN)

- When pass-2 contradicts pass-1 by hallucinating the textbook fix, add
  a GROUND TRUTH block to the contract quoting the fixture's actual
  (non-)checks verbatim ("contains NO allowlist, NO builtins
  restriction; the only check is X; judge supplied source only").
  Correlated with C55's clear; CONFOUNDED with streak-breaking — needs
  an A/B (same fixture, grounding on/off) before promotion to rule.
  Until then: include by default (cheap, possibly decisive).

## 2026-11-01 — physical `tui/` dir shadows root `tui.py` (GG2)

Wrong assumption: creating `web/`, `tui/`, `mcp/` marker packages alongside
root `tui.py` is additive and gate-safe. What the evidence showed: any
`tui/` directory with `__init__.py` makes `import tui` resolve to the package
instead of root `tui.py`, so `from tui import FIXTURE_ORDER` raises
ImportError and the gate goes red at collection. Fix: no physical category
dirs — `docs/{web,tui,mcp}/INDEX.md` maps are the form. Same reason root
`modules/` stays a shim and `tui.py` keeps its `modules.*` spellings.

## 2026-11-01 — swarm spawn misroutes contributor id to Anthropic (GG lead)

Wrong assumption: `swarm spawn model:"muse-spark-1.3-contributor"` (or
`model:"inherit"`) reaches the Meta route. What the evidence showed: the
router built a different-provider request for `muse-spark-1.3-contributor`, Anthropic
rejected it, and spawn refused 11x rather than substitute. Correct route per
`swarm list_models` is the openai-compatible `meta-muse` route with the
jcode credential — but the spawn path did not honor it from this session.
Workaround: proceed solo, one write at a time; re-attempt spawn only for
genuinely parallel writer work.

## 2026-11-01 — `ui_scan.py` needs the project venv for Chrome (GG5)

Wrong assumption: `python3 scripts/dev/ui_scan.py --browser chrome` works
with system python. What the evidence showed: the CDP drive path does
`import websockets`, which only exists in `.venv` — instant ModuleNotFoundError.
Firefox (WebDriver/urllib path) works on either. Rule: always run browser
proof as `.venv/bin/python scripts/dev/ui_scan.py ...`.

## 2026-11-01 — physical `web/` is safe, `tui/` is not (GG2 follow-up, webui-v3 branch)

Wrong assumption (carried from GG2): NO physical category dirs at all. What
the evidence showed: the shadowing trap is name-specific — root `tui.py`
occupies the `tui` import name, so only a `tui/` package dir breaks the gate.
`web/` has no root `web.py` counterpart, so a physical `web/` dir imports
cleanly and the gate stays green. Rule refined: physical dirs are allowed
unless a same-named top-level module exists; `tui/` stays a map, `web/` may
be physical. Verified: gate green after `web/` migration (contract suite).

## 2026-11-02 — intermittent session-container survivors are daemon-side, not a tracking bug (D1 closed-loop)

Wrong assumption: "one surviving running target per scan = untracked leak in `close()`" — so the fix must be more tracking.
Evidence: instrumented 1-, 2-, and 4-fixture runs with a `close()` spy all showed `tracked=1 net=1` and converged to zero residue for the spied sessions (`80c6d59d`, `013e3fd2`, `642933f5`, `3ab1e2ab`, `9f8e5c4d`, plus the full 4-fixture trace `795baeba/fd5dad2c/dca3513e/f1658f28`); `keep_tracked` (round 6 + F-01) covers transient-`remove` failures and `close()` surfaces persistent failure as `SandboxError` with the session label instead of dropping it. The survivors correlate with no code path — single runs converge, sequential runs intermittently leave one `Up` target that was demonstrably tracked at `close()` time with `cleanup_ok=True`.
Lesson: after `close()` returns success, a container that still shows `Up` is a daemon-side slow/stuck reaping outside the tracked contract, not an ownership bug. The reconciler is `main.py --cleanup` (label-filtered `remove_stale_resources` — removed 19+6 here, verified 0/0). Do not add more tracking; re-run `--cleanup` after proof batches and move on. Genuine leaks would show `cleanup_ok=False` or `SandboxError`, which never occurred in any instrumented run.

## 2026-11-02 — closed-loop session traps (competition-lockdown closeout)

- **Trap: `ruff check` flip-flops between "All checks passed" and I001 after moving an import.**
  Wrong assumption: one `--fix` run settles import sorting.
  Evidence: moving `_SNIPPET_LANGUAGE_BY_SUFFIX` into the top-level `mcp_bridge` import block needed two `--fix` passes plus a manual merge of the resulting duplicate `from modules.services.mcp_bridge import (...)` blocks; `format --check` stayed green throughout while `check` flipped. Fix pattern: merge duplicate from-blocks by hand, re-run `check`, repeat until stable (3 consecutive greens), then gate.
  Lesson: after touching top-level imports, run `ruff check` in a loop until it passes 3x; a single green is not stable.
- **Trap: wall-clock correlation lies across the Docker boundary (D1).**
  Wrong assumption: container `Created` timestamps share the shell clock, so "created 7s before run start" means "from another run".
  Evidence: shell `date` said 15:09 PST while the daemon stamped 16:08 for the same instant (~59 min skew). Session-label grouping (`--filter label=purplebox.session=<id>`) is the only valid attribution; timestamps across the boundary are not comparable.
  Lesson: never attribute containers by time; always group by session label.
- **Trap: pytest runs inside `dev.py check` can flake once and pass twice.**
  Wrong assumption: one red gate = real regression, must fix before merging.
  Evidence: final gate showed `1 failed, 1029 passed`, then two consecutive full runs (direct pytest + full gate) went 1030 green with no code change. No test was touched; the failure line was not captured (grep found no FAILED block — output buffering).
  Lesson: on a single-test gate red with no failure block captured, re-run the suite before touching code; two consecutive greens bracket a flake. Record it; do not chase it.
- **Trap: the write tool can report success on a file that never lands.**
  Wrong assumption: `write` replying "Created ..." means the file exists.
  Evidence (prior session, still true): two `edit` calls failed "old_string not found", then `read` said "File not found" — the create never landed. Shell heredoc worked first try.
  Lesson: after `write` of a NEW file, verify with `ls`/`read` before editing it.

## Function-local import shadows top-level name (2026-11-03, branch feature/full-surface-parity)

- **Trap: `from x import name` inside an `if` block makes `name` function-local for the WHOLE function — sibling branches reading the top-level `name` then raise `UnboundLocalError`.**
  Wrong assumption: "a lazy import inside one branch is contained to that branch." Python scoping is function-wide at compile time: c5's `--showcase-status` dispatch did a lazy `from modules.services.sms_api import showcase_status` while c3's `--ops-status` dispatch (same `main()`) called the top-level `showcase_status`. Running `--ops-status` skipped the import line, leaving the local unbound — the generic handler reported "could not start (UnboundLocalError)". The failure appeared only when both slices merged; each slice was green alone.
  Evidence: 3 ops tests failed post-merge, `grep showcase main.py` showed the local import at :3280 vs top-level at :43 and the unconditional call at :3353; deleting the lazy import (top-level already provides it) → 23/23 green.
  Lesson: never lazy-import a name that is also top-level-imported in the same module — or that any merged slice may top-level-import. One import site per name per module; grep co-slices before adding a second.

## Repo-intake-live merge reconciliations (2026-11-03, branch feature/repo-intake-live)

- **Trap: six green slices + a red merge — merged code is unverified until the merged gate runs.**
  Wrong assumption: "each slice was gate-green alone, so the merge is green." Slice-32's None short-circuit (`if not commit_hash: parsed=None`) bypassed the spec constructor that slice-31 made optional-aware — HEAD-as-is died at the intake gate with a 40-hex lecture. Each slice green alone, merged RED.
  Evidence: `test_ingest_accepts_then_workflow_receives...HEAD...` failed post-merge; slice-31's spec accepted `(GOOD_URL, None)`, slice-32 never called it for None.
  Lesson: the merge commit gets its own RED-first run, not just each slice. Budget the reconciliation pass before promising ship.
- **Trap: optional-commit display code assumed the old required shape.**
  Wrong assumption: `commit_hash[:12]` is safe because the parser requires the pair.
  Evidence: two `ValueError: None has no len()` sites in main.py WS progress + refusal paths after D2 made commit optional; fixed with `(spec.commit_hash or 'HEAD')[:12]` at both sites (lines ~2492, ~2534).
  Lesson: when a LAW/pin changes a field from required to optional, grep every `[:12]`, `len(`, and f-string interpolation of that field in the same commit.
- **Trap: stale F-204 refusal pins outlive the refusal.**
  Wrong assumption: "the gate will tell me which pins are stale." It did — 4 pins across 3 files asserted `exit 2 on bare --ingest-repo`, `not fetched/not verified` refusal text, and refusal-before-runtime-detection. Each needed a retarget to the live path (parse-clean + HEAD default, mocked-Docker staging into the workflow, README-only fails at runtime detection not fetch).
  Evidence: `test_ingest_args_red.py::test_ingest_repo_requires_commit_hash`, `test_sa_main_red.py::test_f204...`, `test_w22_ingest_wire_red.py` pair.
  Lesson: when a brief retires a refusal, grep the refusal's signature strings (`not fetched`, `requires --`, `never fetched`) across tests/ in the same commit — the pins that enforced the old rule are now the bug.
- **Trap: the fake workflow must return a result shaped like the real one.**
  Wrong assumption: `return None` from a mocked `execute_project_workflow` is fine because the test only checks routing.
  Evidence: retargeted F-204 WS test routed correctly, then died at `result.model_dump()` → `AttributeError: NoneType`. A `_FakeResult` with the 7-field `model_dump()` dict (target/status/message/diff/cleanup_ok/cycles/total_tokens+cost_usd) fixed it — same shape w22 already used.
  Lesson: mocks must satisfy the downstream contract, not just the assertion under test. Copy the existing fake-result shape instead of inventing a thinner one.

## Demo live bugs (2026-11-03, branch feature/test-web-2026-11-03)

- **Trap: the segmented test that never tested the arrows.**
  Wrong assumption: "the demo setup controls work with a keyboard because the stepper test covers ArrowUp/Down." That test drove the *stepper* input; the *segmented* radiogroup ("Operational mode") had its own keydown map with only left/right — up/down silently no-op'd on exactly the two-option control where wrap matters most.
  Evidence: node probe of the handler map pre-fix (`ArrowUp -> undefined`); post-fix round-trip Right/Down/Up/Left returns to start.
  Lesson: one keyboard test per widget type, not per page. When a form file has N keydown handlers, each needs its own pin.
- **Trap: retry covered statuses but not the transport.**
  Wrong assumption: "RETRY_MAX_ATTEMPTS = 2 means two tries." Only for HTTP *statuses*. An httpx.HTTPError (timeout/DNS/reset) raised AgentError on attempt 0 — the loop's second iteration never ran. A single blip produced status=error and the demo's "Scan could not complete / Nothing was changed" verdict.
  Evidence: RED pin (blip-then-success) failed pre-fix, green post-fix; persistent-failure pin still fails closed with the identical no-fallback message in exactly 2 calls.
  Lesson: when a retry loop has two failure ingresses (status vs exception), pin both. SPEC's no-fallback lock constrains *providers*, not *attempts* — one bounded re-try of the same provider is policy-safe.

## Retry-budget change retargets (2026-11-03, branch feature/test-web-2026-11-03)

- **Trap: the attempt index is not the failure count.**
  Wrong assumption: passing `attempt` (0-based) to the delay helper yields immediate/10s/20s. It yields 0.5s/10s/20s — the first *failure* must map to the immediate slot, so the helper takes a 1-based *failure count* incremented per failure, and both call sites (status path, transport path) bump the same counter. My own new pin caught it ([0.5, 10] vs expected [10, 20]) before the gate did.
  Evidence: `_retry_delay_seconds(failures, ...)` + `consecutive_failures` in `_request`; corrected pin `test_transport_ladder_waits_immediate_10s_then_20s` asserts [~0.5, ~10, ~20].
  Lesson: name delay-helper params for what they count (`failures`, never `attempt`/`index`), and assert the full sleep vector in the pin, not just the last value.
- **Trap: raising the retry budget breaks every pin that counted attempts.**
  Wrong assumption: "RETRY_MAX_ATTEMPTS 2→4 is a one-line change." Eight pins across four files asserted exactly 2 calls / 1 sleep / `== 2` — all RED post-change, all correct-by-construction under the old budget. Each needed retargeting to the ladder (4 calls, [immediate, 10s, 20s] sleeps) while keeping its original *intent* (no body leak, rate-limit named, hostile Retry-After capped, UI survivable).
  Evidence: `test_config_agents`, `test_w29_load_red`, `test_w13_throttle_ui_red`, `test_recovery_convergence_red` retargeted in the same commit; gate green after.
  Lesson: a budget constant is a load-bearing contract — grep every reference in tests/ before changing it, and retarget in the same commit as the implementation.

## Stepper zombie hold-timers (2026-11-03, branch feature/test-web-2026-11-03)

- **Trap: the pressed button does not survive its own click.**
  Wrong assumption: "pointerdown ... pointerup bracket one press, so the
  repeat timer always gets cleared." bump()->set() fires onChange->refresh->
  setContext->render()->replaceChildren, which DESTROYS the pressed button
  mid-press. pointerup lands on the NEW node and clears the NEW closure's
  (idle) timer; the OLD closure's pending setTimeout fires as a zombie,
  bumps, re-renders, reschedules — a stuck ~14 Hz repeat. One click leaves
  one invisible zombie; opposing clicks (+ then -) fight forever: the
  visible 1<->2 sweep oscillation. Every further click adds another zombie,
  and each zombie rewrite flickers the Request preview.
  Evidence: traced from the hold()/render()/refresh() call chain (headless
  Firefox unusable here — desktop profile lock — so the pin simulates the
  DOM-lifetime race in node); post-fix simulation shows exactly one bump
  per click with the zombie tick killed.
  Lesson: any setTimeout/setInterval chained from a DOM event must check
  its node's liveness (`btn.isConnected`) before re-firing — especially
  when the handler synchronously triggers a re-render. The clearer only
  works if it shares a lifetime with the timer.

## Timeout + preset pass (2026-11-03, branch feature/test-web-2026-11-03)

- **Trap: the timeout knob existed but reached nothing per-run.**
  Wrong assumption: "META_MUSE_TIMEOUT_SECONDS covers it — the deep pass
  just needs a bigger env value." The env knob required a server restart
  per budget, the default (180 s) sat below the standard red call's own
  166 s answer time, and 0 was rejected — so "wait as long as needed" was
  inexpressible. The dry run proved it: 4 x 180 s timeouts + ladder waits =
  392 s of nothing, killing a 10-minute live run.
  Evidence: `logs/traces/core.agents.jsonl` red-pass 392161 ms error x2
  (tonight + the earlier 90 s deep timeout at 19:58).
  Lesson: a budget knob that cannot be set per-run and cannot express
  "unlimited" is a fixed constant with extra steps. Ship default 300,
  0 = uncapped read, `?timeout_s=` + `--timeout-s` + MCP/library params.
- **Trap: presets via o.values lose to stored choices — or clobber them.**
  Wrong assumption: "pass values into OptionForm and first visit gets the
  recording setup." Constructor merged stored-over-values, so a stale
  localStorage would silently override the director's presets — or, if
  reversed naively, presets would clobber a returning user's explicit
  picks. The merge order is now schema < presets < stored, documented in
  form.js: presets seed first visits, stored choices always win after.
  Lesson: any "sensible default" injection must state its precedence in
  a comment at the merge site, or the next surface will re-break it.

## Ingest auto-detect (2026-11-03, Part 2 dry run)

- **Trap: the server demanded what the form never collected.**
  Wrong assumption: "the ingest form sends everything the server needs."
  The console sent URL + contract only; the server required runtime_command
  or file_list and refused with "runtime_command is required when file_list
  is not given." The form had no field for either — the demand existed only
  server-side. The Part 2 dry run died at the gate with zero scan.
  Evidence: console showed `invalid` + the message; `intake_repo_to_snapshot`
  raises when both are None.
  Fix: with neither present, the WS path clones with a placeholder then
  resolves the real runtime from the cloned tree via detect_runtime (same
  derivation the library path uses). Explicit argv and file_list paths
  untouched; undetectable trees still fail closed with an actionable
  "pass an explicit runtime_command" message. Plus an optional
  "Start command" field on the ingest form so power users can pin the argv.
  Lesson: when server and form are built in different slices, the contract
  lives in NEITHER file — pin the wire shape (required vs optional keys)
  in a shared test, or the UI will keep sending frames the server refuses.
- **Trap: three branches, two conditions.**
  Wrong assumption: "if/else covers explicit vs auto." The original had
  `if intake_files is None: clone(...) / else: clone(..., file_list)`.
  Adding auto-detect inside the first branch while explicit+no-file_list
  still routes there sent `["true"]`... no — sent the explicit argv into
  the placeholder path. The condition must be three-way: auto (both None),
  file_list, explicit-argv. My own RED pin caught it (expected explicit
  argv, got placeholder).
  Lesson: when a branch grows a third case, rewrite the condition as an
  explicit three-way from the start — `if/else` with a hidden middle case
  is a bug waiting for the next slice.

## Docker 29 get_archive vs read-only/tmpfs (2026-11-03, Part 2 dry run)

- **Trap: get_archive 404s on read-only/tmpfs-mounted containers.**
  Wrong assumption: "the clone wrote bytes, so get_archive can read them."
  On Docker 29 (overlay2 here), archiving ANY path inside a `read_only`
  and/or tmpfs-mounted container 404s ("Could not find the file") — even
  though the same archive call works on plain containers. Bisected across
  5 variants (baseline/user/readonly/tmpfs/combos): baseline + user-only
  pass, every readonly/tmpfs combination fails. The clone DID succeed
  (exit 0, bytes on disk, verified via logs) — only the extraction lied.
  Evidence: `/work/repo` 404s but `/work` and `/` return; `/work` tar holds
  a single `work` dir entry (tmpfs contents invisible to the daemon's
  archive path).
  Fix: clone container runs with a WRITABLE root (still no host mounts,
  still uid 10001, still all-caps-dropped, still no-new-privileges) and
  clones into plain `/work`. Only the staged tree leaves via get_archive.
  Lesson: the "hardened container" checklist (read-only + tmpfs) breaks
  Docker's own archive API on this storage driver. Harden the PROBE
  containers (they never export bytes); the CLONE container must stay
  readable. Bisect isolation flags against the extraction API, not just
  the workload.
- **Trap: the tree prefix moved and nobody told the pins.**
  Wrong assumption: "tree/ paths are stable." Stripping the repo dir
  (`tree/repo/app.js` → `tree/app.js`) broke 3 pins across 3 files that
  asserted the old prefix. Retargeted in the same commit.
  Lesson: a path-shape change is a contract change — grep `tree/` across
  tests/ in the same commit.

## Ingest binary-blob refusal (2026-11-04, Part 2 dry run)

- **Trap: refusing the whole tree for one font file.**
  Wrong assumption: "non-UTF-8 bytes in the snapshot = hostile or broken
  input, refuse." AnyCam's tree carries DejaVuSans.ttf (Rust GUI assets) —
  a legitimate repo file that is neither model-readable nor patchable.
  The old code refused the entire 44-file staging over one font. The
  "pass an explicit runtime_command" hint was doubly wrong: the argv was
  already pinned, the blob was the problem.
  Evidence: `ValueError: staged snapshot holds non-UTF-8 bytes at
  'tree/rust/src/gui/assets/DejaVuSans.ttf'` killed the Part 2 run at the
  ingest gate after the clone fix landed.
  Fix: skip undecodable blobs, keep the text tree. The runtime argv + text
  files carry the verification; fonts/images/compiled artifacts ride along
  as names only (still visible to red as attack surface, never sent as
  model text). A tree with ZERO decodable text files still needs a guard
  (future: refuse "no text files staged" explicitly rather than passing
  an empty file set downstream).
  Lesson: fail-closed means refusing the THREAT, not the bystander. A
  blob is not an attack — it is absence of signal. Skip absence, refuse
  malice.

## Ingest target writable scratch cwd (2026-11-04, Part 2 dry run)

- **Trap: staged source is not a working directory.**
  Wrong assumption: "the target runs with cwd=/workspace, where its files
  are." Real apps (AnyCam: `./cert`) persist runtime state under cwd —
  and /workspace is the read-only staged source. `OSError: [Errno 30]
  Read-only file system: '/workspace/cert'` killed the Part 2 run at
  target start, after the clone fix landed.
  Evidence: target container exited 1 with the makedirs traceback; only
  the SECOND failure in the chain (clone extraction, then this).
  Fix: the ingest target wrapper copies the tree to /tmp/scratch (bounded
  tmpfs: rw, nosuid, nodev, uid 10001) and execs the runtime argv there.
  Relative reads find staged bytes, relative writes land on scratch, never
  on staged bytes. Absolute writes still fail closed on the read-only
  root. Plus openssl pinned into the target image (AnyCam's self-signed
  cert needs it; the base had node+php only).
  Lesson: fixtures never write, so the read-only-everywhere posture went
  unchallenged until a real app arrived. Any "real project" target needs
  a writable scratch cwd by default — pristine source and working state
  are different directories, always.

## Ingest service wrapper (2026-11-04, Part 2 dry run)

- **Trap: the harness only probes 8080, but real repos serve nothing there.**
  Wrong assumption: "detect_runtime finds the entrypoint, the target runs
  it, readiness passes." AnyCam IS a server — but on 8443/MJPEG/portal
  paths, with cert generation that needs openssl + LAN. The entrypoint
  runs, serves everything except 8080, and the 10 s readiness probe fails
  closed. Correct refusal, wrong outcome for the video: the harness can
  only verify HTTP-on-8080 targets.
  Evidence: Part 2 dry run attempt 4, "Ingested target did not become
  ready", target logs showing AnyCam alive on its own ports.
  Fix: with no explicit argv, the WS ingest path wraps the staged tree as
  a plain stdlib HTTP service on 8080 — every decodable staged text file
  served at /<path>, /files lists, /health answers, / serves index or
  listing. Red/blue work against REAL staged bytes over the REAL probe
  surface; the original entrypoint is never executed by the harness
  (explicit argv still runs the real thing).
  Lesson: the probe surface is the contract. A target that cannot speak
  it must be ADAPTED to it (serve its bytes), not executed and hoped.
  The day a second probe shape exists, the wrapper gains a sibling —
  not a flag.
- **Trap: ARG_MAX kills the inline wrapper.**
  Wrong assumption: "the file map fits in argv." AnyCam's 41 text files
  serialize to 447 KB — triple the 128 KB exec limit. OSError E2BIG, no
  fallback. Fix: the map rides as tree/.wrapper_files.json (a staged file
  like any other, hidden from its own listing); the argv is a fixed small
  loader (~2 KB). Data travels as files, never as arguments.
  Lesson: bytes that scale with the repo must never ride the command
  line. If it grows with input size, it is a file.
- **Trap: TMPDIR vs cwd breaks map-relative loading in tests.**
  Wrong assumption: "cwd=tmp_path means relative opens see tmp_path."
  On this box pytest's tmp_path honors $TMPDIR (~/.jcode/scratch, mounted
  volume) while the loader child resolved relatives against the process
  cwd — map file present on disk, "not found" at boot. Production is
  unaffected (sandbox cwd IS the staged tree). The test passes the map by
  absolute path; the loader keeps its relative candidates.
  Lesson: a test that boots a subprocess must not assume tmp_path and
  child-cwd agree — or it will fail only on machines with redirected
  TMPDIR. Prefer absolute paths in test harnesses; keep relatives in
  shipped code.

## Staged service wrapper + Docker timeouts (2026-11-04, Part 2 dry run)

- **Trap: non-HTTP repos cannot pass an HTTP readiness gate.**
  Wrong assumption: "detect the entrypoint, run it, probe 8080." AnyCam
  binds 8443/MJPEG/portal paths and needs openssl + LAN for its cert —
  none of which is 8080. The 10 s readiness probe failed closed, correctly
  but uselessly for the video: the harness could only verify HTTP-shaped
  targets, so "any repo" really meant "any web app."
  Evidence: Part 2 attempt 5, "Ingested target did not become ready",
  AnyCam alive on its own ports in the sandbox (verified via exec).
  Fix: with no explicit argv, the WS ingest path wraps the staged tree as
  a plain stdlib HTTP service on 8080 — every decodable staged text file
  served at /<path>, /files lists, /health answers, / serves the tree's
  own index page when one exists (the app's front door, not a listing).
  Red/blue work against REAL staged bytes over the REAL probe surface;
  the original entrypoint is never executed by the harness (explicit argv
  still runs the real thing — same three-way branch as auto-detect).
  Any repo is now verifiable for static content exposure; behaviour-level
  verification of non-HTTP runtimes stays an explicit-argv job.
  Lesson: the probe surface is the contract. Adapt the target TO it
  (serve its bytes) rather than executing arbitrary code and hoping.
- **Trap: ARG_MAX kills inline file maps.**
  Wrong assumption: "the file map fits in argv." 41 files → 447 KB of
  JSON, triple the 128 KB exec limit (E2BIG). Fix: the map rides as
  tree/.wrapper_files.json (a staged file, hidden from its own listing);
  the argv is a fixed ~2 KB loader. Data that scales with input travels
  as files, never as arguments.
- **Trap: Docker daemon timeouts under image-build load.**
  Wrong assumption: "30 s docker timeout is plenty." The baseline check
  failed with UnixHTTPConnectionPool Read timed out — not a code bug, a
  wedged daemon (build cache pressure + orphaned containers + a stray
  system AnyCam squatting on 8080 during tests). Fix: default
  docker_timeout_seconds 30 → 120 (env + example.env), pruned orphans,
  and the wrapper unit test uses a random free port with a stale-server
  guard instead of assuming 8080 is free.
  Lesson: "project check failed before producing a result" with a
  ConnectionError underneath is infrastructure, not logic — check daemon
  health (`docker system df`, orphans, port squatters) before touching
  workflow code.

## OOM naming + container budget knobs (2026-11-04, Part 2 dry run)

- **Trap: exit 137 masquerades as a generic check failure.**
  Wrong assumption: "the wait call failed, so the check failed." A
  SIGKILLed container (OOMKilled, exit 137) wedges `container.wait` with a
  ConnectionError — and the old code reported only "Project check failed
  before producing a result." 20 minutes of daemon debugging before the
  events log showed `die ... exitCode=137`. The fix names the killer:
  inspect OOMKilled/ExitCode on wait failure and say the memory limit +
  the knob (PURPLEBOX_CONTAINER_MEM_LIMIT). A SIGKILL must never read as
  a logic failure.
  Evidence: warmed-up wrapper container, `die execDuration=20 exitCode=137`
  in docker events; baseline direct-repro then passed at 1g after failing
  at 256m.
  Lesson: every fail-closed error should name the most likely resource
  cause when one exists. "Check failed" with no resource hint is a trap
  that burns the next debugger's night.
- **Trap: raising a default breaks the dead-knob pins.**
  Wrong assumption: "256m → 1g is a one-line change." Two TRUE-DEAD pins
  asserted the mem/cpu env vars do NOT exist — they were written when the
  knobs were dead, and the OOM fix made them live (PURPLEBOX_CONTAINER_
  MEM_LIMIT/_CPU_NANO). Retargeted: dead list shrinks, new LIVE test pins
  the env wiring. Same commit, same gate.
  Lesson: "dead" is a temporary property. When a knob goes live, its pins
  must flip from pinned-dead to pinned-live in the same commit — or the
  gate enforces the old world.

## wait() timeout means alive, not failed (2026-11-04, Part 2 dry run)

- **Trap: the wrong ConnectionError.**
  Wrong assumption: "the codebase has one ConnectionError." The
  `except ConnectionError` in run_project_check caught the BUILTIN — but
  the Docker SDK raises `requests.exceptions.ConnectionError` (urllib3
  ReadTimeoutError underneath). The branch never fired; every still-
  running baseline fell through to the generic SandboxError. The code was
  right, the exception type was wrong — verified by printing the actual
  type (`requests.exceptions.ConnectionError: ... Read timed out`).
  Evidence: sleeper test (300 s sleep) raised SandboxError pre-fix,
  timed_out post-fix; quick-exit still returns 0 fast.
  Lesson: `except ConnectionError` in a file that talks HTTP is a trap —
  requests, urllib3, and builtin all define one. Name the module
  (`requests.exceptions.ConnectionError`) or catch the behavior (message
  match), never the bare name.
- **Trap: fixing it twice.**
  Wrong assumption: the first edit (bare ConnectionError + message match)
  was sufficient. It was not — the handler never ran at all. Always
  re-run the LIVE repro after the fix, not just the unit pin: the pin
  asserted source text ("STILL-"), which passed while the runtime path
  still failed. The sleeper/baseline repro is the real gate.
  Lesson: a source-text pin proves the comment exists. Only a live
  behavioral repro proves the branch runs. Both are needed — neither
  alone.

## Wrapper smoke vs serve argv (2026-11-04, Part 2 dry run)

- **Trap: the probe surface is not a regression command.**
  Wrong assumption: "the target argv runs for both probing and baseline."
  The wrapper SERVES forever by design — so the baseline regression check
  (which waits for exit) wedged until the daemon timed out, then failed
  the run as "Project check failed" / "regression failed". The 9th Part 2
  attempt died on this: correct refusal, wrong command.
  Evidence: attempt 9, "Original project failed its preserved regression
  command"; the long-lived wrapper never exits by design.
  Fix: the wrapper ships TWO argv — serve (long-lived 8080, the probe
  surface, `runtime_command`) and `--smoke` (verifies the file map,
  prints the servable count, exits 0 — the preserved `regression_command`).
  The harness runs smoke for baseline + post-patch regression, serve for
  probes. Explicit-argv runs keep their real regression command.
  Lesson: a serving target and a checking target are different verbs.
  Any wrapper that serves forever must also ship an exit-0 health verb —
  or the baseline will (correctly) refuse a run that never ends.

## Verifier probe surface: cyber, not just text (2026-11-04, Part 2 dry run)

- **Trap: the wrapper serves text, but red needs sockets.**
  Wrong assumption: "serving staged files on 8080 generalizes the probe
  surface." It generalizes the CONTENT, not the CHANNEL. A purple-team
  probe must open real connections: raw TCP/UDP to arbitrary ports, TLS
  handshakes, DNS — cyber, not just HTTP-text. The verifier containers
  already rode the scan network (no network_mode=none on the RUNTIME —
  only the image-build STAGE is isolated), so the capability was there;
  only the red prompt still said "http://target-service:8080" as if it
  were the only surface.
  Evidence: live proof — a raw-socket probe from a verifier container hit
  a listening target on port 9999, resolved target-service via DNS, and
  confirmed the TLS module (test_verifier_reaches_target_on_arbitrary_port).
  Fix: all four red prompts now describe the full surface (8080 file
  service by default + direct sockets/TLS/DNS to target-service on any
  port). socket/ssl were never forbidden (only subprocess/pty/ctypes/
  multiprocessing/shutil/resource/signal are) — no allowlist change
  needed, just permission stated.
  Lesson: an unadvertised capability is an unused capability. The network
  plumbing existed; the prompt was the lock. When expanding a surface,
  check what the sandbox ALREADY permits before building new pipes.

## Overnight full-spectrum traps (2026-11-04, branch feature/overnight-full-spectrum)
- **Trap: target image has no git, so HEAD pin fails exit 127.** Wrong
  assumption: `target_base_image` can run `git ls-remote`. It cannot
  (`which git` empty). Fix: pin resolution runs in `clone_base_image`
  (purplebox-clone-base has git 2.49.1). File: `library/services/sms_api.py`
  `_resolve_head_commit`.
- **Trap: basename vs relpath in runtime detect.** `detect_runtime` got
  `tree/anycam.py` (staged relpath) but compared against bare `anycam.py`;
  AnyCam fell through to ValueError. Fix: `_python_command` + bare-name
  fallback compare basenames, return the staged relpath. Files:
  `library/services/repo_intake.py`.
- **Trap: scan_repo ran the raw entrypoint instead of the wrapper.**
  The WS default wraps the staged tree as an HTTP service (serve argv +
  `--smoke` regression); the library path ran `python3 tree/anycam.py`
  (long-lived camera app) as the regression command and failed the
  baseline. Fix: `scan_repo` calls `build_service_wrapper` (idempotent —
  skips when `repo.smoke_command` present) and uses serve/smoke argv.
  File: `library/services/sms_api.py`.
- **Trap: binary sweep correctly caps at 3, source goes to 5.** The chain
  pass (4) is refused fail-closed on binaries (chain verdicts need 3-link
  evidence the harness cannot express), so coverage (5) is unreachable
  there. Do not "fix" the binary 3-cap to 5. Files:
  `library/workflows/binary_sweep.py`, `library/services/mcp_bridge.py`
  (binary tool stays maximum 3).
- **Trap: persona-count pins encode the roster size.** Adding red
  personas (5→7: Bloodsniffer, Blacklight) breaks wrap-around math and
  length asserts in 3 test files. Retarget all three together:
  `test_deep_scan.py`, `test_verify_r2_redact_red.py`.
- **Trap: pass-cap pins live in 4+ files.** Raising 4→5 touches
  `main.py` (WS gate, CLI clamp ×2, help), `sms_api.py` (×2),
  `tui.py` (×4), `mcp_bridge.py` (source tool only), `schema.js`
  (max + labels), plus `test_chain_live_reach_red.py`,
  `test_cli_parity.py`, `test_audit_m_drift.py`,
  `test_truth_sweep_fixes.py`, `test_verify_r2_svc_red.py`.
  Miss one and the gate fails, not the feature.
