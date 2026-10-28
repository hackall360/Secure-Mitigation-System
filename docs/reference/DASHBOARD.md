# Dashboard panels and hooks map

`static/app.js` owns all DOM writes and network calls; `fx.js` and `panels.js`
are side-effect-scoped layers. CSP-safe throughout: `textContent` and
`setAttribute` only, no `innerHTML`, no `eval`, no inline handlers.

## Layers

| File | Hooks in / out |
|---|---|
| `static/app.js` | Owns `writeLine(team, msg)`, WebSocket fan-out (`/ws/project`, `/ws/combat/{target}`), all `fetch()` and `addEventListener` wiring. |
| `static/fx.js` | Motion layer in: cursor glow, parallax CSS vars, stage data-flow pulses. Out: none (visual only). WAAPI + rAF-throttled, transform/opacity only, honors `prefers-reduced-motion`. Companion CSS at tail of `static/app.css`. |
| `static/panels.js` | Timeline markers in: `writeLine(team, msg)` calls from `app.js`. Out: marker strip (max 100 markers). |

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

Related: [MODULES.md](MODULES.md), [CLI.md](CLI.md).
