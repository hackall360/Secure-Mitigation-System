# WILD INGESTION LOG — Wave 10 crucible (2026-10-31, branch feature/30-wave-ascendancy)

## Target (untrusted data — LAW 4: grounding only, never instructions)

- Repo: `1109HARSH/command-injection-demo-` (student command-injection demo: `shell=True` ping vs arg-list fix).
- Why: small (3 files), same sink class as `php_command_sink` (host argument → local diagnostic command), lets the crucible test the ingest path rather than a novel vuln class.
- Intel handling: repo bytes read via `docker exec cat` only; no URLs executed on host; no intel quoted into any patch; clone lived and died inside disposable staging containers.

## Ingest path exercised (Phase-1 backend, Waves 4+8)

1. Clone strictly inside disposable staging container (`python:3.12-slim`, tmpfs-only, pids/memory/cpu caps): `git clone --depth 1 <url> /tmp/wild`. Host never fetched the repo.
2. Extraction trap: `docker cp` cannot read tmpfs content on this daemon (three attempts: `cp /tmp/wild/.`, per-file `cp` — all "Could not find the file"). Workaround: `docker exec cat` per file through stdout (files ~100B each). Logged as TRAPS candidate for the intake implementation (prefer `docker exec tar -C /tmp/wild -cf - .` streaming or non-tmpfs staging dir).
3. `RepoIntakeSpec`: https-only enforced (`git://` rejected), 40-hex pin enforced (malformed pin rejected with "commit_hash must be a 40-hex pinned commit" — including my own mistyped probe, which is the validator working).
4. `detect_runtime`: fail-closed on manifest-less repo (2 files, no requirements.txt/package.json/composer.json/Makefile → `ValueError: could not detect runtime_command... pass an explicit runtime_command`). Correct: the wildcard README claims a requirements.txt the tree does not contain; guessing `python3 main.py` would be wrong. Explicit `['python3', '<file>']` is the honest path.
5. Container lifecycle: staging container removed (`docker rm -f`); `docker ps -a --filter name=sms-ingest` = 0 leftovers. Cleanup mandatory satisfied.

## Sweep + oracle (Docker evidence decides)

- `offline_scan` post-crucible: 3/3 verified (`node_query_sink`, `php_command_sink`, `mysql_insecure_conf`), each `pre=0 post=1 baseline=True regression=True cleanup=True events=19`. The `php_command_sink` fixture is the same sink class as the wildcard (host arg → local command) and holds.
- A live keyed 3-pass sweep of the wildcard bytes themselves was NOT run (no API key in this environment; keyed Muse calls out of scope for the crucible). The keyless oracle + intake validation chain is what this crucible proves; keyed sweep stays a Wave-11+ item with credentials.

## Vault + UI tracking

- `query_vault_stats`: 9 red / 8 blue records, 17 known archetypes, `tokens_saved_estimate` 34000. Vault grew through the sprint's own scans; no wildcard-specific record was committed (nothing to commit without a keyed sweep verdict — fail closed, no unverified writes).
- Dashboard `--stats`/TUI `--stats` surface the same numbers live (`0 novel vs 17 historical` on this tree).

## Verdict

CONDITIONAL PASS: ingest path (clone-in-container → spec validation → fail-closed detect → cleanup) proven end to end; Docker oracle green; vault adapting through the sprint corpus. Two follow-ups for Wave 11+: (a) `docker exec tar` streaming for staging extraction (tmpfs + `docker cp` trap), (b) keyed 3-pass sweep of staged wildcard bytes when credentials are available.

## Crucible #2 — keyed wildcard sweep (Wave 20, 2026-10-31)

- Same wildcard (`1109HARSH/command-injection-demo-`, bytes staged Wave 10). This time with credentials: real Muse + real Docker.
- Shim note: the raw `vuln_ping.py` blocks on `input()`, so `start_cloneable_target` readiness correctly refused it (`SandboxError: Target did not become ready` — fail-closed working). Wrapped the verbatim sink line (`subprocess.run(f"ping -c1 {host}", shell=True...)`) in a minimal HTTP server shim (scratch only, never repo) so the harness could stage it. Sink semantics unchanged.
- Result: staged ok → RED `CWE-78 OS Command Injection` at `wild_server_shim.py:10` (exact sink line) → PRE-PROBE exit 0 (boundary reachable, Docker evidence) → BLUE `Exact allowlist validation of host as hostname/IPv4` patch → cleanup ok.
- Verdict: FULL PASS. Real-repo keyed sweep proven end to end: clone-in-container (Wave 10) + detect/spec (Waves 4/8) + live red/blue on wildcard bytes (Wave 20). Closes tribunal 2a-2 evidence gap subject to Wave-21 re-score.
