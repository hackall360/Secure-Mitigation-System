# LAW 1 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 1 — Branch flow: feature → develop → main, never direct

NEVER work directly in `main` or `develop`. EVER. All work happens in
feature branches: `feature/<short-description>`.

```bash
git checkout -b feature/my-work   # from develop
# ... edit, test, commit ...
```

Ship flow, in this order, no shortcuts:

1. `git checkout develop && git merge --no-ff feature/my-work`
2. `git push origin develop`
3. `git checkout main && git merge --no-ff develop`
4. `git push origin main`
5. `git checkout develop` (always end here — `develop` is home)

`main` is the release line. `develop` is the integration line. Feature
branches are where work happens. A direct commit to `main` or `develop` is a
process failure, full stop. Tooling enforces this with a pre-tool hook; do
not work around it.

The words "Ship it" invoke this LAW as a standing command. When the user
says "ship it" (or "stage, commit, merge into develop, push develop, merge
into main, push main, go back to develop"), execute this exact sequence
without asking for clarification:

1. `git add -A` (or otherwise stage the complete feature-branch work)
2. `git commit` with a descriptive message
3. `git checkout develop && git merge --no-ff feature/<name>`
4. `git push origin develop`
5. `git checkout main && git merge --no-ff develop`
6. `git push origin main`
7. `git checkout develop` — always end here, report the branch

Narrower requests stop early: "merge to develop" stops at step 4, "merge to
main" assumes work already on develop. "Ship it" means the full run:
feature → develop → pushed → main → pushed → back on develop. The full
gate (`dev.py check`) must be green before step 2; never ship a red gate.

