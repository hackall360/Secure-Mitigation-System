# TRAPS — things that looked correct and were not

One growing map per `docs/guides/WORKFLOWS.md`. Highest value first: the
wrong assumption, then what the evidence actually showed. Link new entries
here, not in scattered notes.

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
