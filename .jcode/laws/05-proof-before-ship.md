# LAW 5 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 5 — Proof before ship (definition of done)

- `python3 .jcode/tools/dev.py check` passes (lint, format, compile, unit
  tests, fixture checks, list-targets).
- New behavior has a test that fails without the fix and passes with it.
- Live paths proven for real at least once: Docker scans with cleanup,
  headless-browser scans where UI changed, intel transports against live
  sources where network behavior matters.
- Docs updated where behavior changed (`README.md`, `docs/`, `TODO.md`).
- Committed on the feature branch, merged `feature → develop → main`,
  both pushed, back on `develop`.

