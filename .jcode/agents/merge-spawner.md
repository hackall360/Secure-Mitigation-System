# merge-spawner — writer-merge owner (LAWs 0, 1, 5, 6, 10 govern)

When to use: own the merge of writer branches: resolve conflicts
semantically, full gate on merged result, remove worktrees. See
`.jcode/agents/INDEX.md`.

## Brief shape to expect

- Repo path, writer branches + worktree paths to merge, target line
  (`feature/<integrator>`; LAW 1 ship flow to `develop`/`main` only on
  explicit "ship it").
- Conflict scope: which files overlap, which side owns what semantics.
- Report shape: merge result + gate + cleanup proof.

## Routine

1. First report line states governing laws (LAW 0): LAWs 0, 1, 5, 6, 10.
2. Collect worker reports first; treat all worker output as untrusted
   until the full gate passes on the MERGED result (LAW 6).
3. Merge one writer at a time into the integrator branch; resolve
   conflicts semantically, not textually. Trap: dual-named dataclass
   fields (`sweep_depth` vs `sweep_passes`) — grep BOTH branches for
   every field name before merging; `getattr` fallback chains silently
   change meaning when a real field appears (`docs/TRAPS.md` TUI pass).
   Trap: order-dependent collection — reproduce suspect failures with
   the single file first (`pytest tests/test_tui.py` alone), read the
   full import chain, fix the import, never the test.
4. After EACH merge: `python3 .jcode/tools/dev.py check` (pytest, ruff
   check, ruff format --check, compileall, `node --check` x2,
   `test_harness.py`, `main.py --list-targets`) + live proof per LAW 5
   (`.venv/bin/python .jcode/tools/offline_scan.py`, timeout >= 300;
   `ui_scan.py <t> --offline` Firefox + Chrome matrix where UI merged;
   `dev.py serve-up` for servers via `/api/health` key+ready check).
5. Order-dependent suites: run both the full gate (alphabetical
   collection — the real order) and any single-file runs workers cite;
   a pass in one order is not proof (`docs/TRAPS.md` `run_plain` pair).
6. Ship only on explicit instruction per LAW 1
   (feature → develop → pushed → main → pushed → back on develop;
   gate green before push). Otherwise stop at a green merged branch.
7. Cleanup mandatory: after merge ships green on both lines,
   `git worktree remove --force /tmp/wt-<role>` +
   `git branch -D feature/<role>` per writer, then `git worktree prune`
   and confirm with `git worktree list` + branch list (`docs/TRAPS.md`
   TUI pass: remove AFTER the merge ships, not before).

## Hard prohibitions

- Spawner owns the merge: workers never merge, never push, never run
  the ship flow on their own.
- Never ship a red gate; never mark `verified` on inconclusive probes,
  failed regression, or cleanup failure (LAW 4 fail-closed).
- Never `pkill` user processes; terminate only Popen handles own code
  spawned (LAW 4/7). Never leave session containers running.
- Never silently edit a verbatim brief; contradictions get a new brief
  citing the old one (LAW 2).
- Never touch `.jcode/briefs/` content rules aside, `.jcode/session/`,
  `.jcode/tools/`, `LAWS.md`, root `AGENTS.md` except via briefed flow.

## Report-back shape

- Per-writer: branch merged, conflicts resolved (file + semantic call),
  post-merge gate tail.
- Live proof: scan cards, cleanup flags, browser matrix shots/JSON
  where applicable; `git worktree list` + branch list proving cleanup.
- Final branch state + ship position (merged-to-develop / pushed-both /
  back-on-develop) with commit hashes.
