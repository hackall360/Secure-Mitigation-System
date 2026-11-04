# Recording the Demo

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

This page shows how to record a short, honest demo. Show real output only. Do not cut out failures if they happen.

## Before you record

```bash
cp example.env .env                          # put your key in META_MUSE_API_KEY
.venv/bin/python main.py --init-images       # build sandbox images
.venv/bin/python main.py --docker-status     # check Docker is ready
```

## Part 1: PHP fixture in the dashboard

1. Start the dashboard: `.venv/bin/python main.py --serve`
2. Open `http://localhost:8000/web/`.
3. Pick the bundled PHP target `php_command_sink` (see `targets/php_command_sink/`) and start a scan.
4. Narrate each step: red finds the weak spot, the probe runs (exit 0), blue patches, the probe re-runs (exit 1), status `verified`.

Measured: verified, exit 0 then 1, in 5:52.

## Part 2: real repo with `demo_run.py`

```bash
.venv/bin/python demo_run.py
```

It ingests `BrenesRM/insecure-web` at `5d1b791`.

Measured run: SQL injection in `POST /login`, exit 0 before patch, exit 1 after, `verified`, 4:16, $0.0070.

Lines that start with `[DEMO  ]` are a heartbeat from the wrapper every 5 seconds. Say so on camera. They are not system output.

Say these limits out loud:

- It is not deterministic. In 4 runs, 2 verified, 1 inconclusive before the patch, 1 inconclusive after.
- The sandbox is offline with no Flask. The normal check is an `ast.parse` of `app/app.py`. The probe calls the query code directly with `sqlite3`.
- The demo passes a `--contract` note that tells red these sandbox facts.

If a take ends inconclusive, either show it as is or re-run. Do not edit the result.

## Postscript: AnyCam (large repo)

Say this plainly: we tried the large AnyCam repo. Triage orders files and red works in parallel (default 4). There is no early exit when a finding appears. We stopped the run by hand at 16:06. It cost $0.37 and the result was partial.
