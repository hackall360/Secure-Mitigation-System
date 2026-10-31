# LAW 7 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 7 — Single server + key check on start/restart

Before starting a server, probe the port first. The app's only health route
is `/api/health` (see `main.py`; there is no `/health` route). If a live
server already answers on `/api/health`:

1. Kill ONLY handles your own code spawned (PIDs you started, Popen handles
   you own). Never broad-`pkill`, never touch the user's processes — the same
   rule as LAW 4 cleanup and the Firefox terminate discipline.
2. Restart with `.env` sourced (the app never loads `.env` itself — zero
   dotenv references — so the key only lands if exported in the starting
   shell).
3. Verify via `/api/health` that `api_key_configured` is true and
   `inference_ready` is true before declaring the server up.

Root cause this encodes (2026-10-28): a stale keyless 14:05 process held
`:8000` while a fresh restart bounced off EADDRINUSE, so the dashboard showed
"No API key" with a valid `.env` on disk. See
`.jcode/briefs/2026-10-28-ui-gaps-green-crash.md`.
Tooling: `python3 .jcode/tools/dev.py serve-up [--port 8000] [--no-restart]`
implements exactly this (probe `/api/health` → terminate only the own
tracked `Popen` handle → start with `META_MUSE_API_KEY` from owner-only
`.env` → verify). Prefer it over hand-rolled `curl` + `kill`.

