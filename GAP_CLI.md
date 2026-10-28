# CLI → Dashboard Gap Audit

Date: 2026-10-28. Auditor: read-only agent session.
Scope: every CLI flag/option in `sms_cli.py`, `main.py` argparse, `tui.py`
vs every dashboard control in `static/index.html` + `static/app.js`.
Rule: a gap = CLI capability with **zero** UI equivalent. Each item carries
file:line evidence on **both** sides (CLI definition + nearest UI neighbor
proving the absence was checked, not assumed).

**Gap count: 13** (10 full, 3 qualified/partial). No source files were
touched; this file is the only write.

## Compliance rerun (same day, commit after 541e46a)

Governing laws for this rerun: LAWs 0, 8, 10, 11 per tasking. Note: the
in-repo `LAWS.md` defines LAWs 1–6 only; 0/8/10/11 are task-overlay
references (surface wiring, blast radius, audit-only N/A), applied as stated.

1. **Re-verification: all 13 gaps still hold.** `git diff 541e46a HEAD`
   over `main.py`, `sms_cli.py`, `tui.py`, `static/app.js`,
   `static/index.html` is empty — no other track touched these files, so no
   gap was closed. Spot re-checks against current line numbers:
   argparse block `main.py:899-1048` intact (`--init-images` `:901`,
   `--rebuild-images` `:904`, `--cleanup` `:909-912`, `--tui` `:915-919`,
   `--port` `:937`, `--cve-scan` `:979-983`, `--deep-assessment` `:984-988`,
   `--offline-cve` `:989-993`, `--config` `:1014-1020`,
   `--show-usage` `:1027-1031`, `--research-scanners` `:1042-1048`,
   `--red-agents/:961`, `--blue-agents/:964`,
   `--allow-remote-inference` `:969-973`, `--intel-offline` `:1009-1013`);
   UI absences unchanged (`static/app.js:757` hint text,
   `:432-435` ultra_heavy gate, `:726-728` hardcoded 4-scanner list,
   `:566-567` usage-hidden-when-empty, `:931` coerced `intel_offline`;
   `static/index.html:83-84` disabled agent inputs, `:88` project-form-only
   consent; TUI still fixture-only `tui.py:291,376`). **Dropped: none
   (0 of 13 closed).**
2. **LAW 8 — surface wiring (see matrix below).** Every gap: CLI ✓ (source
   surface), Web UI ✗ (no control), TUI ✗ (TUI exposes only `--fixture`
   picker + start/stop/scroll/filter; it wires none of the 13). Gaps 4
   (`--tui`) and 5 (`--port`) are CLI-only by nature (noted in matrix).
3. **LAW 10B — blast radius (see matrix below).** Files that wiring each gap
   would touch. No wiring done — audit only.
4. **LAW 11: N/A (audit only).** This rerun changes no behavior, schema,
   API, or docs contract beyond this audit file itself; there is no
   migration, compat, or rollout surface to assess.

### LAW 8 × LAW 10B matrix (all 13 surviving gaps)

| # | Gap (CLI flag) | Lacks wiring on | Blast-radius files to wire it |
|---|---|---|---|
| 1 | `--init-images` (`main.py:901`) | Web UI, TUI | `static/index.html` (button), `static/app.js` (action), `main.py` (new endpoint/WS action reusing `ensure_base_images` handler `:1194-1197`), `tests/` |
| 2 | `--rebuild-images` (`main.py:904`) | Web UI, TUI | Same as 1 (reusing `build_base_images`), `docker_manager.py` (no change — fn exists) |
| 3 | `--cleanup` (`main.py:909-912`, handler `:1198-1201`) | Web UI, TUI | Same as 1 (reusing `remove_stale_resources`), plus per-session vs stale-scope confirmation copy in `static/index.html` |
| 4 | `--tui` (`main.py:915-919`) | Web UI (by nature — dashboard *is* the alt surface), TUI (self) | Docs only; no wiring is meaningful (server has no terminal to offer a browser client) |
| 5 | `--port` (`main.py:937`, consumed `:1203,1291`) | Web UI (by nature — page runs inside the bound server), TUI | None/docs only; port is a serve-time bind, not a scan parameter |
| 6 | `--cve-scan` (`main.py:979-983`, exec `:589-594`, CLI plumb `:1283`) | Web UI, TUI | `static/index.html` (toggle), `static/app.js` (`projectSpec` + `/ws/project` body), `main.py` (`run_socket` `:258-345` + `cli_runner` params), `cve_workflow.py` (exists), `tests/` |
| 7 | `--deep-assessment` (`main.py:984-988`, plumb `:1284`) | Web UI, TUI | Same as 6 |
| 8 | `--offline-cve` (`main.py:989-993`, plumb `:1285`) | Web UI, TUI | Same as 6 (`include_osv=not offline_cve` already supported at `:594`) |
| 9 | `--config` (`main.py:1014-1020`; `sms_cli.py:27-46,87-124`) | Web UI, TUI | `static/index.html` (file input), `static/app.js` (parse + merge into spec/query), `main.py` (accept config payload), `sms_cli.py` (reuse `load_config_file`/`merge_config` server-side), `tests/` |
| 10 | `--show-usage` (`main.py:1027-1031`) | Web UI (empty-case only), TUI | `static/app.js:566-567` (honor flag instead of `calls.length === 0`), `static/index.html` (toggle), `main.py` (socket query passthrough) |
| 11 | Arbitrary `--red-agents`/`--blue-agents` (`main.py:960-965`, guard `:1115-1118`) | Web UI (non-ultra profiles), TUI | `static/app.js:432-435` + `static/index.html:83-84` only (enable inputs); `projects.py`/`main.py` validation already allows 1–12 |
| 12 | `--research-scanners` picker (`main.py:1042-1048`, allowlist `main.py:277`) | Web UI (choice; hardcoded 4 at `static/app.js:726-728`), TUI | `static/app.js:726-728` + `static/index.html:87` (multi-select); server allowlist already covers all 5 |
| 13 | `--allow-remote-inference` + `--intel-offline` for `--ai-demo` (`main.py:969-973,1009-1013`) | Web UI Green-build mode (consent checkbox hidden by `setSourceMode`, `static/app.js:389-399`; offline coerced at `:931` + `main.py:472-473`), TUI | `static/index.html:62-66` (visible consent + offline toggle in `demo-build-config`), `static/app.js` (`:931` send), `main.py` (`run_demo_build` `:437-452` coercion `:471-473`), `tests/` |

