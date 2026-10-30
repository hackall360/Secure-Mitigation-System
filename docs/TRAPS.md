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
