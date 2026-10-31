# Dashboard panels and hooks map

`static/app.js` owns all DOM writes and network calls; `fx.js` and `panels.js`
are side-effect-scoped layers. CSP-safe throughout: `textContent` and
`setAttribute` only, no `innerHTML`, no `eval`, no inline handlers.

## Layers

| File | Hooks in / out |
|---|---|
| `static/app.js` | Owns `writeLine(team, msg)`, WebSocket fan-out (`/ws/project`, `/ws/combat/{target}`), all `fetch()` and `addEventListener` wiring. |
| `static/graph.js` | Phase-graph renderer in: `SMSGraph.update({stage} | {result})` from `setStage`/`showResult`. Out: none (canvas only, decorative). Canvas-2D force layout, team colors (green/red/blue/purple), edge particles, purple freeze on verified, `prefers-reduced-motion` static. |
| `static/fx.js` | Motion layer in: cursor glow, parallax CSS vars, stage data-flow pulses. Out: none (visual only). WAAPI + rAF-throttled, transform/opacity only, honors `prefers-reduced-motion`. Companion CSS at tail of `static/app.css`. |
| `static/panels.js` | Timeline markers in: `writeLine(team, msg)` calls from `app.js`. Out: marker strip (max 100 markers). Doubles as the graph fallback path: stays mounted and rendering even when `SMSGraph` is off (`isFallback()`). |

## Guidance routes, scoreboard, HUD (2026-10-30)

Hash routes in the single served shell — no server route churn, deep-linkable,
back-button safe. Modes sync to the route; every control keeps its id/handler.

| Route / surface | DOM ids | Render fn | Source |
|---|---|---|---|
| `#/` landing | `view-landing` | `applyRoute`/`bootRoutes` (`app.js`) | Static hero; links to `#/demo` / `#/live`. |
| `#/demo` happy path | `view-demo` | `applyRoute` + `setSourceMode('demo')` | Bundled fixtures + Green build (`demo`, `demo-build` modes). |
| `#/live` real-time | `view-live` | `applyRoute` + `setSourceMode('project')` | Project / MCP / binary (`project`, `mcp`, `binary` modes). |
| Phase graph | `phase-graph` | `SMSGraph.init/update/kick` (`graph.js`) | Stage/result events; `isFallback()` true only when canvas bind fails. |
| Scoreboard | `scoreboard`, `score-agents`, `score-vulns`, `score-patches`, `score-verified` | `renderScoreboard` (`app.js`) | Roster presence + result outcomes (pre_probe_exit, diff, verified). Session-only, no backend call. |
| HUD toggles | `hud-toggle-sweep/profile/research/compression/vault/differential/binary` | `bootRoutes` hud wiring (`app.js`) | Each flips an existing surface (sweep select, profile row, research checkbox, fact rows, cycle reports, binary mode). No dead controls. |

## Key hooks (`app.js`)

| Hook | Role |
|---|---|
| `writeLine(team, text)` | Single chokepoint for feed lines; `panels.js` taps it for markers |
| `fetch('/api/targets')` + `fetch('/api/health')` | Bootstraps fixture list and readiness |
| `run-btn` / `stop-btn` click | `startScan` / `stopScan` |
| `.mode` buttons click | Source mode switch (fixture vs project) |
| `project-scan-profile` change | `updateScanProfile` |
| `allow-remote` change | Remote-inference consent toggle |
| `download-btn` click | Evidence download |
| WebSocket `onmessage` | Routes `payload.team`/`payload.msg` to `writeLine`; unreadable events get a system line |
| `socket.onerror` / close | System lines; server finishes cleanup before next scan |

## MCP snippet panel (Milestone 2)
`POST /mcp` (Streamable HTTP JSON-RPC) exposes `submit_code_snippet`;
the dashboard `MCP snippet` mode posts the same call and renders the
structured result inline. No WebSocket involved.

| Fact / panel | DOM ids | Render fn | Source fields |
|---|---|---|---|
| MCP snippet form | `mcp-form`, `mcp-language`, `mcp-filename`, `mcp-source`, `mcp-contract`, `mcp-errors`, `mcp-result` | `submitMcpSnippet` (`app.js`) | `fetch('/mcp')` JSON-RPC `tools/call submit_code_snippet`; result text `status/pre_probe_exit/post_probe_exit/receipt sha12`. |

## Sweep depth selector (Milestone 3)

Fixture scans accept `?sweep_passes=2|3` (mirrors `--sweep-passes`); absent/1
keeps the legacy single loop. `summaryEvidence` rolls `pass_results` into the
shared summary shape (`N/M passes hold`, per-pass reachable/blocked counts).

