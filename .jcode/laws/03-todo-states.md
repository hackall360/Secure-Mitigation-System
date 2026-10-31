# LAW 3 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 3 — TODO states: not done, partial, in-progress, done

Every brief decomposes into `TODO.md` items with exactly these states:

- `[ ]` not done — accepted, work has not started.
- `[/]` partial — attempted or landed incomplete; the item text MUST say
  what remains.
- `[.]` in-progress — actively being worked right now. At most one `[.]`
  per owner; flip it back to `[ ]`, `[/]`, or `[x]` when you stop.
- `[x]` done — landed with proof: the item names its files and its proof
  (test names, gate output, live evidence). No proof, no `[x]`.

Rules: every item names its files and its proof. Partial items never
masquerade as done. When resuming, read the states — `[/]` and `[.]` tell
you and every other agent exactly where to pick up.

