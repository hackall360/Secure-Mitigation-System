# Feature tags + per-module semver (post-refactor re-implementation)

Port of the Oct-28 `feature/work-tags` change set onto the post-refactor
tree (`library/` rename + `docs/HOW_IT_WORKS.md` + plain README). The old
branch is superseded; this doc replaces `TAGS_NOTES.md`.

## PART A — invisible feature tagging

- `library/tags.py` (canonical): `FEATURE_TAGS` maps 127 tag-ids ->
  `{surfaces, backend, ui, cli, tui}`. Surfaces: cli/web/tui/api.
  `check_registry()` walks the registry, asserts each tag has a live
  binding on its claimed surface(s), reports covered/uncovered.
  `WEB_DELEGATED_NEEDLES` records the verified JS wirings for controls
  reached by delegation (mode buttons via `button.dataset.mode`, chips via
  `chip(`, timeline via `getElementById('scan-timeline')` in panels.js/graph.js,
  filters via `.filter` loop).
- `static/index.html`: elements carry `data-feature` audit hooks
  (space-separated where one DOM id serves several tags). Attributes only —
  no markup, style, or script changes. `app.css`/all `static/*.js` contain
  zero `data-feature` references (test-pinned). New `demo-*` controls added
  by later waves are cli-only tags (no hook) unless the registry gives them
  a ui id — the checker enforces the DOM subset.
- `dev.py tags`: `python3 .jcode/tools/dev.py tags` prints
  `127/127 covered` or lists UNCOVERED lines and fails.
- `tests/test_feature_tags.py` (LAW 9 red-first): bogus-binding fixture
  fails pre-registration; 127/127 live post-implementation; versions
  pinned; DOM invisibility pinned.
- Honest-recorded gap (not silently dropped): the old `ws-demo` 4
  first-frame key claim has no anchor in the current `main.py`; the
  demo entries are backended to `run_demo_build`/`ai_demo_runner`
  instead. `serve-dashboard` keeps the corrected cli+api registration
  (the dashboard IS the served page, not a control).

## PART B — per-module semver (landed constants; law text is a proposal)

Stamped `__version__ = "0.1.0"` on 11 leaves
(`library.shared.sms_*`, `library.intel.research`,
`library.services.demo_gen`, `library.workflows.{workflow,project_workflow}`,
`library.tags`); `library.core.version` carries `APP_VERSION = "0.13.1"` +
`__version__ = "0.13.1"`. All mirrored in `library.tags.MODULE_VERSIONS`
with importable dotted keys (test-pinned equality).

Bump rule (mirrors LAW 12): capability -> module minor (`0.1.0` ->
`0.2.0`); fix/polish only -> module patch (`0.1.0` -> `0.1.1`).
Top-level app version stays LAW 12. This change set ships modules at
`0.1.0` (new audit tooling, no user-visible capability).

## LAW text proposal (do NOT edit LAWS.md — proposal only)

> ### LAW 13 — Per-module semver (leaves version independently)
>
> Every modularized leaf carries its own `__version__` (`0.x.y`), mirrored
> in one map (`library.tags.MODULE_VERSIONS`). The bump rule mirrors LAW 12
> at module scope: a new capability in a module moves its minor; a fix,
> polish, or hardening-only change moves its patch. Exactly one bump per
> shipped change set per touched module. The top-level app version stays
> under LAW 12 and moves only on user-visible change — a module bump alone
> never moves it. The checker (`dev.py tags` + `test_feature_tags.py`)
> pins map == leaf constants; drift is a gate failure.

## Traps inherited from the original (all re-verified this pass)

- Delegation needles must be exact verified selectors, not loose
  substrings — never loosen the check to get green (LAW 9B).
- A tag with a fake surface is worse than a gap recorded as missing
  (serve-dashboard lesson).
- Attribute-only DOM rule: any `data-feature` string in css/js fails the
  gate; hooks with no registry entry fail the gate.
