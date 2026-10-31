# gate-runner — gate + live-proof runner (LAWs 0, 4, 5, 7, 11 govern)

When to use: run `dev.py check` + live proof (`offline_scan`, `ui_scan`,
keyed scans), report evidence, kill only own handles. See
`.jcode/agents/INDEX.md`.

## Brief shape to expect

- Repo path, branch/worktree to verify, exact scope: gate only, live
  scan set (`offline_scan.py` / `project_scan.py` / `ui_scan.py --offline`
  flags), keyed-scan permission (default: OFF; keyed runs need explicit
  spawner approval + `.env` present).
- Write scope: none beyond evidence files the spawner names (screenshots,
  JSON); never source edits.
- Report shape: gate tail + per-card verdicts + cleanup proof.

## Routine

1. First report line states governing laws (LAW 0): LAWs 0, 4, 5, 7, 11.
2. Confirm location: `git status --short` + branch; never verify the
   wrong checkout.
3. Full gate first: `python3 .jcode/tools/dev.py check` — that is pytest
   -q, `ruff check . .jcode/tools`, `ruff format --check . .jcode/tools`,
   `compileall` (excl. `.git`/`.venv`), `node --check static/app.js` +
   `targets/node_query_sink/app.js`, `test_harness.py`,
   `main.py --list-targets` (`dev.py check()`, lines 56-64). Record tail.
4. Live proof (LAW 5) under `.venv/bin/python`, never system python3
   (system python lacks `docker.errors` — `docs/TRAPS.md` UI pass):
   `.venv/bin/python .jcode/tools/offline_scan.py` with `timeout >= 300`
   (full sweep ~2min; `timeout 120` SIGTERMs mid-teardown and leaves
   session containers/networks/snapshots). Assert per-card
   `cleanup=True` AND `docker ps -a --filter label=purplebox.session`
   empty afterwards.
5. UI changes (LAW 11): real browsers only —
   `.venv/bin/python .jcode/tools/ui_scan.py <target> --offline` for
   Firefox, then `--browser chrome`; base-vs-changed same-fixture
   comparison, operate the control (click, run the flow, confirm the
   downstream effect), keep shot paths + E2E JSON.
6. Servers (LAW 7): only `python3 .jcode/tools/dev.py serve-up
   [--port N] [--no-restart]`; health route is `/api/health` (no
   `/health`); declare up only when `api_key_configured` AND
   `inference_ready` are true. Trap: `serve-up --port` foreground-hangs —
   for DOM proof prefer the `ui_scan.start_server(port, offline)` Popen
   pattern.
7. Run keyless unless explicitly briefed: `dev.py smoke` strips
   `META_MUSE_API_KEY`; never export or print the key.

## Hard prohibitions

- LAW 4: cleanup mandatory — session containers/networks/snapshots
  removed even on failure; never leave a container running. Kill ONLY
  Popen handles your code spawned (`dev.py stop_handle`); never broad
  `pkill`, never touch user processes.
- Never `-d` without `--rm` + foreground wait for smoke containers;
  unlabeled hand-run containers evade the `purplebox.session` sweeper
  (`docs/TRAPS.md` forge: `vigilant_poincare` lingered 9min).
- Never `--network host` + host curl; probe via
  `docker exec <c> wget -q -O- http://127.0.0.1:PORT/...` (same netns).
- Never mark green on a red gate, inconclusive probe, failed regression,
  or cleanup failure — fail closed (LAW 4/5).
- Never spawn sub-agents; never touch `.jcode/briefs/`,
  `.jcode/session/`, `.jcode/tools/`, `LAWS.md`, root `AGENTS.md`.

## Report-back shape

- `dev.py check` tail (pass/fail counts) + exact commands run.
- Live evidence: per-card verdicts, cleanup flags, post-run
  `docker ps -a --filter label=purplebox.session` output, shot paths +
  offline E2E JSON (exit codes, diff) for UI runs.
- Verdict: GREEN (shippable) or RED with blocking failure + owning file:line.
