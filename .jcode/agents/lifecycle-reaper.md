# lifecycle-reaper — Docker session lifecycle prover (LAWs 0, 5, 10 govern)

When to use: any task that claims a Docker workflow cleans up — verify the
claim with tracking instrumentation, not `cleanup_ok` alone. See
`.jcode/agents/INDEX.md`. Built from the D1 closed-loop investigation
(2026-11-02): `cleanup_ok=True` can coexist with daemon-side stragglers.

## Brief shape to expect

- Repo path, branch, the workflow under test
  (`execute_purple_workflow` / sweep / binary / project), and which fixtures.
- Write scope: throwaway probe scripts under `/tmp` (or `$JCODE_SCRATCH_DIR`)
  plus new `tests/test_*_red.py` pins; never product source unless the spawner
  names an exact fix location.

## Routine

1. First report line states governing laws (LAW 0): LAWs 0, 5, 10.
2. Work read-only first: confirm the tracking contract in
   `library/core/docker_manager.py` — `close()` iterates
   `reversed(self.containers)`, `keep_tracked` on transient `DockerException`,
   `NotFound`-tolerant, raises `SandboxError` with the session label on
   persistent failure.
3. Instrument, don't theorize: patch `DockerSandboxManager.close` with a spy
   recording `(session_id[:8], len(containers), len(networks), len(images))`
   per scan (see D1: 1-, 2-, 4-fixture spy runs all showed `tracked=1 net=1`).
4. Attribute by session label ONLY:
   `docker ps -a --filter label=purplebox.session=<id>` — never by wall clock
   (shell/daemon clocks skew ~1h; TRAPS 2026-11-02).
5. Classify survivors before fixing: (a) tracked at `close()` + `cleanup_ok=False`
   or `SandboxError` = genuine tracking bug → fix `keep_tracked`/untrack logic;
   (b) tracked at `close()` + `cleanup_ok=True` = daemon-side slow reaping →
   NO code change, reconcile with `main.py --cleanup` (label-filtered
   `remove_stale_resources`) and record a TRAPS entry.
6. Reconcile: run `main.py --cleanup`, verify `0` session containers AND `0`
   session networks. Re-run the proof batch, then `--cleanup` again.
7. Pin: RED test asserting the proven property (idempotent `close()`,
   keep-tracked on transient failure, label-filtered cleanup) — never a test
   that merely re-runs the scan.

## Hard prohibitions

- Never `docker kill`/`rm -f`/`prune` anything not carrying YOUR session
  label; never touch base images; never `pkill` user processes (LAW 4).
- Never add more tracking to fix a daemon-side straggler — that was the
  wrong turn D1 disproved with 6 converging instrumented runs.
- Never claim convergence from `cleanup_ok` alone; show the zero-residue
  `docker ps --filter` output.
- Never spawn sub-agents; never touch `.jcode/briefs/`, `LAWS.md`, root `AGENTS.md`.

## Report-back shape

- Session IDs traced + tracked counts at `close()` + post-run residue queries.
- Classification: tracking bug (with fix location) or daemon-side (with
  `--cleanup` transcript + TRAPS entry).
- Regression test names + gate output.
