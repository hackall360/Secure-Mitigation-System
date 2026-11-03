# CLI Surface Notes — LIVE tester (2026-11-02, worktree /tmp/wt-surface1)

Scope: NO commits. Never touched live :8795. Keyless only; Docker present
(`--docker-status` = ready) but NO real keyless fixture scan is possible —
fixture path calls `require_api_key` unconditionally (see Findings F1).
All scan-path evidence below is mocked (monkeypatch `execute_purple_workflow`
/ `execute_cve_scan` / ops fns, same pattern as `tests/test_cli_parity.py`).
Venv: repo `.venv` (worktree has no `.venv`).
`--help` lists all 10 new parity flags (each matched 2x: flag def + help text):
`--show-cycles`, `--show-intel`, `--vault-list`, `--vault-replay`,
`--ops-status`, `--cleanup-dry-run`, `--showcase-status`, `--ops-log`,
`--ingest-dry-run`, `--cve-limit`, plus `--cve-reach-only` (2x).

## Per-flag PASS/FAIL

- PASS `--help` — all 10 parity flags + `--cve-reach-only` listed; Wave 2/5/8
  capability epilog present. Evidence: `main.py --help | grep -c -F -- <flag>` = 2 for each.
- PASS `--version` — `main.py 0.14.0`, exit 0.
- PASS `--list-targets` — 5 fixtures listed, exit 0.
- PASS `--show-cycles` + `--show-intel` (mocked fixture scan) — exit 0, fact
  table renders. Evidence: `PY -c` with `fake execute_purple_workflow` +
  `sys.argv=[..., "--scan","node_query_sink","--show-cycles","--show-intel]` → exit 0.
- PASS `--vault-list` (tmp vault via `PURPLEBOX_VAULT_DIR`) — `red: 1 records`, exit 0.
- PASS `--vault-replay red:<32-hex-id>` (tmp vault) — prints `Record <id>: status/fingerprint/created`, exit 0.
  Bad-id refusals exit 1, never traceback: `badspec` → `expected NAMESPACE:ID`;
  `red:xyz` → `Malformed vault record id; refusing to replay`.
- PASS `--ops-status` (mocked daemon) — table + `--format json` both exit 0, JSON parses.
- PASS `--cleanup-dry-run` (mocked daemon) — `Cleanup dry-run (removes nothing)` + JSON `{"dry_run": true, ...}`, exit 0.
  Live (unmocked, read-only): exit 0, `0 containers, 0 networks, 0 snapshots`.
  Live `--ops-status`: exit 0, Docker ready, `3/4 sections present`.
- PASS `--showcase-status` — table + `--format json` (parses), exit 0, nothing started.
- WEAK-PASS `--ops-log` — exit 0 always, but prints NOTHING: worktree `logs/` tree
  exists (`logs/ logs/ metrics/ traces/`) yet contains zero `*.jsonl` (only
  `metrics/_summary.json`). `--ops-log`, `--ops-log 3`, `--ops-log 0` all exit 0
  with empty stdout. No guidance on empty tree (contrast: missing-tree path prints
  `no observability logs found...` to stderr). See F3.
- PASS `--ingest-dry-run` good — 40-hex commit → `spec valid, nothing cloned` + staging plan, exit 0.
  Evidence: `--ingest-repo https://github.com/example/repo.git --commit-hash aaaa...(40) --ingest-dry-run`.
- PASS `--ingest-dry-run` bad — `xyz` commit → `ingest dry-run: invalid spec (commit_hash must be a 40-hex pinned commit)`, exit 1 (documented).
  `--ingest-dry-run` without `--ingest-repo` → argparse exit 2 (correct: dry-run is a modifier).
- PASS `--cve-limit 1` (mocked CVE, 2 vulns) — exactly 1 `[CVE` line, exit 0.
- PASS `--cve-reach-only` (mocked CVE) — zero `[CVE` lines, `[TOP` topping lines only, exit 0.
- PASS `--health` — `Status ok`, exit 0. `--health --format json` parses
  (`status=ok`, `version=0.14.0`, `api_key_configured=false`), exit 0.
- PASS `--format json` purity (mocked fixture scan) — `json.loads(stdout)` OK;
  `[SYSTEM]` chatter on stderr, stdout machine-pure.
- PASS bad-flag combos → exit 2, never traceback: `--show-intel` (no `--scan`),
  `--sweep-passes 5`, `--cve-limit 0`, `--demo-size small` (no `--ai-demo`),
  `--bogus-flag-xyz`, `--ops-log -1` (`--ops-log must be >= 0`), all exit 2.
- SKIP real keyless fixture scan — IMPOSSIBLE without key: `--scan node_query_sink`
  without `META_MUSE_API_KEY` → status error `META_MUSE_API_KEY is required for
  scans`, exit 1 (JSON mode still emits redacted error JSON, exit 1). `--offline-cve`
  does NOT apply to fixture path (CVE-only flag); Docker is ready but key gate fires
  first. Documented as skipped-with-reason per brief.

## FINDINGS

- F1 (by design, blocks brief's "real keyless scan"): fixture `--scan` has no keyless/
  offline path. `execute_purple_workflow` → `require_api_key` unconditionally;
  `--offline-cve` only skips OSV lookup on the `--cve-scan` project path. So "at least
  one REAL keyless fixture scan" cannot run without a key even with Docker ready.
  Either the brief's expectation or the key gate needs revisiting.
- F2 (BUG — CVE `--format json` broken): mocked `--project ... --cve-scan --offline-cve
  --format json` prints NOTHING to stdout (all lines, incl. `[CVE`/`[TOP`/`[SYSTEM] Report`,
  go to stderr) and no JSON. Fixture path handles `--format json` correctly
  (`print(json.dumps(user_report...))` on stdout); CVE branch has no JSON branch —
  `_out()` routes to stderr in json mode and nothing ever prints the redacted report.
  Silent empty-stdout success (exit 0). Repro: mock `execute_cve_scan`, add `--format json`.
- F3 (confusing): `--ops-log` on empty-but-present `logs/` tree exits 0 with zero output
  and zero guidance. Missing-tree path helpfully says `no observability logs found
  under logs/ (run a scan first)`. Empty tree should say the same.
- F4 (minor, redaction note): `--vault-replay` prints `fingerprint: fp-test-123...`
  (12-char prefix + `...`). Stated redacted-summary contract holds (opaque id + prefix +
  status + mtime; payload `redacted-test` never printed) — flagging only because a naive
  reader may mistake the fingerprint prefix for payload leakage. Not a leak.
- F5 (test-env trap, documented): `ProjectSpec` rejects symlinked ancestors —
  `tempfile.mkdtemp()` under `$JCODE_SCRATCH_DIR` (`/home/sponge/.jcode/scratch` →
  symlink) fails validation. Use a non-symlinked dir (e.g. `/tmp/wt-test2/`) for
  mocked `--project` runs. No product bug.
