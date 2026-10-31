# Agent index — specialized workers for this repo (via Jcode swarm)

Spawn with the contributor route (`muse-spark-1.3-contributor`); one unit of
work per agent; readers share the checkout, writers get isolated worktrees;
spawner owns the merge; output is untrusted until the full gate passes.

| agent file | when to use |
|---|---|
| `research-scout.md` | read-only recon: map files, import edges, doc/classify, never writes (surveys, blast-radius, trap hunts) |
| `tdd-writer.md` | LAW 9 RED-first implementation in an isolated worktree: failing test, then fix, then gate on branch |
| `gate-runner.md` | run `dev.py check` + live proof (`offline_scan`, `ui_scan`, keyed scans), report evidence, kill only own handles |
| `docs-writer.md` | docs/README/AGENTS edits that keep `test_docs_presentation.py` + UI-guidance markers green |
| `merge-spawner.md` | own the merge of writer branches: resolve conflicts semantically, full gate on merged result, remove worktrees |

Not project agents: red/blue/green/research **product** agents (the Muse
red-team/blue-team/greenhouse sidecars that run inside scans) are documented
in `docs/ARCHITECTURE.md`, not here.