## Method

- CLI inventory: `main.py` argparse block (`main.py:899-1048`), config-file
  keys (`sms_cli.py:27-46`), TUI flags (`tui.py:291,376`). `sms_cli.py` has
  no argparse of its own — it is a presentation/config leaf (tables,
  spinner, TOML/JSON loader at `sms_cli.py:87-124`).
- UI inventory: full read of `static/index.html` (217 lines, every
  input/select/textarea/button) and `static/app.js` (1063 lines: `socketQuery`
  at `:721-731`, `projectSpec` at `:443-468`, `startDemoBuild` at `:891-935`,
  profile/intensity wiring at `:426-441`).
- Absence proof: grepped `static/app.js` + `static/index.html` for each flag
  stem (`cve`, `deep.assess`, `offline.cve`, `config`, `toml`, `output.dir`,
  `show.usage`, `init.image`, `rebuild`, port control, scanner picker).
  Only hits were result *displays* (pipeline stage, fact rows), never
  controls — cited per item below.

## Gaps

### Server / lifecycle ops (no UI control by design, still CLI-only)

1. **`--init-images`** (`main.py:900-901`).
   UI side: zero control. Nearest neighbor is a *text hint* telling the user
   to run the CLI command (`static/app.js:757`: `"Run python main.py
   --init-images."`). A hint is not a control.
2. **`--rebuild-images`** (`main.py:903-904`).
   UI side: nothing. No occurrence of `rebuild` anywhere in
   `static/index.html` or `static/app.js`.
3. **`--cleanup`** — remove stale session resources (`main.py:909-912`,
   handler `:1198-1201`).
   UI side: the pipeline `cleanup` stage (`static/index.html:117`) and the
   `fact-cleanup` result row (`static/app.js:703`) only *display* per-scan
   cleanup. No button invokes stale-resource removal.
4. **`--tui`** — launch the terminal UI (`main.py:915-919`).
   UI side: nothing launches the TUI from the dashboard (the dashboard *is*
   the alternative surface, not a TUI launcher).
5. **`--port`** — server bind port (`main.py:937`, consumed `:1203,1291`).
   UI side: no port control exists; the page runs inside the already-bound
   server. CLI-only by nature, recorded for completeness.

### Project deep-scan trio (CLI project-only; no dashboard toggle)

6. **`--cve-scan`** — static+CVE scan instead of probe/patch
   (`main.py:979-983`, wired to `execute_cve_scan` at `:589-594`,
   CLI-plumbed at `:1283`).
   UI side: `projectSpec()` (`static/app.js:443-468`) sends no `cve_scan`
   field; the project form (`static/index.html:67-90`) has no such toggle;
   the `/ws/project` socket path (`main.py:422-424` + `:317-335`) builds the
   spec from the socket JSON only. Unreachable from UI.
7. **`--deep-assessment`** — Muse triage of static/CVE signals
   (`main.py:984-988`, plumbed at `:1284`).
   UI side: same absence as (6) — no field, no toggle, no socket key.
8. **`--offline-cve`** — skip OSV network lookup (`main.py:989-993`,
   plumbed at `:1285`).
   UI side: same absence as (6). Note the dashboard *result* view does render
   `research_records` (`static/app.js:604-616`), but that is display of
   sidecar output, not the CVE-scan mode switch.

### Config / output shaping

9. **`--config`** — TOML/JSON `[sms]` defaults file (`main.py:1014-1020`;
   loader `sms_cli.py:87-124`, key set `sms_cli.py:27-46`).
   UI side: no file-upload or defaults control; the project form
   (`static/index.html:67-90`) holds only per-scan fields.
