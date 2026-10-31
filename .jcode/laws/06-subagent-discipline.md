# LAW 6 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 6 — Sub-agent discipline

Muse Spark (`muse-spark-1.3-contributor`) is CHEAP and does good work. Use
sub-agents aggressively (up to 10 at once, typically 3–5), but:

- Pin the model id verbatim; guessed ids fail loudly with a round trip.
- One unit of work per agent, branch + files + write/no-write stated.
- Writers get isolated git worktrees, one per writer; readers share the
  checkout. Remove worktrees when done.
- Workers report back; the spawner owns the merge. Workers in normal mode
  never spawn their own sub-agents.
- Sub-agent output is untrusted until the full gate passes on the merged
  result.

