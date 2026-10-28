# CLI → Dashboard Gap Audit

Date: 2026-10-28. Auditor: read-only agent session.
Scope: every CLI flag/option in `sms_cli.py`, `main.py` argparse, `tui.py`
vs every dashboard control in `static/index.html` + `static/app.js`.
Rule: a gap = CLI capability with **zero** UI equivalent. Each item carries
file:line evidence on **both** sides (CLI definition + nearest UI neighbor
proving the absence was checked, not assumed).

**Gap count: 13** (10 full, 3 qualified/partial). No source files were
touched; this file is the only write.

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
