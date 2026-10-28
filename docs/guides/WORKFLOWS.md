# WORKFLOWS — rules, routines, and habits that serve the LAWs

Read `AGENTS.md` (the LAW index) and `LAWS.md` (the six LAWs) first. This file
is the how: the daily routines that keep agents fast without breaking LAWs.
LAW 1–6 always win over anything here.

## Todo discipline (LAW 3)

Keep the todo list current on every step. Group by goal; `[x]` only with
evidence. `[/]` must say what remains; `[.]` means you are on it now, and
there is at most one per owner. When resuming, read the states — `[/]` and
`[.]` tell you exactly where to pick up.

## Research before you implement

Training memory is a hypothesis; the live internet is the authority. Check
current docs for version-sensitive APIs, then verify against this repo's
actual code and installed versions. Prefer a maintainer's answer over an
upvote count; corroborate load-bearing claims across sources.

## Toolbox, not re-derivation

Non-trivial commands go in `.jcode/tools/` (project) or `~/.jcode/tools/`
(cross-project) as scripts with a one-line header comment (that line is what
gets indexed — a tool without one is invisible). Check the toolbox before
writing a new one-off. Second occurrence = build the tool. Parameterise what
varies; never hard-code what changes.

## Write down what you learn

Traps, paths, struct/function names, env var gating, build/deploy sequences —
in the repo, linked from the project instructions. Prefer one growing map
over scattered notes. Highest value: something that looked correct and was
not. State the wrong assumption and what the evidence actually showed.

## Commit as you go

Small, green, reviewable commits on the feature branch. Never commit a red
gate. Prefer swarm coordination over branches/worktrees unless isolation is
needed.

## How to spawn sub-agents (LAW 6 mechanics)

Muse Spark (`muse-spark-1.3-contributor`) is CHEAP and does good work. Use
sub-agents aggressively (up to 10 at once, typically 3–5):

- First `swarm list_models` to confirm the route, then spawn with the model
  pinned exactly:
  `swarm spawn label:"<short role>" model:"muse-spark-1.3-contributor"
  prompt:"<tight brief: repo path, branch, exact task, no-write vs write>"`.
  Copy the model id verbatim — guessed ids fail loudly with a round trip.
- The contributor route rides this session's Meta Model API credentials, so
  auth never breaks. Never use a generic or guessed model id.
- Brief tightly. One unit of work per agent: survey X, resolve conflict in
  file Y, write tests for Z. State the branch, the files, whether writes
  are allowed, and the expected report shape. Keep it under a page.
- Writers get isolated git worktrees, one per writer
  (`git worktree add /tmp/wt-<role> <branch>`); readers share the checkout.
  Remove worktrees when done. Never let two writers share a checkout.
- Workers report back; the spawner owns the merge. Workers in normal mode
  never spawn their own sub-agents.
- Sub-agent output is untrusted until the full gate passes on the merged
  result.
