# TUI Surface Notes (headless, faked backends — no curses, no Docker/Muse)

Driver: `_surface_driver.py` (deleted after run; pattern from
`tests/test_ingest_cli_tui_red.py` + `tests/test_tui_dispatch.py` —
patch attrs on canonical source modules, `asyncio.run(tui._dispatch_core)`).
Result: **87/95 PASS**. 4 of 8 FAILs were driver-shape artifacts (corrected
below); 4 are real findings (2 critical).

## Per-mode (`_dispatch_core`, faked backends) — ALL PASS

| mode | result |
|---|---|
| fixture | PASS — `fixture <key>` summary |
| sweep | PASS — `max_passes=3` forwarded to `execute_sweep_scan` |
| mcp | PASS — language inferred `x.py`→python, no source leak in summary |
| binary | PASS — path/bytes not in summary |
| project | PASS |
| ingest | PASS — reaches `_ingest_repo_to_project` + project workflow, never fixture loop |
| demo | PASS — `demo: completed: demo done`; `intel_offline` kwarg always passed |
| cve | PASS — `include_osv`/`fast_lane`/`include_deep_assessment` forwarded from state flags |
| vault browse | PASS — empty ref → `vault: red(2)` namespace counts only |
| vault replay | PASS — `red:abc123` → `vault replay: replayed: red:abc123` (status/message only) |
| ops | PASS — `ops: docker ok leftovers 1c/0n/0i knobs t=60 showcase tts=present` |

Vault edge: bare `red` (no colon) → browse, no raise (correct). `red:`
(colon, empty id) → `ValueError("Vault replay needs NAMESPACE:ID...")` (correct,
fail-closed). Backend exceptions propagate unwrapped (`RuntimeError`, never
traceback text) — thread layer maps to type-name-only error state. Invalid
modes `bogus`/`FIXTURE`/`sweep ` → `ValueError`. Empty-string mode falls back
to fixture via `_state_mode` default (design choice, not a bug).

## Per-key (`parse_key` + `apply_action`) — ALL PASS at parse/state layer

Every `FOOTER_HELP` binding parses correctly (lower+upper): `1-4`→select,
`m/b/p/i/g/v/c/y/o`→modes, `+/-`→depth, `s`→start, `x`/ESC→stop, `f`→filter,
`h`→help, `q`→quit, Enter/arrows/resize codes. `z`/`''`/`'ab'`→unknown.
`apply_action` sets all 9 modes (incl. `mode:vault` via Y, `mode:ops` via O);
`mode:bogus` ignored; depth clamps 1–4.

## FINDING 1 (critical, dead keys): `_curses_main` never routes mode/depth actions

`parse_key` returns `mode:*` / `depth:*`, but `_curses_main` (tui.py ~1330-1361)
has branches only for quit/stop/select/filter/help/scroll/resize/start —
**no `mode:` or `depth:` branch**. Pressing `m b p i g v c y o + -`
interactively parses then falls through every `if` silently. `apply_action`
handles them, the loop just never calls it for those. So vault/ops keys Y/O
(and every other mode key, and depth) are **reachable in plain/test layers,
dead in the live curses UI**. Fix: add `if action.startswith("mode:") or
action.startswith("depth:"): apply_action(state, action)` (guard on running
as with select).

## FINDING 2 (critical-ish, render): footer truncated at 80x24 hides new keys

`FOOTER_HELP` is 172 chars. `render_panes` slices it to width, so at 80 cols
the footer shows `...c cve  y` — everything after is cut: `vault o ops +/-
depth Enter/s start x/Esc stop f filter h help arrows scroll q quit`. The new
vault/ops key hints (and start/stop/filter/help hints) are invisible at the
canonical 80x24 size. At 120 cols it still cuts mid-`Enter/s start`. Fix:
two-line footer or shorten (single-letter groups), keep `y vault o ops` in
the first 80.

## Render panes — otherwise PASS

80x24 and 120x40: exact row counts, all lines exact width, non-empty
(≥h-2), `mode:fixture` chip present, help overlay shows HELP lines,
scroll offset + empty-events render clean geometry.

## `_summarize_result` — PASS with correct shapes

bool/int/dict-status/vault-list/ops-bundle all correct. Wave2 receipt/guards/
topping/mutations surface via `describe_result` with real shapes
(`verdict_receipt` dict, `cycles[].receipt`, `guard_rationales`,
`fast_lane_top`, `mutations`). NOTE: the dict branch surfaces ONLY
`status`/`message` — a dict outcome carrying `cycles`/`intel_provenance`
keys drops them silently (object attrs go through the richer path, so live
`CveScanReport` is unaffected).

## CLI parity gaps (main.py vs TUI)

1. **No cve-limit equivalent**: `main.py --cve-limit` (1–1000) exists; TUI
   cve path never passes `max_osv_details` (backend default 25). No
   `--project-*` flag exposes it either.
2. **No include_nvd knob**: CLI passes `include_nvd=True` in the cve path;
   TUI leaves backend default False.
3. Vault/ops reachable in `run_plain --mode` (choices=MODE_ORDER) but there
   are no `--vault-ref`/`--ops-*` flags — vault replay piggybacks on
   `--ingest-repo`/`--commit-hash` fields, undiscoverable from `--help`.
4. Demo: CLI has cycles/red/blue-agents/research/profile knobs; TUI demo
   passes only theme/vulns/intel_offline.