10. **`--show-usage`** — print token/cost table even with zero model calls
    (`main.py:1027-1031`).
    UI side (qualified — display exists, the *empty* case does not): usage
    renders only when calls exist (`static/app.js:566-567`:
    `el('usage').hidden = calls.length === 0`). Forcing the empty table is
    CLI-only. Minor.

### Intensity controls the dashboard gates or hardcodes

11. **Arbitrary `--red-agents` / `--blue-agents` outside `ultra_heavy`**
    (`main.py:960-965`; CLI allows 1–12 with any profile, `:1115-1118`).
    UI side (qualified): inputs exist (`static/index.html:83-84`) but are
    `disabled` unless `ultra_heavy` (`static/app.js:432-435`); other profiles
    cannot set team size. E.g. CLI `--scan-profile heavy --red-agents 8`
    has no UI expression.
12. **`--research-scanners` picker** (`main.py:1042-1048`; server allowlist
    of 5 at `main.py:277`).
    UI side (qualified): hardcoded to 4 scanners, no `dependency-track`, no
    user choice (`static/app.js:726-728`:
    `'trivy,grype,osv-scanner,dependency-check'`). CLI can select any
    allowlisted subset including `dependency-track`; the UI cannot express
    `dependency-track` at all.
13. **Green-build consent/offline pair: `--allow-remote-inference` +
    `--intel-offline` for `--ai-demo`** (`main.py:969-973,1009-1013`).
    UI side (qualified): the `allow-remote` checkbox lives *inside* the
    project form (`static/index.html:88`) which is hidden in Green-build mode
    (`static/app.js:397-399` `setSourceMode`); the demo socket instead
    *coerces* `intel_offline` from that hidden checkbox
    (`static/app.js:931`, server coercion `main.py:472-473`). There is no
    explicit offline toggle (`demo-build-config`, `static/index.html:62-66`,
    has brief/vulns/theme only) and no visible consent control in Green
    mode. The CLI's explicit `--intel-offline` / consent flags have zero
    Green-mode UI equivalent.

## Explicitly NOT gaps (covered — evidence of exhaustiveness)

- `--scan` → target cards + Run (`index.html:56-61,95-100`; `app.js:814`).
- `--project`, `--image`, `--command`, `--test-command`, `--contract` →
  project form fields (`index.html:67-72`; `app.js:446-464,468`).
- `--scan-profile`, `--cycles` (custom), `--context-budget` →
  `project-scan-profile` / `project-cycles` / `project-budget`
  (`index.html:73-85`; `app.js:426-441,450-461`). Fixture/demo scans have no
  cycles knob on *either* surface — parity, not a gap.
- `--profile` → profile radiogroup (`index.html:91-94`; `app.js:492-513`).
- `--research` → `research-toggle` (`index.html:86`; `app.js:724-725`).
- `--build-brief`, `--vulns`, `--intel-theme` → Green-build inputs
  (`index.html:62-66`; `app.js:931` sends all three).
- `--allow-remote-inference` (project mode) → `allow-remote` checkbox
  (`index.html:88`; `app.js:462,468`).
- `--health` → status chips + setup notes from `/api/health`
  (`index.html:23-27`; `app.js:742-763`).
- `--list-targets` → target cards from `/api/targets`
  (`index.html:57-59`; `app.js:740-741`).
- `--docker-status` → Docker chip from the same `docker_status()` source
  (`index.html:25`; `app.js:751-753`).
- `--format json` → Download JSON report (`app.js:977-993`); table mode is
  the visual result itself.
- `--output-dir` → Download JSON + Download patch buttons
  (`app.js:977-1003`). Server-side run dir vs browser download differs in
  mechanism, same user-visible artifact — not counted.
- `--serve` → N/A (the dashboard is the served thing).
- `tui.py --fixture` (`tui.py:291,376`) → target picker parity; TUI
  filter/scroll/start/stop keys map to dashboard filters, native scroll,
  Run/Stop buttons. TUI contributes no unique capability.

## Traps found while auditing (not gaps — accepted-but-ignored flags)

- `main.py --scan <fixture> --red-agents/--blue-agents/--context-budget/--cycles`:
  argparse accepts them (the project-options guard at `main.py:1137-1152`
  does not list red/blue/context), but `cli_runner` (`main.py:553-566`)
  takes none of those params on the fixture path — silently dropped.
- `main.py --ai-demo --cycles/--context-budget`: same — `ai_demo_runner`
  (`main.py:437-452`) has no `cycles`/`context_budget` params
  (`--red-agents/--blue-agents` ARE forwarded at `main.py:529-538`).
  Recommend either rejecting or forwarding these; silence is the trap.

## Notes

- `sms_cli.py` defines no CLI flags; its `CONFIG_KEYS`
  (`sms_cli.py:27-46`) are the `--config`-file surface, covered by gap 9.
- Server WS routes accept only `profile` / `research` / `research_scanners`
  query params (`main.py:272-291`) plus spec/request JSON bodies
  (`:317-345`); every gap above corresponds to a key the socket never
  reads.
