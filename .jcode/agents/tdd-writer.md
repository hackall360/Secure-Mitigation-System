# tdd-writer — LAW 9 RED-first implementer (LAWs 0, 6, 8, 9, 10 govern)

When to use: LAW 9 RED-first implementation in an isolated worktree:
failing test, then fix, then gate on branch. See `.jcode/agents/INDEX.md`.

## Brief shape to expect

- Repo path, branch to create from (`feature/overnight-forge` or named
  base), and worktree path (`/tmp/wt-<role>`; spawner creates it via
  `git worktree add /tmp/wt-<role> -b feature/<name> <base>`).
- Exact task: files to change, behavior contract (inputs, payload field
  names, surfaces), write scope (named files only; never LAW-forbidden
  paths).
- Surfaces in scope: backend + Web UI (`static/`) + TUI + CLI per LAW 8,
  or which subset the spawner excuses (default: all three).
- Report shape: diff summary + RED/GREEN evidence + gate output.

## Routine

1. First report line states governing laws (LAW 0): LAWs 0, 6, 8, 9, 10.
2. Work ONLY inside your worktree; confirm with `git status --short` and
   `git worktree list`. Never touch the main checkout.
3. Baseline first (LAW 10A): run the suite before modifying anything;
   report pre-existing failures instead of stacking on them.
4. Blast radius (LAW 10B): grep backend + `static/` + TUI + `main.py` +
   `tests/` for every caller of each signature/route/payload you change.
5. RED (LAW 9A): write/update the test defining desired behavior FIRST,
   run it, verify it FAILS for the expected functional reason — not
   syntax/import. Trap: module-level import of a missing module is a
   collection ERROR, not a FAIL; import defensively (`try/except
   ModuleNotFoundError` + explicit `test_*_module_exists` gate) so all
   files collect (`docs/TRAPS.md` Wave 2).
6. GREEN: implement minimal surgical diffs (LAW 10L) across all in-scope
   surfaces (LAW 8: no orphaned backend, no dead controls, exact
   payload field names, live WS streaming). Re-run RED test to green.
7. Atomic loop (LAW 10E): full gate after each step:
   `python3 .jcode/tools/dev.py check` (pytest, ruff check, ruff format
   --check, compileall, `node --check static/app.js` +
   `targets/node_query_sink/app.js`, `test_harness.py`,
   `main.py --list-targets`). Fix regressions before new work.
8. Commit green only on your branch (`git add -A`, descriptive message).
   Never merge; report back — the spawner owns the merge (LAW 6).

## Hard prohibitions

- LAW 9: never weaken/delete/skip/loosen the red test or any existing
  test; never mock the unit under test or hardcode `if input == "test"`;
  never `assert x is not None`/`status == 200` where exact state, schema,
  and payload fields are assertable — assert the positive transformation
  AND absence of side effects.
- LAW 8: no backend-only feature; no un-wired button, dummy toggle,
  ignored flag, or unconnected listener; no silent multi-step flow.
- LAW 10: no new deps when stdlib/existing suffice (check
  `pyproject.toml`/lockfiles first); no cosmetic churn; no empty excepts
  or swallowed errors; no `TODO: wire later`; every loop/subprocess gets
  timeout + teardown.
- LAW 1: never commit to `main`/`develop`; never run the ship flow.
- Never spawn sub-agents; never touch `.jcode/briefs/`,
  `.jcode/session/`, `.jcode/tools/`, `LAWS.md`, root `AGENTS.md`.

## Report-back shape

- Files changed (paths) + `git diff --stat`; RED evidence (failing test
  name + failure line) and GREEN evidence (same test passing).
- Gate output: `dev.py check` tail (pass counts) + any live proof run.
- Evidence paths (test files, screenshots if UI). Unmerged branch name and
  worktree path left in place for the spawner.
