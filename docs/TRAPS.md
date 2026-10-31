# TRAPS — things that looked correct and were not

One growing map per `docs/guides/WORKFLOWS.md`. Highest value first: the
wrong assumption, then what the evidence actually showed. Link new entries
here, not in scattered notes.

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
