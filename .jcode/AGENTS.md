# Jcode harness notes (this repo's `.jcode/` — machine + harness specific)

Root `AGENTS.md` is the project map (harness-neutral). This file is the
Jcode-harness half of the split: model, machine, and computer specifics that
other harnesses should replace with their own, not copy.

## Harness + model

- Harness: Jcode (`jcode` CLI/API). Contributor route for sub-agents:
  `muse-spark-1.3-contributor` on the Meta Model API (route-pinned, cheap,
  good at tight briefs). Pin the id verbatim; guessed ids fail loudly.
- Spawning: `swarm spawn label:"<role>"
  prompt:"<repo path, branch, exact task, no-write vs write>"` — OMIT `model:`
  so the worker inherits this session's proven coordinator route. Do NOT pass
  `model:"muse-spark-1.3-contributor"`: the router reads a bare id as
  a different-provider request (Anthropic) and refuses (11 refusals 2026-11-01). Workers in
  normal mode never spawn sub-agents; spawner owns the merge; writers get
  isolated git worktrees (`git worktree add /tmp/wt-<role> <branch>`),
  readers share the checkout; remove worktrees when done.
- Briefs live in `.jcode/briefs/` (git-ignored). One dated file per user
  message, verbatim quote + numbered decomposition (LAW 2).

## Machine specifics (this box — do not treat as repo truth)

- Linux x86_64, NVIDIA GPU present, Python 3.12 venv at `.venv/`.
- Gate: `python3 .jcode/tools/dev.py check` (pytest, ruff check+format,
  compileall, `node --check static/app.js` + fixture app.js,
  `test_harness.py`, `main.py --list-targets`).
- Live proof: keyed Muse via owner-only `.env` (`META_MUSE_API_KEY`, never
  committed); Docker Engine with Linux containers for `offline_scan.py`
  (3 fixtures) and `project_scan.py`; headless Firefox/Chrome for
  `ui_scan.py --offline` (LAW 11 matrix).
- `.jcode/tools/` holds this box's scripts (one-line header comment each);
  cross-project tools live in `~/.jcode/tools/`.

## Overnight runs

- Run dirs: `/home/sponge/.jcode/overnight/runs/<run_id>/` with
  `review-notes.md`, `task-cards/`, `validation/`, `review.html`,
  `manifest.json`. Coordinator stays visible; no hidden supervisor loop.
