# ADR 003: Dashboard UI layers (`app.js` / `panels.js` / `fx.js`)

Date: 2026-10-28 · Status: accepted

## Context

The arena dashboard needed timeline markers and motion without risking XSS or
layout thrash in the scan feed path.

## Decision

Three layers with strict scopes: `app.js` owns all DOM writes, network, and
the `writeLine(team, msg)` chokepoint; `panels.js` only taps `writeLine` to
render timeline markers (max 100); `fx.js` is visual-only (cursor glow,
parallax vars, data-flow pulses via WAAPI + rAF, transform/opacity only,
`prefers-reduced-motion` honored). CSP-safe: `textContent`/`setAttribute`
only, external files, no inline handlers.

## Consequences

Pro: feed path stays auditable; motion/markers removable without touching scan
logic. Con: hook contract (`writeLine` signature) is implicit — pinned in
[reference/DASHBOARD.md](../reference/DASHBOARD.md).
