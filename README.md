# Secure Mitigation System

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

A tool that finds a weak spot in code, fixes it, and proves the fix works. This page takes about 3 minutes to read.

## What it is

The tool runs a loop with two AI agents and a locked box.

1. A **red team** agent reads the code and finds a weak spot.
2. Red writes a small test (a "probe") that tries to reach that weak spot.
3. A **sandbox** runs the probe. The sandbox is a Docker container with no network.
   Exit 0 means the weak spot was reached. Exit 1 means it was blocked. Exit 2 means unclear.
4. A **blue team** agent writes a small patch to fix the weak spot.
5. Normal-input checks run, then the probe runs again on the patched code.
6. Only if the probe now fails (exit 1) and the normal checks still pass, the result is marked **verified**.

Containers and networks are removed when the run ends.

## Quick start

You need Python 3.12+, Docker, and a Meta Muse API key.

```bash
python -m venv .venv
.venv/bin/python scripts/dev/dev.py setup   # install dependencies
cp example.env .env                          # then put your key in META_MUSE_API_KEY
.venv/bin/python main.py --init-images       # build the sandbox images
.venv/bin/python main.py --serve             # dashboard at http://localhost:8000/web/
```

Other useful commands:

```bash
.venv/bin/python main.py --help              # all options
.venv/bin/python main.py --list-targets      # bundled practice targets
.venv/bin/python scripts/dev/dev.py check    # run the test gate
```

## Fast demo

```bash
.venv/bin/python demo_run.py
```

No arguments. It pulls the public practice app `BrenesRM/insecure-web` at commit `5d1b791` and runs the full loop.

One measured run:

- Found: SQL injection in `POST /login`.
- Probe exit 0 before the patch, exit 1 after the patch.
- Status: `verified`.
- Time: 4:16. Cost: $0.0070.
- The wrapper prints a labelled heartbeat every 5 seconds. The longest gap with no output was 6 seconds.

Be honest with yourself about this demo. The AI is not deterministic. In 4 runs on the same day, 2 were verified, 1 was inconclusive before the patch, and 1 was inconclusive after the patch.

The demo also has limits. The sandbox is offline and has no Flask. So the normal-input check is only a parse check (`ast.parse`) of `app/app.py`. The probe tests the query code directly with `sqlite3`, not over HTTP. The demo passes a `--contract` note that tells red these sandbox facts.

## Scan any repo (Universal Omni-Ingest)

```bash
.venv/bin/python main.py --ingest-repo https://github.com/OWNER/REPO --commit-hash SHA --allow-remote-inference
```

- The repo is cloned inside an offline Docker staging step, pinned to the commit you give.
- The tool guesses how to run the app (Node, PHP, Python, and so on). This is `detect_runtime` in `library/services/repo_intake.py`.
- If the guess is wrong, set it yourself with `--command "..."` (and `--test-command "..."` for the normal checks).
- Use `--ingest-dry-run` to see the plan without running a scan.

## Models: Meta Muse Spark

The tool uses Meta Muse models only. Defaults (from `library/core/config.py` and `example.env`):

- Red model: `muse-spark-1.3-contributor` (`META_MUSE_RED_MODEL`)
- Blue model: `muse-spark-1.3-contributor` (`META_MUSE_BLUE_MODEL`)
- Open-weight option: `meta-models/muse-spark-open-1026`
- Optional escalation: set `META_MUSE_BLUE_ESCALATION_MODEL` (for example `muse-wonder-1.0`). If blue fails, it gets exactly one retry with that model. Empty means off.

The `balanced` profile (`--profile balanced`) uses Spark for red and Spark for blue.

**How does Muse compare to Opus 5.5, Fable 5.1, or Luna 6?** We do not know. No head-to-head benchmark was run. We use Muse Spark because it is cheap and it worked on our tests: the demo above cost under one cent per verified run.

## Scale: big repos (AnyCam)

What exists today:

- Triage ranks files and scans them in order, most likely first.
- Red gathers evidence in parallel (`red_evidence_parallelism`, default 4, env `PURPLEBOX_RED_EVIDENCE_PARALLELISM`).

What does **not** exist: there is no early exit. The scan does not stop when it finds the first problem. On a big repo it keeps going.

Our one AnyCam run was stopped by hand at 16:06. It cost $0.37. The result was partial. Large repos are not a solved case yet.

## Limitations

- `verified` means one probe was blocked after the patch. It does not mean the code is safe.
- Results vary run to run. Re-run before you trust a result.
- The sandbox has no network. Apps that need outside services or missing packages may only get weak checks (like a parse check).
- Runtime detection can guess wrong. Use `--command` when it does.
- No early exit on big repos, so cost and time grow with repo size.
- No benchmark against other model families.
- A person must review every patch.

## More reading

- [`docs/DEMO.md`](docs/DEMO.md): how to record the demo.
- [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md): how the parts fit together.
- [`docs/TRAPS.md`](docs/TRAPS.md): things that looked right and were not.
- [`docs/index.md`](docs/index.md): map of all docs.

## Tests

```bash
.venv/bin/python scripts/dev/dev.py check
```

Last result: 1697+ passed, 3 skipped. Tests are mocked. They make no API calls.

## Acceptable Use, Warnings, and Disclaimer

Defensive work only: check input rules in code you own or may test, in throwaway sandboxes, with a person watching.

Do not use this on systems you may not test. Do not treat `verified` as proof of safety. Sandboxes can fail and models can be wrong. Do not strip safety controls to harm others. You carry the risk and must follow the law. When in doubt, stop.

Licensed under [PolyForm Noncommercial 1.0.0](LICENSE.md).
