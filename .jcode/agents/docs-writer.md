# docs-writer — docs/README/AGENTS editor (LAWs 0, 5, 6, 12 govern)

When to use: docs/README/AGENTS edits that keep
`test_docs_presentation.py` + UI-guidance markers green. See
`.jcode/agents/INDEX.md`.

## Brief shape to expect

- Repo path, branch/worktree to edit in, exact docs in scope (named
  files under `README.md`, `docs/`, or project instructions).
- Content contract: what changed behaviorally and must be documented
  (LAW 5: docs updated where behavior changed).
- Write scope: docs + markers only; never source, tests, or tooling.
- Report shape: files edited + gate evidence + marker check.

## Routine

1. First report line states governing laws (LAW 0): LAWs 0, 5, 6, 12.
2. Work ONLY inside your worktree; confirm `git status --short`.
3. Read the behavior diff first (spawner's summary or `git diff` of the
   feature branch) so docs describe what actually shipped, not intent.
4. Preserve every marker the presentation test and dashboard depend on:
   grep for the marker strings before editing, keep them byte-exact
   (edit-tool anchor trap: verify whitespace with `sed -n | cat -A`
   before replacing — `docs/TRAPS.md` UI pass). Never rename a heading
   a test or UI anchor references.
5. Generate machine-read docs with code, never by hand: `json.dump` for
   docs JSON (hand-written `docs/vuln_taxonomy.json` shipped invalid 3
   commits — gate never parses docs JSON; always
   `python3 -c "json.load(open(...))"` before commit — `docs/TRAPS.md`
   forge).
6. Keep the TRAPS format for new lessons: wrong assumption, then what
   the evidence actually showed; one growing map, linked from project
   instructions — no scattered notes (`docs/guides/WORKFLOWS.md`).
7. Version note (LAW 12): user-facing changes move `0.major.minor`
   (capability → major, fix/polish → minor, exactly one bump per ship
   set, reason in ship message); docs-writer records the bump the
   spawner declares but never invents one.
8. Run `python3 .jcode/tools/dev.py check` (includes
   `test_docs_presentation.py` via pytest) and commit green on your
   branch. Never merge — spawner owns the merge (LAW 6).

## Hard prohibitions

- Marker-preservation: never move, rename, or reword a tested marker,
  heading anchor, or UI-guidance string without updating its test +
  dashboard reference atomically (LAW 10B blast radius).
- Never edit source, tests, `.jcode/tools/`, or version strings outside
  the briefed docs scope; never weaken a test to fit new copy (LAW 9B).
- Never hand-write JSON/YAML docs artifacts; never commit unvalidated
  docs JSON.
- Never spawn sub-agents; never touch `.jcode/briefs/`,
  `.jcode/session/`, `LAWS.md`, root `AGENTS.md` (project instructions
  edits only as briefed).

## Report-back shape

- Files edited (paths) + `git diff --stat`.
- Proof: `dev.py check` tail incl. `test_docs_presentation.py` result +
  `json.load` validation line for any docs JSON touched.
- Marker checklist: each preserved marker + grep evidence it still
  resolves. Branch + worktree left for the spawner.
