# busy-guard — admission-lock atomicity prover (LAWs 0, 5, 6, 9 govern)

When to use: any task touching scan admission (`scan_lock`, `busy`/`-32001`,
`async with lock`) on any surface (WS/MCP/CLI/TUI). See
`.jcode/agents/INDEX.md`. Built from the F-02 resilience fix (2026-11-01):
check-then-gap-then-acquire lets two callers serialize instead of refusing.

## Brief shape to expect

- Repo path, branch, the admission site(s) (`main.py` `run_socket` + `/mcp`
  branches, or `tui.py` dispatch), and the expected loser contract
  (`busy`+1013 on WS, `-32001` on MCP).
- Write scope: `tests/test_*_red.py` lock-step proofs + the re-check edit at
  the named site(s); no other surfaces unless the spawner lists them.

## Routine

1. First report line states governing laws (LAW 0): LAWs 0, 5, 6, 9.
2. RED-first (LAW 9): write the lock-step proof BEFORE touching admission —
   two coroutines, old shape (check, `await sleep(gap)`, unconditional
   acquire) must yield `['A:ran', 'B:ran']`; new shape (re-check immediately
   before acquire, no awaits between) must yield `['A:ran', 'B:busy']`.
   Run it; verify the old shape FAILS the refusal assertion for the expected
   functional reason.
3. Implement: re-check `locked()` immediately before `acquire()` with no
   awaits between (atomic in one event-loop step); on loss, send the loser
   contract and return WITHOUT acquiring; release-then-`async with` for the
   winner body (asyncio.Lock is not reentrant — acquire-then-release-then-`async
   with` is the shape; see `main.py` WS path).
4. Live proof: slow-holder socket + second socket must get `busy` (frames
   include `{"type": "busy"}`) + close code 1013 (WS) or `-32001` (MCP);
   `/api/health` shows `busy: true` during the hold.
5. Neighbor check: entrypoint + negatives + MCP suites green
   (`test_project_entrypoints.py`, `test_ws_negatives_red.py`,
   `test_mcp_server.py`).
6. Full gate green before reporting; commit on your branch only (spawner owns
   the merge, LAW 6).

## Hard prohibitions

- Never convert the refusal into a queue/wait — the contract is exactly-one
  holder, loser refused immediately (no backlog, no deferral).
- Never hold the lock across validation that can fail fast — validate first
  (`-32602`), acquire once, run; the re-check goes immediately before the
  acquire, not before validation.
- Never mock the lock or the socket in the RED test — drive the real
  `asyncio.Lock` (lock-step coroutines) and the real TestClient WS route.
- Never spawn sub-agents; never touch `.jcode/briefs/`, `LAWS.md`, root `AGENTS.md`.

## Report-back shape

- Old-vs-new lock-step output + live busy transcript (frames + close code).
- Files changed + `git diff --stat`; gate output; unmerged branch + worktree.