| Fact / panel | DOM ids | Render fn | Source fields |
|---|---|---|---|
| Sweep depth | `sweep-passes` | `socketQuery` (`app.js`) | `?sweep_passes=2|3` on `/ws/combat/{key}`; value `1` sends nothing. |
| Pass summary | `result-meta` | `renderResultMeta` via `summaryEvidence` | `pass_results[]` (`pass_id`, `pre/post_exit_code`, `cleared`, `receipt`, `regression_passed`). |

## Binary sweep panel (Milestone 4)

`/ws/binary` takes the validated binary as a base64 first frame (`blob_b64`,
bare `filename`, `contract`; 8 MiB cap, magic-checked server-side) and runs
the binary 4-pass sweep over the shared socket flow; `summaryEvidence`
renders `pass_results` the same way as source sweeps.

| Fact / panel | DOM ids | Render fn | Source fields |
|---|---|---|---|
| Binary mode | `mode-binary`, `binary-form`, `binary-file`, `binary-filename`, `binary-contract`, `binary-errors` | `submitBinary` (`app.js`) | FileReader → base64 → first WS frame on `/ws/binary`; per-field client validation. |

## Wave 2 (SPEC 14.8) panels (`renderW2v2`, `static/app.js:807`)

All collectors are defensive (optional fields, odd shapes degrade to null,
never throw). DOM ids verified in `static/index.html:202-217`.

| Fact / panel | DOM ids | Render fn | Source fields |
|---|---|---|---|
| Verdict receipt (`Verdict receipt` row) | `fact-receipt`, `download-receipt-btn` | `w2v2Receipt` (`app.js`) | `result.receipt` (VerdictReceipt) or first `cycle.receipt` (CycleReceipt); legacy `verdict_receipt`. Text: `fixture`, `probe pre/post`, `regression passed` (or `baseline/patched` exits), `differential passed`, `properties passed`, `sha <12>`, `chain ok/broken` (W7: `w2v2Chain` reads `chain_ok` else `prev_receipt_sha` link; render only). Button downloads live receipt as JSON (license notice wrapper); hidden when no receipt. |
| Receipt chain (`Receipt chain` row + verify badge) | `fact-receipt-chain`, `receipt-chain-badge` (`status` verified/failed/idle) | `w2v2Chain` + `renderW2v2` (`app.js`) | Same receipt record; badge text `chain verified` / `chain broken` / `chain unknown`, `data-state` follows. |
| Guard rationales | `fact-guards`, `guard-rationales` + `guard-list` | `w2v2Guards` (`app.js:707`) | Top-level `guard_rationale`, then each cycle `evidence.replacement_validation.guard_rationale` / `evidence.guard_rationale` (`guard_id`/`reason`/`trigger`); legacy `guard_rationales` list. Max 3 cycles, max 8 shown; wrap unhidden only when non-empty. |
| Fast-lane topping | `fact-topping`, `fast-lane-topping` + `topping-list` | `w2v2Topping` (`app.js:747`) | First 10 `vulnerabilities[]` with `queue_evidence` or `reach_score`: `id`/`cves[0]`, `queue_evidence` (else `reach N`), `fixed_versions[0]`, `KEV-listed`, `EPSS x.xx`, `reach_evidence[]` sub-list. |
| Mutation probes | `fact-mutations`, `mutation-evidence` + `mutation-text` | `w2v2Mutation` (`app.js:766`) | Cycle `evidence.{patched,pre}_verification.mutations` `ExecutionEvidence` (`N/M held|failed (exit N)` parsed from output); legacy `mutation_evidence`/`mutations` dict. Wrap unhidden only when present. |

## Wave 5 (SPEC 14.9) — no new panels

Verified via `static/app.js` + `static/index.html` grep 2026-10-29: SPEC 14.9
adds no panels, DOM ids, or render functions. Freshness/template state flows
through existing surfaces only:

| Behavior | Existing panel | How it shows |
|---|---|---|
| Queue freshness | Fast-lane topping (`w2v2Topping`, `app.js:747`) | Same `queue_evidence` string; stale-dated signals render as `kev:absent` / `epss:absent` — no freshness badge or date text (stamps are internal). |
| EUVD exclusion | None | Fail-closed assert only; no panel or feed line. |
| Solver-shape guard | Guard rationales (`w2v2Guards`, `app.js:707`) | Same `{guard_id, reason, trigger}` rows; `solver_synthesized_shape` appears as another `guard_id` value. |
| Frozen mutation pool | Mutation probes (`w2v2Mutation`, `app.js:766`) | Drift surfaces only as the existing failed-mutation `N/M` text; no digest shown. |

Related: [MODULES.md](MODULES.md), [CLI.md](CLI.md).
